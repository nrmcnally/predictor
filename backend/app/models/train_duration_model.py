from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.features.duration_features import (
    add_interval_features,
    build_matchup_duration_features,
    duration_categorical_feature_names,
    duration_numeric_feature_names,
)
from app.repositories import event_fights_repository
from app.services.duration_settlement import ROUND_SECONDS, resolve_fight_duration, settle_duration_result


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"
TRAINING_MATCHUPS_CSV = PROCESSED_DATA_DIR / "training_matchups.csv"
DURATION_MODEL_PATH = MODELS_DIR / "duration_model.joblib"
DURATION_FEATURES_PATH = MODELS_DIR / "duration_model_features.json"
DURATION_METRICS_PATH = MODELS_DIR / "duration_model_metrics.json"

MODEL_TYPE = "discrete_time_survival"
MODEL_VERSION = "duration-survival-0.2.0"
FEATURE_SCHEMA_VERSION = "duration-survival-features-2"
SETTLEMENT_VERSION = "ufc-standard-rounds-2"
INTERVAL_ROUNDS = 0.5
SUPPORTED_SCHEDULES = (3, 5)


def hazard_intervals(scheduled_rounds: int) -> list[float]:
    """Half-round interval ends used by the discrete-time hazard likelihood."""
    count = int(round(float(scheduled_rounds) / INTERVAL_ROUNDS))
    return [round((index + 1) * INTERVAL_ROUNDS, 1) for index in range(count)]


def supported_market_lines(scheduled_rounds: int) -> list[float]:
    """Sportsbook-style half-round totals that occur before the scheduled limit."""
    return [
        line
        for line in hazard_intervals(scheduled_rounds)
        if line < scheduled_rounds and math.isclose(line % 1.0, 0.5, abs_tol=1e-9)
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_state() -> dict[str, Any]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT.parent, text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=PROJECT_ROOT.parent, text=True
            ).strip()
        )
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"commit": "", "dirty": None}


def _metric_payload(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    *,
    fight_urls: np.ndarray | None = None,
) -> dict[str, Any]:
    clipped = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    truth = np.asarray(y_true, dtype=int)
    predicted = (clipped >= 0.5).astype(int)
    auc = float(roc_auc_score(truth, clipped)) if len(np.unique(truth)) > 1 else None
    payload = {
        # Kept for UI/API compatibility; in the multi-line backtest this is the
        # number of exact-line observations, not the unique-fight count.
        "fight_count": int(len(truth)),
        "line_observation_count": int(len(truth)),
        "accuracy": float(accuracy_score(truth, predicted)),
        "brier_score": float(brier_score_loss(truth, clipped)),
        "log_loss": float(log_loss(truth, clipped, labels=[0, 1])),
        "roc_auc": auc,
        "over_rate": float(truth.mean()),
        "average_over_probability": float(clipped.mean()),
    }
    if fight_urls is not None:
        payload["unique_fights"] = int(pd.Series(fight_urls).nunique())
    return payload


def _calibration_rows(y_true: np.ndarray, probabilities: np.ndarray) -> list[dict[str, Any]]:
    frame = pd.DataFrame({"actual": y_true, "probability": probabilities})
    edges = [0.0, 0.4, 0.5, 0.6, 1.000001]
    labels = ["Under lean", "Near 50% (Under)", "Near 50% (Over)", "Over lean"]
    frame["bucket"] = pd.cut(
        frame["probability"], bins=edges, labels=labels, include_lowest=True, right=False
    )
    rows: list[dict[str, Any]] = []
    for label in labels:
        group = frame[frame["bucket"] == label]
        if group.empty:
            continue
        rows.append(
            {
                "name": label,
                "line_observation_count": int(len(group)),
                "average_over_probability": float(group["probability"].mean()),
                "actual_over_rate": float(group["actual"].mean()),
            }
        )
    return rows


