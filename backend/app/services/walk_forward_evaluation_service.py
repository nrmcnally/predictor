from __future__ import annotations

"""
Walk-forward (expanding-window) backtest.

The single-holdout numbers in model_evaluation_service tell you how the model did
on one slice of recent history. That is one sample, with no sense of variance.

This service instead retrains the production model type once per recent calendar
year, each time training only on fights that happened strictly before that year,
then scoring that year out-of-sample. Rolling this forward gives:

    - a metric per fold (year), so you can see drift and variance
    - an aggregate mean with a 95% confidence interval
    - a transparent Elo-only baseline per fold for context

Nothing here touches the saved production model. It trains throwaway models so the
backtest is honest (no fold is ever scored on data it trained on).
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.models.train_calibrated_models import (
    CALIBRATED_METRICS_PATH,
    build_base_models,
    evaluate_model,
    get_feature_columns,
    make_calibrated_model,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRAINING_MATCHUPS_CSV = PROJECT_ROOT / "data" / "processed" / "training_matchups.csv"
WALK_FORWARD_ARTIFACT_PATH = PROJECT_ROOT / "models" / "walk_forward_evaluation.json"

DEFAULT_N_FOLDS = 8
DEFAULT_MIN_TEST_FIGHTS = 150
DEFAULT_MIN_TRAIN_FIGHTS = 1000

# Fraction of each training window reserved (chronologically) for probability
# calibration, used only when the production model type is a calibrated variant.
CALIBRATION_TAIL_FRACTION = 0.10

_RESULT_CACHE: dict[tuple, dict[str, Any]] = {}


def _load_matchups() -> pd.DataFrame:
    if not TRAINING_MATCHUPS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {TRAINING_MATCHUPS_CSV}. Run the update pipeline first."
        )

    df = pd.read_csv(TRAINING_MATCHUPS_CSV)
    df["event_date_parsed"] = pd.to_datetime(df["event_date"], errors="coerce")
    df = df[df["event_date_parsed"].notna()].copy()
    df["year"] = df["event_date_parsed"].dt.year.astype(int)

    return df


def resolve_production_model_spec() -> tuple[str, str]:
    """
    Returns (base_model_name, calibration_method) describing the current
    production best model, so the backtest replicates the same model family.

    calibration_method is one of: "none", "sigmoid", "isotonic".
    """
    base_name = "logistic_regression"

    if CALIBRATED_METRICS_PATH.exists():
        with open(CALIBRATED_METRICS_PATH, "r", encoding="utf-8") as file:
            payload = json.load(file)

        best = str(payload.get("best_model_name", "") or "")

        if best.startswith("calibrated_"):
            return best[len("calibrated_"):], "sigmoid"
        if best.startswith("shadow_isotonic_"):
            return best[len("shadow_isotonic_"):], "isotonic"
        if best:
            return best, "none"

    return base_name, "none"


def build_fold_plan(
    df: pd.DataFrame,
    n_folds: int,
    min_test_fights: int,
    min_train_fights: int,
) -> list[dict[str, Any]]:
    """
    Picks the most recent calendar years that are large enough to score, and for
    each one defines an expanding training window of every prior fight.
    """
    fights = df.drop_duplicates("fight_url")
    fights_per_year = fights.groupby("year").size()

    eligible_years = sorted(
        year for year, count in fights_per_year.items() if count >= min_test_fights
    )

    folds: list[dict[str, Any]] = []

    for test_year in eligible_years:
        prior_fight_count = int((fights["year"] < test_year).sum())

        if prior_fight_count < min_train_fights:
            continue

        folds.append(
            {
                "test_year": int(test_year),
                "train_fights": prior_fight_count,
                "test_fights": int((fights["year"] == test_year).sum()),
            }
        )

    # Keep only the most recent n_folds windows.
    return folds[-n_folds:]


def _chronological_calibration_split(
    train_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    fight_dates = (
        train_df[["fight_url", "event_date_parsed"]]
        .drop_duplicates()
        .sort_values("event_date_parsed")
        .reset_index(drop=True)
    )

    core_end = int(len(fight_dates) * (1.0 - CALIBRATION_TAIL_FRACTION))
    core_urls = set(fight_dates.iloc[:core_end]["fight_url"])

    core_df = train_df[train_df["fight_url"].isin(core_urls)].copy()
    calibration_df = train_df[~train_df["fight_url"].isin(core_urls)].copy()

    return core_df, calibration_df


def _elo_baseline_accuracy(test_df: pd.DataFrame) -> float | None:
    if "diff_prior_elo" not in test_df.columns:
        return None

    elo_diff = pd.to_numeric(test_df["diff_prior_elo"], errors="coerce")
    predicted = (elo_diff > 0).astype(int)
    target = test_df["target"].astype(int)

    scorable = elo_diff.notna()
    if scorable.sum() == 0:
        return None

    return float((predicted[scorable] == target[scorable]).mean())


def _fit_fold_model(
    base_model_name: str,
    calibration_method: str,
    numeric_features: list[str],
    categorical_features: list[str],
    train_df: pd.DataFrame,
    feature_columns: list[str],
):
    base_models = build_base_models(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    if base_model_name not in base_models:
        base_model_name = "logistic_regression"

    model = base_models[base_model_name]

    if calibration_method in {"sigmoid", "isotonic"}:
        core_df, calibration_df = _chronological_calibration_split(train_df)

        # Guard against a calibration slice too small to be useful.
        if len(calibration_df) >= 100:
            model.fit(core_df[feature_columns], core_df["target"])
            calibrated = make_calibrated_model(model, method=calibration_method)
            calibrated.fit(
                calibration_df[feature_columns],
                calibration_df["target"],
            )
            return calibrated, base_model_name, calibration_method

    model.fit(train_df[feature_columns], train_df["target"])
    return model, base_model_name, "none"


def _summarize(values: list[float | None]) -> dict[str, Any]:
    clean = [float(v) for v in values if v is not None and np.isfinite(v)]

    if not clean:
        return {"mean": None, "std": None, "ci95": None, "n": 0}

    array = np.array(clean, dtype=float)
    mean = float(array.mean())
    std = float(array.std(ddof=1)) if len(array) > 1 else 0.0
    ci95 = float(1.96 * std / np.sqrt(len(array))) if len(array) > 1 else 0.0

    return {"mean": mean, "std": std, "ci95": ci95, "n": len(array)}


def _drift_summary(folds: list[dict[str, Any]]) -> dict[str, Any]:
    if len(folds) < 3:
        return {
            "status": "insufficient",
            "label": "Not enough folds",
            "message": "At least three yearly folds are required for the drift check.",
        }

    latest = folds[-1]
    prior_values = [float(row["accuracy"]) for row in folds[:-1]]
    prior_mean = float(np.mean(prior_values))
    delta = float(latest["accuracy"] - prior_mean)
    latest_elo_edge = latest.get("model_minus_elo_accuracy")
    prior_elo_edges = [
        float(row["model_minus_elo_accuracy"])
        for row in folds[:-1]
        if row.get("model_minus_elo_accuracy") is not None
    ]
    prior_elo_edge_mean = (
        float(np.mean(prior_elo_edges)) if prior_elo_edges else None
    )
    elo_edge_delta = (
        float(latest_elo_edge - prior_elo_edge_mean)
        if latest_elo_edge is not None and prior_elo_edge_mean is not None
        else None
    )
    accuracy_watch = delta <= -0.03
    relative_watch = elo_edge_delta is not None and elo_edge_delta <= -0.03
    status = "watch" if accuracy_watch or relative_watch else "stable"
    reasons = []
    if accuracy_watch:
        reasons.append("absolute accuracy")
    if relative_watch:
        reasons.append("the advantage over Elo")
    return {
        "status": status,
        "label": "Drift watch" if status == "watch" else "No material performance drift",
        "latest_year": int(latest["test_year"]),
        "latest_accuracy": float(latest["accuracy"]),
        "prior_fold_mean_accuracy": prior_mean,
        "delta": delta,
        "latest_model_minus_elo_accuracy": latest_elo_edge,
        "prior_model_minus_elo_mean": prior_elo_edge_mean,
        "model_minus_elo_delta": elo_edge_delta,
        "threshold": -0.03,
        "message": (
            "The newest fold is at least 3 percentage points lower in "
            + " and ".join(reasons)
            + " than the mean of prior folds."
            if status == "watch"
            else "The newest fold is within 3 percentage points of prior-fold accuracy and relative Elo edge."
        ),
    }


def run_walk_forward_evaluation(
    n_folds: int = DEFAULT_N_FOLDS,
    min_test_fights: int = DEFAULT_MIN_TEST_FIGHTS,
    min_train_fights: int = DEFAULT_MIN_TRAIN_FIGHTS,
    drop_feature_columns: tuple[str, ...] = (),
) -> dict[str, Any]:
    """
    drop_feature_columns lets you ablate a feature group (e.g. strength-of-schedule)
    so its marginal contribution can be measured on identical folds.
    """
    n_folds = max(2, min(int(n_folds), 20))
    drop_set = set(drop_feature_columns)

    cache_key = (
        n_folds,
        int(min_test_fights),
        int(min_train_fights),
        tuple(sorted(drop_set)),
        resolve_production_model_spec(),
        TRAINING_MATCHUPS_CSV.stat().st_mtime if TRAINING_MATCHUPS_CSV.exists() else 0,
    )
    if cache_key in _RESULT_CACHE:
        return _RESULT_CACHE[cache_key]

    df = _load_matchups()

    numeric_features, categorical_features = get_feature_columns(df)

    if drop_set:
        numeric_features = [c for c in numeric_features if c not in drop_set]
        categorical_features = [c for c in categorical_features if c not in drop_set]

    feature_columns = numeric_features + categorical_features

    base_model_name, calibration_method = resolve_production_model_spec()

    fold_plan = build_fold_plan(
        df=df,
        n_folds=n_folds,
        min_test_fights=min_test_fights,
        min_train_fights=min_train_fights,
    )

    fold_rows: list[dict[str, Any]] = []
    resolved_calibration = calibration_method

    for fold in fold_plan:
        test_year = fold["test_year"]

        train_df = df[df["year"] < test_year].copy()
        test_df = df[df["year"] == test_year].copy()

        if train_df.empty or test_df.empty:
            continue

        model, used_base_name, used_calibration = _fit_fold_model(
            base_model_name=base_model_name,
            calibration_method=calibration_method,
            numeric_features=numeric_features,
            categorical_features=categorical_features,
            train_df=train_df,
            feature_columns=feature_columns,
        )
        resolved_calibration = used_calibration

        metrics = evaluate_model(
            model,
            test_df[feature_columns],
            test_df["target"],
        )

        elo_accuracy = _elo_baseline_accuracy(test_df)
        model_vs_elo = (
            metrics["accuracy"] - elo_accuracy if elo_accuracy is not None else None
        )

        fold_rows.append(
            {
                "test_year": test_year,
                "train_fights": int(train_df["fight_url"].nunique()),
                "test_fights": int(test_df["fight_url"].nunique()),
                "test_rows": int(len(test_df)),
                "accuracy": metrics["accuracy"],
                "brier_score": metrics["brier_score"],
                "log_loss": metrics["log_loss"],
                "roc_auc": metrics["roc_auc"],
                "elo_baseline_accuracy": elo_accuracy,
                "model_minus_elo_accuracy": model_vs_elo,
            }
        )

    aggregate = {
        "accuracy": _summarize([row["accuracy"] for row in fold_rows]),
        "brier_score": _summarize([row["brier_score"] for row in fold_rows]),
        "log_loss": _summarize([row["log_loss"] for row in fold_rows]),
        "roc_auc": _summarize([row["roc_auc"] for row in fold_rows]),
        "elo_baseline_accuracy": _summarize(
            [row["elo_baseline_accuracy"] for row in fold_rows]
        ),
        "model_minus_elo_accuracy": _summarize(
            [row["model_minus_elo_accuracy"] for row in fold_rows]
        ),
    }

    result = {
        "available": len(fold_rows) > 0,
        "message": (
            ""
            if fold_rows
            else "Not enough history to build walk-forward folds yet."
        ),
        "metadata": {
            "model_type": used_base_name if fold_rows else base_model_name,
            "calibration_method": resolved_calibration,
            "n_folds": len(fold_rows),
            "requested_folds": n_folds,
            "min_test_fights": int(min_test_fights),
            "min_train_fights": int(min_train_fights),
            "feature_count": len(feature_columns),
            "metric_note": (
                "Each fold trains a fresh model on every fight before that test year, "
                "then scores that year out-of-sample. Metrics are row-level over the "
                "mirrored matchup rows, consistent with training. Elo baseline picks the "
                "higher pre-fight Elo."
            ),
        },
        "aggregate": aggregate,
        "folds": fold_rows,
        "drift": _drift_summary(fold_rows),
        "evidence": {
            "level": "established" if len(fold_rows) >= 5 else "moderate",
            "label": (
                "Established walk-forward evidence"
                if len(fold_rows) >= 5
                else "Moderate walk-forward evidence"
            ),
            "message": "Every fold is trained only on fights before its test year.",
        },
    }

    _RESULT_CACHE[cache_key] = result
    return result


def clear_walk_forward_cache() -> None:
    _RESULT_CACHE.clear()


def write_walk_forward_evaluation_artifact(
    artifact_path: Path = WALK_FORWARD_ARTIFACT_PATH,
) -> dict[str, Any]:
    clear_walk_forward_cache()
    payload = run_walk_forward_evaluation()
    payload.setdefault("metadata", {})["artifact_file"] = (
        "models/walk_forward_evaluation.json"
    )
    payload["metadata"]["artifact_role"] = "frozen_expanding_window_backtest"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def get_walk_forward_evaluation() -> dict[str, Any]:
    if WALK_FORWARD_ARTIFACT_PATH.exists():
        try:
            return json.loads(WALK_FORWARD_ARTIFACT_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    if TRAINING_MATCHUPS_CSV.exists():
        return run_walk_forward_evaluation()

    return {
        "available": False,
        "message": (
            "The frozen walk-forward artifact is missing. Run the local training "
            "pipeline and deploy the generated model JSON artifacts."
        ),
        "metadata": {"artifact_file": "models/walk_forward_evaluation.json"},
        "aggregate": {},
        "folds": [],
    }
