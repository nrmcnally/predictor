from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score

from app.repositories import event_fights_repository, saved_predictions_repository
from app.services.duration_settlement import settle_duration_result
from app.services.model_evaluation_service import evidence_status, wilson_interval


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DURATION_METRICS_PATH = PROJECT_ROOT / "models" / "duration_model_metrics.json"


def _fight_key(value: Any) -> str:
    """Canonical UFCStats fight identity shared by upcoming and result URLs.

    Upcoming-card pages omit ``www`` while completed-result pages include it, so
    the trailing ``fight-details`` identifier is the stable cross-table key.
    """
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip().rstrip("/").rsplit("/", 1)[-1].casefold()


def _finite_probability(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(probability) or probability < 0 or probability > 1:
        return None
    return probability


def _provided(value: Any) -> bool:
    if value is None or value == "":
        return False
    try:
        return not bool(pd.isna(value))
    except (TypeError, ValueError):
        return True


def _valid_prediction(row: pd.Series) -> tuple[float, float, float] | None:
    try:
        line = float(row.get("duration_line"))
        market_line = float(row.get("rounds_line"))
    except (TypeError, ValueError):
        return None
    over = _finite_probability(row.get("duration_over_probability"))
    under = _finite_probability(row.get("duration_under_probability"))
    if (
        not math.isfinite(line)
        or line <= 0
        or not math.isfinite(market_line)
        or not math.isclose(line, market_line, abs_tol=1e-9)
        or over is None
        or under is None
    ):
        return None
    if not math.isclose(over + under, 1.0, abs_tol=0.01):
        return None
    return line, over, under


def _enrich_metrics(metrics: dict[str, Any], *, prospective: bool = False) -> dict[str, Any]:
    enriched = dict(metrics or {})
    fight_count = int(enriched.get("fight_count") or 0)
    accuracy = enriched.get("accuracy")
    over_rate = enriched.get("actual_over_rate", enriched.get("over_rate"))
    if fight_count and accuracy is not None:
        correct_count = int(round(float(accuracy) * fight_count))
        lower, upper = wilson_interval(correct_count, fight_count)
        enriched["correct_count"] = correct_count
        enriched["accuracy_ci95_lower"] = lower
        enriched["accuracy_ci95_upper"] = upper
    if over_rate is not None:
        majority = max(float(over_rate), 1.0 - float(over_rate))
        enriched["majority_baseline_accuracy"] = majority
        if accuracy is not None:
            enriched["accuracy_above_majority"] = float(accuracy) - majority
    enriched["evidence"] = evidence_status(fight_count, prospective=prospective)
    return enriched


def _metric_payload(
    actual: list[int],
    probabilities: list[float],
    *,
    prospective: bool = False,
) -> dict[str, Any]:
    truth = np.asarray(actual, dtype=int)
    predicted_probabilities = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    predicted = (predicted_probabilities >= 0.5).astype(int)
    auc = (
        float(roc_auc_score(truth, predicted_probabilities))
        if len(np.unique(truth)) > 1
        else None
    )
    return _enrich_metrics({
        "fight_count": int(len(truth)),
        "accuracy": float(accuracy_score(truth, predicted)),
        "brier_score": float(brier_score_loss(truth, predicted_probabilities)),
        "log_loss": float(log_loss(truth, predicted_probabilities, labels=[0, 1])),
        "roc_auc": auc,
        "actual_over_rate": float(truth.mean()),
        "average_over_probability": float(predicted_probabilities.mean()),
        "predicted_over_rate": float(predicted.mean()),
    }, prospective=prospective)


def _historical_payload(metrics_path: Path) -> dict[str, Any]:
    if not metrics_path.exists():
        return {
            "available": False,
            "status": "not_trained",
            "message": (
                "No exact-line duration backtest artifact is installed. Run "
                "`python -m app.models.train_duration_model` from `backend`."
            ),
            "split": {"strategy": "chronological_80_20_unique_fights"},
        }

    try:
        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {
            "available": False,
            "status": "invalid_artifact",
            "message": f"Duration metrics artifact could not be read: {error}",
            "split": {"strategy": "chronological_80_20_unique_fights"},
        }

    required = {"model", "split", "metrics", "by_line", "recent_results"}
    missing = sorted(required - set(payload))
    if missing:
        return {
            "available": False,
            "status": "invalid_artifact",
            "message": f"Duration metrics artifact is missing: {', '.join(missing)}.",
            "split": payload.get("split") or {"strategy": "chronological_80_20_unique_fights"},
        }

    model = payload.get("model") or {}
    if model.get("type") != "discrete_time_survival":
        return {
            "available": False,
            "status": "stale_artifact",
            "message": (
                "The installed duration artifact uses the retired standard-line classifier. "
                "Retrain the discrete-time survival model before using these metrics."
            ),
            "split": payload.get("split") or {
                "strategy": "chronological_80_20_unique_fights_before_interval_expansion"
            },
        }

    payload["metrics"] = _enrich_metrics(payload.get("metrics") or {})
    payload["by_line"] = [
        _enrich_metrics(row or {}) for row in (payload.get("by_line") or [])
    ]
    return {"available": True, **payload}


def _prospective_payload(
    saved_predictions_df: pd.DataFrame,
    event_fights_df: pd.DataFrame,
) -> dict[str, Any]:
    duration_columns = {
        "duration_line",
        "duration_over_probability",
        "duration_under_probability",
    }
    if saved_predictions_df.empty or not duration_columns.issubset(saved_predictions_df.columns):
        return {
            "available": False,
            "status": "not_collecting",
            "message": "No frozen exact-line duration predictions have been saved yet.",
            "saved_predictions": 0,
            "scored_predictions": 0,
            "pending_predictions": 0,
            "invalid_predictions": 0,
            "future_card_results": [],
            "by_line": [],
        }

    result_lookup = {
        fight_key: row
        for _, row in event_fights_df.iterrows()
        if (fight_key := _fight_key(row.get("fight_url")))
    }

    saved_count = 0
    pending_count = 0
    invalid_count = 0
    excluded_count = 0
    actual: list[int] = []
    probabilities: list[float] = []
    result_rows: list[dict[str, Any]] = []

    for _, row in saved_predictions_df.iterrows():
        prediction = _valid_prediction(row)
        if prediction is None:
            if any(_provided(row.get(column)) for column in duration_columns):
                invalid_count += 1
            continue
        saved_count += 1
        line, over_probability, under_probability = prediction
        fight_url = str(row.get("fight_url") or "").strip()
        result = result_lookup.get(_fight_key(fight_url))
        if result is None:
            pending_count += 1
            continue

        settlement = settle_duration_result(
            result,
            line=line,
            scheduled_rounds=row.get("scheduled_rounds"),
        )
        if settlement["status"] != "settled":
            excluded_count += 1
            continue

        target_over = int(settlement["target_over"])
        predicted_side = "over" if over_probability >= under_probability else "under"
        actual_side = str(settlement["actual_side"])
        actual.append(target_over)
        probabilities.append(over_probability)
        result_rows.append(
            {
                "fight_url": fight_url,
                "event_name": str(row.get("event_name") or result.get("event_name") or ""),
                "event_date": str(row.get("event_date") or result.get("event_date") or ""),
                "fighter_1": str(row.get("fighter_1") or result.get("fighter_1") or ""),
                "fighter_2": str(row.get("fighter_2") or result.get("fighter_2") or ""),
                "line": line,
                "over_probability": over_probability,
                "under_probability": under_probability,
                "predicted_side": predicted_side,
                "predicted_probability": max(over_probability, under_probability),
                "actual_side": actual_side,
                "correct": predicted_side == actual_side,
                "model_version": str(row.get("duration_model_version") or ""),
                "saved_at": str(row.get("saved_at") or ""),
            }
        )

    result_rows.sort(key=lambda item: (item["event_date"], item["saved_at"]), reverse=True)
    by_line: list[dict[str, Any]] = []
    if result_rows:
        scored_frame = pd.DataFrame(result_rows)
        for line_value in sorted(scored_frame["line"].unique()):
            line_rows = scored_frame[scored_frame["line"] == line_value]
            line_actual = [1 if side == "over" else 0 for side in line_rows["actual_side"]]
            line_probabilities = [float(value) for value in line_rows["over_probability"]]
            metrics = _metric_payload(
                line_actual, line_probabilities, prospective=True
            )
            metrics["line"] = float(line_value)
            by_line.append(metrics)

    scored_count = len(actual)
    return {
        "available": scored_count > 0,
        "status": "ready" if scored_count > 0 else "collecting",
        "message": (
            "Scores frozen exact-line predictions saved before results arrived."
            if scored_count > 0
            else "Exact-line snapshots are collecting, but none have settled yet."
        ),
        "saved_predictions": saved_count,
        "scored_predictions": scored_count,
        "pending_predictions": pending_count,
        "invalid_predictions": invalid_count,
        "excluded_results": excluded_count,
        "metrics": (
            _metric_payload(actual, probabilities, prospective=True)
            if scored_count
            else None
        ),
        "by_line": by_line,
        "future_card_results": result_rows[:50],
    }


def build_duration_evaluation(
    *,
    metrics_path: Path = DURATION_METRICS_PATH,
    saved_predictions_df: pd.DataFrame | None = None,
    event_fights_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    historical = _historical_payload(metrics_path)
    saved = (
        saved_predictions_repository.read_all_df()
        if saved_predictions_df is None
        else saved_predictions_df
    )
    results = (
        event_fights_repository.read_all_df()
        if event_fights_df is None
        else event_fights_df
    )
    prospective = _prospective_payload(saved, results)

    totals_snapshots = 0
    if not saved.empty and "rounds_line" in saved.columns:
        totals_snapshots = int(pd.to_numeric(saved["rounds_line"], errors="coerce").notna().sum())

    return {
        "status": "ready" if historical.get("available") else "foundation",
        "semantic_contract": (
            "A market-independent survival curve is queried at the exact saved market line; "
            "P(Decision) is never substituted."
        ),
        "historical": historical,
        "prospective": prospective,
        "readiness": {
            "historical_backtest_available": bool(historical.get("available")),
            "future_duration_snapshots": int(prospective.get("saved_predictions", 0)),
            "settled_future_duration_predictions": int(
                prospective.get("scored_predictions", 0)
            ),
            "saved_totals_snapshots": totals_snapshots,
        },
    }