def build_duration_fights() -> tuple[pd.DataFrame, dict[str, int]]:
    """One resolved elapsed-time row per unique historical fight."""
    if not TRAINING_MATCHUPS_CSV.exists():
        raise FileNotFoundError(f"Missing training matchups: {TRAINING_MATCHUPS_CSV}")

    matchups = pd.read_csv(TRAINING_MATCHUPS_CSV, low_memory=False)
    matchups["event_date_parsed"] = pd.to_datetime(matchups["event_date"], errors="coerce")
    matchups = (
        matchups.sort_values(["event_date_parsed", "fight_url"])
        .drop_duplicates(subset=["fight_url"], keep="first")
        .reset_index(drop=True)
    )

    results = event_fights_repository.read_all_df().copy()
    result_columns = [
        "fight_url",
        "result_1",
        "result_2",
        "winner",
        "method",
        "round",
        "time",
    ]
    merged = matchups.merge(results[result_columns], on="fight_url", how="left")
    merged["fight_context_scheduled_rounds"] = pd.to_numeric(
        merged["fight_context_scheduled_rounds"], errors="coerce"
    )

    exclusions: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        duration = resolve_fight_duration(
            row,
            scheduled_rounds=row.get("fight_context_scheduled_rounds"),
        )
        if duration["status"] != "resolved":
            exclusions[duration.get("reason") or duration["status"]] += 1
            continue
        record = row.to_dict()
        record["elapsed_seconds"] = float(duration["elapsed_seconds"])
        record["observed_finish"] = bool(duration["observed_finish"])
        records.append(record)

    fights = pd.DataFrame(records)
    fights = fights.dropna(subset=["event_date_parsed"]).sort_values(
        ["event_date_parsed", "fight_url"]
    )
    return fights.reset_index(drop=True), dict(sorted(exclusions.items()))


def build_person_period_dataset(fights: pd.DataFrame) -> pd.DataFrame:
    """Expand resolved fights into at-risk half-round intervals.

    A finish contributes one event interval. A decision is administratively
    censored at the scheduled limit and contributes survival intervals only.
    """
    base_features = build_matchup_duration_features(fights)
    rows: list[dict[str, Any]] = []

    for index, fight in fights.iterrows():
        scheduled_rounds = int(fight["fight_context_scheduled_rounds"])
        elapsed_seconds = float(fight["elapsed_seconds"])
        observed_finish = bool(fight["observed_finish"])
        base = base_features.loc[index].to_dict()

        for interval_end in hazard_intervals(scheduled_rounds):
            interval_start_seconds = (interval_end - INTERVAL_ROUNDS) * ROUND_SECONDS
            interval_end_seconds = interval_end * ROUND_SECONDS
            if elapsed_seconds <= interval_start_seconds:
                break

            event_in_interval = int(
                observed_finish and elapsed_seconds <= interval_end_seconds
            )
            rows.append(
                {
                    **add_interval_features(base, interval_end),
                    "fight_url": str(fight["fight_url"]),
                    "event_date_parsed": fight["event_date_parsed"],
                    "target_hazard": event_in_interval,
                }
            )
            if event_in_interval:
                break

    return pd.DataFrame(rows)


def build_prediction_grid(fights: pd.DataFrame) -> pd.DataFrame:
    """All scheduled intervals for holdout fights, independent of their results."""
    base_features = build_matchup_duration_features(fights)
    rows: list[dict[str, Any]] = []
    for index, fight in fights.iterrows():
        scheduled_rounds = int(fight["fight_context_scheduled_rounds"])
        base = base_features.loc[index].to_dict()
        for interval_end in hazard_intervals(scheduled_rounds):
            rows.append(
                {
                    **add_interval_features(base, interval_end),
                    "fight_url": str(fight["fight_url"]),
                    "interval_end_rounds": interval_end,
                }
            )
    return pd.DataFrame(rows)


def survival_curves_from_hazards(
    prediction_grid: pd.DataFrame, hazards: np.ndarray
) -> dict[str, dict[float, float]]:
    scored = prediction_grid[["fight_url", "interval_end_rounds"]].copy()
    scored["hazard"] = np.clip(np.asarray(hazards, dtype=float), 1e-6, 1 - 1e-6)
    curves: dict[str, dict[float, float]] = {}
    for fight_url, rows in scored.groupby("fight_url", sort=False):
        survival = 1.0
        curve: dict[float, float] = {}
        for _, row in rows.sort_values("interval_end_rounds").iterrows():
            survival *= 1.0 - float(row["hazard"])
            curve[float(row["interval_end_rounds"])] = float(survival)
        curves[str(fight_url)] = curve
    return curves


