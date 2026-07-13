from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.features.duration_features import (
    add_interval_features,
    build_prediction_duration_features,
)
from app.services.prediction_service import (
    apply_prediction_weight_class_context,
    file_aware_cache,
    get_fighter_row,
    load_current_features,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DURATION_MODEL_PATH = PROJECT_ROOT / "models" / "duration_model.joblib"
EXPECTED_ARTIFACT_TYPE = "fightiq_duration_survival"
EXPECTED_MODEL_TYPE = "discrete_time_survival"


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _market_lines(scheduled_rounds: int, interval_rounds: float) -> list[float]:
    interval_count = int(round(scheduled_rounds / interval_rounds))
    interval_ends = [round((index + 1) * interval_rounds, 1) for index in range(interval_count)]
    return [
        line
        for line in interval_ends
        if line < scheduled_rounds and math.isclose(line % 1.0, 0.5, abs_tol=1e-9)
    ]


@file_aware_cache(lambda: [DURATION_MODEL_PATH])
def load_duration_artifact() -> dict[str, Any]:
    if not DURATION_MODEL_PATH.exists():
        raise FileNotFoundError(
            "Duration survival artifact is missing. Run "
            "`python -m app.models.train_duration_model` from `backend`."
        )

    artifact = joblib.load(DURATION_MODEL_PATH)
    if not isinstance(artifact, dict):
        raise ValueError("Duration artifact is not a versioned FightIQ payload.")
    if artifact.get("artifact_type") != EXPECTED_ARTIFACT_TYPE:
        raise ValueError("Duration artifact predates the survival-model contract; retrain it.")
    if artifact.get("model_type") != EXPECTED_MODEL_TYPE:
        raise ValueError("Duration artifact has an unsupported model type.")
    if artifact.get("market_inputs_used") is not False:
        raise ValueError("Duration artifact does not prove market-independent inference.")
    if artifact.get("market_line_role") != "query_only":
        raise ValueError("Duration artifact does not enforce query-only market lines.")
    if not artifact.get("pipeline"):
        raise ValueError("Duration artifact is missing its fitted survival pipeline.")
    return artifact


def survival_curve_from_hazards(
    interval_ends: list[float], hazards: list[float] | np.ndarray
) -> dict[float, float]:
    """Convert interval finish hazards into a monotonic P(T > line) curve."""
    if len(interval_ends) != len(hazards):
        raise ValueError("Interval and hazard lengths must match.")

    survival = 1.0
    curve: dict[float, float] = {}
    for interval_end, hazard in sorted(zip(interval_ends, hazards), key=lambda item: item[0]):
        hazard_value = float(np.clip(hazard, 0.0, 1.0))
        survival *= 1.0 - hazard_value
        curve[float(interval_end)] = float(np.clip(survival, 0.0, 1.0))
    return curve


def _unavailable(reason: str, message: str) -> dict[str, Any]:
    return {
        "available": False,
        "status": "unavailable",
        "unavailable_reason": reason,
        "message": message,
        "line": None,
        "over_probability": None,
        "under_probability": None,
        "curve": [],
        "market_inputs_used": False,
        "market_line_role": "query_only",
    }


def predict_duration_data(
    *,
    fighter_a: str,
    fighter_b: str,
    weight_class: str,
    fight_context: dict[str, Any] | None,
    market_line: Any = None,
) -> dict[str, Any]:
    """Predict a fight-duration survival curve, then query an optional market line.

    Only the numeric threshold is applied after the full curve is predicted. Market
    odds and the bookmaker's choice of line never enter the fitted feature matrix.
    """
    try:
        artifact = load_duration_artifact()
    except FileNotFoundError as error:
        return _unavailable("artifact_missing", str(error))
    except (OSError, ValueError) as error:
        return _unavailable("artifact_incompatible", str(error))

    context = dict(fight_context or {})
    scheduled_rounds_number = _finite_number(context.get("fight_context_scheduled_rounds"))
    scheduled_rounds = int(scheduled_rounds_number) if scheduled_rounds_number is not None else 0
    supported_schedules = {int(value) for value in artifact.get("supported_scheduled_rounds", [])}
    if scheduled_rounds not in supported_schedules:
        return _unavailable(
            "unsupported_scheduled_rounds",
            f"Duration model supports scheduled rounds {sorted(supported_schedules)}.",
        )

    features_df = load_current_features()
    fighter_a_row = apply_prediction_weight_class_context(
        get_fighter_row(features_df, fighter_a), weight_class
    )
    fighter_b_row = apply_prediction_weight_class_context(
        get_fighter_row(features_df, fighter_b), weight_class
    )
    base_features = build_prediction_duration_features(
        fighter_a_row,
        fighter_b_row,
        weight_class=weight_class,
        fight_context=context,
    )

    interval_rounds = float(artifact.get("interval_rounds", 0.5))
    interval_count = int(round(scheduled_rounds / interval_rounds))
    interval_ends = [
        round((index + 1) * interval_rounds, 1) for index in range(interval_count)
    ]
    prediction_rows = pd.DataFrame(
        [add_interval_features(base_features, interval_end) for interval_end in interval_ends]
    )
    numeric_features = list(artifact.get("numeric_features") or [])
    categorical_features = list(artifact.get("categorical_features") or [])
    required_features = numeric_features + categorical_features
    missing = [name for name in required_features if name not in prediction_rows.columns]
    if missing:
        return _unavailable(
            "feature_schema_mismatch",
            f"Duration prediction is missing features: {', '.join(missing)}.",
        )

    hazards = artifact["pipeline"].predict_proba(prediction_rows[required_features])[:, 1]
    internal_curve = survival_curve_from_hazards(interval_ends, hazards)
    supported_lines = _market_lines(scheduled_rounds, interval_rounds)
    curve = [
        {
            "line": line,
            "over_probability": internal_curve[line],
            "under_probability": 1.0 - internal_curve[line],
        }
        for line in supported_lines
    ]

    requested_line = _finite_number(market_line)
    exact = None
    if requested_line is not None:
        exact = next(
            (row for row in curve if math.isclose(row["line"], requested_line, abs_tol=1e-9)),
            None,
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "available": exact is not None,
        "status": "ready" if exact is not None else "curve_only",
        "unavailable_reason": (
            ""
            if exact is not None
            else "market_line_unavailable"
            if requested_line is None
            else "unsupported_market_line"
        ),
        "message": (
            "FightIQ survival curve queried at the exact market line."
            if exact is not None
            else "Duration curve is available, but there is no supported exact market line to query."
        ),
        "line": exact["line"] if exact else None,
        "rounds_line": exact["line"] if exact else None,
        "over_probability": exact["over_probability"] if exact else None,
        "under_probability": exact["under_probability"] if exact else None,
        "curve": curve,
        "scheduled_rounds": scheduled_rounds,
        "model_type": artifact.get("model_type"),
        "model_version": artifact.get("model_version", ""),
        "feature_schema_version": artifact.get("feature_schema_version", ""),
        "promotion_status": artifact.get("promotion_status", "experimental"),
        "model_trained_at": artifact.get("trained_at", ""),
        "generated_at": generated_at,
        "market_inputs_used": False,
        "market_line_role": "query_only",
        "monotonic_by_construction": True,
    }
    return payload