def build_line_outcomes(
    fights: pd.DataFrame,
    curves: dict[str, dict[float, float]] | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, fight in fights.iterrows():
        scheduled_rounds = int(fight["fight_context_scheduled_rounds"])
        fight_url = str(fight["fight_url"])
        for line in supported_market_lines(scheduled_rounds):
            settlement = settle_duration_result(
                fight,
                line=line,
                scheduled_rounds=scheduled_rounds,
            )
            if settlement["status"] != "settled":
                continue
            row = {
                "fight_url": fight_url,
                "event_name": str(fight["event_name"]),
                "event_date_parsed": fight["event_date_parsed"],
                "fighter_1": str(fight["fighter_a"]),
                "fighter_2": str(fight["fighter_b"]),
                "line": float(line),
                "target_over": int(settlement["target_over"]),
            }
            if curves is not None:
                row["over_probability"] = float(curves[fight_url][float(line)])
            rows.append(row)
    return pd.DataFrame(rows)


def _build_model(numeric_columns: list[str], categorical_columns: list[str]) -> Pipeline:
    preprocessing = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_columns,
            ),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("one_hot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_columns,
            ),
        ]
    )
    return Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            ("classifier", LogisticRegression(C=0.5, max_iter=3000, solver="liblinear")),
        ]
    )


def train_duration_model() -> dict[str, Any]:
    fights, exclusions = build_duration_fights()
    if len(fights) < 100:
        raise RuntimeError("Not enough resolved fights to train the duration survival model.")

    target_split_index = max(1, min(len(fights) - 1, int(math.floor(len(fights) * 0.8))))
    test_start_date = fights.iloc[target_split_index]["event_date_parsed"]
    train_fights = fights[fights["event_date_parsed"] < test_start_date].copy().reset_index(drop=True)
    test_fights = fights[fights["event_date_parsed"] >= test_start_date].copy().reset_index(drop=True)
    if train_fights.empty or test_fights.empty:
        raise RuntimeError("Chronological 80/20 split produced an empty fight partition.")

    train_periods = build_person_period_dataset(train_fights)
    prediction_grid = build_prediction_grid(test_fights)
    numeric_columns = duration_numeric_feature_names()
    categorical_columns = duration_categorical_feature_names()
    model = _build_model(numeric_columns, categorical_columns)
    model.fit(
        train_periods[numeric_columns + categorical_columns],
        train_periods["target_hazard"].astype(int).to_numpy(),
    )

    hazards = model.predict_proba(
        prediction_grid[numeric_columns + categorical_columns]
    )[:, 1]
    curves = survival_curves_from_hazards(prediction_grid, hazards)
    test_lines = build_line_outcomes(test_fights, curves)
    train_lines = build_line_outcomes(train_fights)
    if test_lines.empty or train_lines.empty:
        raise RuntimeError("No settled exact-line observations were available for evaluation.")

    y_test = test_lines["target_over"].astype(int).to_numpy()
    probabilities = test_lines["over_probability"].astype(float).to_numpy()
    test_metrics = _metric_payload(
        y_test,
        probabilities,
        fight_urls=test_lines["fight_url"].astype(str).to_numpy(),
    )

    training_over_rates = {
        float(line): float(rows["target_over"].mean())
        for line, rows in train_lines.groupby("line")
    }
    global_training_over_rate = float(train_lines["target_over"].mean())
    baseline_probabilities = np.asarray(
        [training_over_rates.get(float(line), global_training_over_rate) for line in test_lines["line"]],
        dtype=float,
    )
    baseline_metrics = _metric_payload(
        y_test,
        baseline_probabilities,
        fight_urls=test_lines["fight_url"].astype(str).to_numpy(),
    )

    by_line: list[dict[str, Any]] = []
    for line_value, line_rows in test_lines.groupby("line", sort=True):
        line_truth = line_rows["target_over"].astype(int).to_numpy()
        line_probabilities = line_rows["over_probability"].astype(float).to_numpy()
        row = _metric_payload(
            line_truth,
            line_probabilities,
            fight_urls=line_rows["fight_url"].astype(str).to_numpy(),
        )
        row["line"] = float(line_value)
        row["training_base_over_rate"] = training_over_rates.get(float(line_value))
        by_line.append(row)

    monotonic_violations = 0
    for curve in curves.values():
        values = [curve[line] for line in sorted(curve)]
        monotonic_violations += sum(
            1 for previous, current in zip(values, values[1:]) if current > previous + 1e-12
        )

    recent_results: list[dict[str, Any]] = []
    recent_lines = test_lines.sort_values(
        ["event_date_parsed", "fight_url", "line"], ascending=[False, True, True]
    ).head(40)
    for _, row in recent_lines.iterrows():
        over_probability = float(row["over_probability"])
        predicted_side = "over" if over_probability >= 0.5 else "under"
        actual_side = "over" if int(row["target_over"]) == 1 else "under"
        recent_results.append(
            {
                "fight_url": str(row["fight_url"]),
                "event_name": str(row["event_name"]),
                "event_date": row["event_date_parsed"].date().isoformat(),
                "fighter_1": str(row["fighter_1"]),
                "fighter_2": str(row["fighter_2"]),
                "line": float(row["line"]),
                "over_probability": over_probability,
                "predicted_side": predicted_side,
                "predicted_probability": max(over_probability, 1 - over_probability),
                "actual_side": actual_side,
                "correct": predicted_side == actual_side,
            }
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    git_state = _git_state()
    lines_by_schedule = {
        str(rounds): supported_market_lines(rounds) for rounds in SUPPORTED_SCHEDULES
    }
    metrics = {
        "status": "experimental_backtest",
        "message": (
            "Chronological 80/20 historical evaluation of an experimental discrete-time "
            "survival model. Market odds are not model inputs. The model is integrated "
            "as an experimental Future Cards insight and is not production-approved."
        ),
        "generated_at": generated_at,
        "model": {
            "name": "Discrete-time half-round survival baseline",
            "type": MODEL_TYPE,
            "version": MODEL_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "settlement_version": SETTLEMENT_VERSION,
            "promotion_status": "experimental",
            "market_inputs_used": False,
            "market_line_role": "query_only",
            "monotonic_by_construction": True,
        },
        "split": {
            "strategy": "chronological_80_20_unique_fights_before_interval_expansion",
            "training_fights": int(len(train_fights)),
            "test_fights": int(len(test_fights)),
            "training_hazard_intervals": int(len(train_periods)),
            "test_line_observations": int(len(test_lines)),
            "training_fraction": float(len(train_fights) / len(fights)),
            "test_fraction": float(len(test_fights) / len(fights)),
            "training_date_min": train_fights["event_date_parsed"].min().date().isoformat(),
            "training_date_max": train_fights["event_date_parsed"].max().date().isoformat(),
            "test_date_min": test_fights["event_date_parsed"].min().date().isoformat(),
            "test_date_max": test_fights["event_date_parsed"].max().date().isoformat(),
        },
        "metrics": test_metrics,
        "base_rate_strategy": "training_over_rate_for_same_exact_line",
        "training_over_rate_by_line": {
            str(line): rate for line, rate in sorted(training_over_rates.items())
        },
        "base_rate_metrics": baseline_metrics,
        "by_line": by_line,
        "calibration": _calibration_rows(y_test, probabilities),
        "recent_results": recent_results,
        "survival_validation": {
            "curves_checked": int(len(curves)),
            "monotonicity_violations": int(monotonic_violations),
        },
        "supported_market_lines_by_scheduled_rounds": lines_by_schedule,
        "dataset": {
            "resolved_fights": int(len(fights)),
            "excluded_fights": int(sum(exclusions.values())),
            "exclusions": exclusions,
            "training_matchups_sha256": _sha256(TRAINING_MATCHUPS_CSV),
        },
        "source": {
            "git_commit": git_state["commit"],
            "git_dirty": git_state["dirty"],
        },
    }

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "artifact_type": "fightiq_duration_survival",
            "model_type": MODEL_TYPE,
            "pipeline": model,
            "numeric_features": numeric_columns,
            "categorical_features": categorical_columns,
            "model_version": MODEL_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "settlement_version": SETTLEMENT_VERSION,
            "trained_at": generated_at,
            "interval_rounds": INTERVAL_ROUNDS,
            "supported_scheduled_rounds": list(SUPPORTED_SCHEDULES),
            "supported_market_lines_by_scheduled_rounds": lines_by_schedule,
            "market_inputs_used": False,
            "market_line_role": "query_only",
            "promotion_status": "experimental",
        },
        DURATION_MODEL_PATH,
    )
    DURATION_FEATURES_PATH.write_text(
        json.dumps(
            {
                "model_type": MODEL_TYPE,
                "model_version": MODEL_VERSION,
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "numeric_features": numeric_columns,
                "categorical_features": categorical_columns,
                "interval_rounds": INTERVAL_ROUNDS,
                "target": "discrete finish hazard within each at-risk half-round interval",
                "curve": "P(fight continues beyond line) is the cumulative product of interval survival",
                "market_contract": "market line is queried after inference; odds and lines are not fighter features",
                "null_policy": "median imputation with missingness indicators for numeric features",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    DURATION_METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    report = train_duration_model()
    print(json.dumps(report, indent=2))
