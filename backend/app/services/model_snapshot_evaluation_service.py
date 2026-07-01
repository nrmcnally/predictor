from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from app.models.model_version import load_current_provenance
from app.repositories import event_fights_repository, saved_model_predictions_repository


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

EVENT_FIGHTS_CSV = RAW_DATA_DIR / "event_fights.csv"
SAVED_MODEL_PREDICTIONS_CSV = PROCESSED_DATA_DIR / "saved_model_predictions.csv"


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def normalize_name(value: Any) -> str:
    return clean_text(value).lower()


def normalize_fight_url(value: Any) -> str:
    normalized = clean_text(value)
    normalized = normalized.replace("https://www.", "https://")
    normalized = normalized.replace("http://www.", "http://")
    return normalized.rstrip("/")


def optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


from app.utils.bool_parsing import parse_bool  # noqa: E402


def read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def build_actual_result_lookup(event_fights_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if event_fights_df.empty or "fight_url" not in event_fights_df.columns:
        return {}

    lookup: dict[str, dict[str, Any]] = {}

    for _, row in event_fights_df.iterrows():
        fight_url = normalize_fight_url(row.get("fight_url", ""))
        winner = clean_text(row.get("winner", ""))
        loser = clean_text(row.get("loser", ""))

        if not fight_url or not winner:
            continue

        lookup[fight_url] = {
            "fight_url": fight_url,
            "actual_winner": winner,
            "actual_loser": loser,
            "actual_method": clean_text(row.get("method", "")),
            "actual_round": clean_text(row.get("round", "")),
            "actual_time": clean_text(row.get("time", "")),
            "actual_event_name": clean_text(row.get("event_name", "")),
            "actual_event_date": clean_text(row.get("event_date", "")),
        }

    return lookup


def score_prediction_row(row: pd.Series, actual_lookup: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if not parse_bool(row.get("prediction_available", False)):
        return None

    fight_url = normalize_fight_url(row.get("fight_url", ""))
    actual = actual_lookup.get(fight_url)

    if actual is None:
        return None

    fighter_1 = clean_text(row.get("fighter_1", ""))
    fighter_2 = clean_text(row.get("fighter_2", ""))
    actual_winner = clean_text(actual.get("actual_winner", ""))
    predicted_winner = clean_text(row.get("predicted_winner", ""))

    fighter_1_probability = optional_float(row.get("fighter_1_probability"))

    if fighter_1_probability is None:
        return None

    # Clamp only for log-loss safety. Do not alter the stored prediction itself.
    clipped_probability = min(max(fighter_1_probability, 1e-15), 1 - 1e-15)
    target = 1 if normalize_name(actual_winner) == normalize_name(fighter_1) else 0
    predicted_correct = normalize_name(predicted_winner) == normalize_name(actual_winner)

    brier = (fighter_1_probability - target) ** 2
    log_loss_value = -math.log(clipped_probability if target == 1 else 1 - clipped_probability)

    return {
        "saved_at": clean_text(row.get("saved_at", "")),
        "event_id": clean_text(row.get("event_id", "")),
        "event_name": clean_text(row.get("event_name", "")),
        "event_date": clean_text(row.get("event_date", "")),
        "fight_id": clean_text(row.get("fight_id", "")),
        "fight_url": fight_url,
        "fighter_1": fighter_1,
        "fighter_2": fighter_2,
        "weight_class": clean_text(row.get("weight_class", "")),
        "model_name": clean_text(row.get("model_name", "")),
        "is_best_model": parse_bool(row.get("is_best_model", False)),
        "predicted_winner": predicted_winner,
        "actual_winner": actual_winner,
        "prediction_correct": predicted_correct,
        "fighter_1_probability": fighter_1_probability,
        "fighter_2_probability": optional_float(row.get("fighter_2_probability")),
        "confidence": optional_float(row.get("confidence")),
        "brier_score": brier,
        "log_loss": log_loss_value,
        "market_favorite": clean_text(row.get("market_favorite", "")),
        "market_favorite_probability": optional_float(row.get("market_favorite_probability")),
    }


def percentage(value: float | None) -> str:
    if value is None:
        return "N/A"

    return f"{value * 100.0:.1f}%"


def average(values: list[float]) -> float | None:
    cleaned = [value for value in values if value is not None and math.isfinite(value)]
    if not cleaned:
        return None

    return float(sum(cleaned) / len(cleaned))


# Coarse buckets — the prospective (saved-prediction) sample is small, so fine
# buckets would just be noise.
PROSPECTIVE_CALIBRATION_BUCKETS = [(0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 1.01)]


def build_calibration_buckets(scored_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Reliability curve on the saved predictions: per confidence band, what the model
    *said* (avg confidence) vs what actually happened (hit rate). This is the truly
    out-of-sample, post-deployment calibration — the gold standard, but only
    meaningful once enough cards have completed.
    """
    buckets = []

    for lower, upper in PROSPECTIVE_CALIBRATION_BUCKETS:
        in_bucket = [
            row
            for row in scored_rows
            if row.get("confidence") is not None
            and lower <= float(row["confidence"]) < upper
        ]
        label = f"{int(lower * 100)}-{min(int(upper * 100), 100)}%"

        if not in_bucket:
            buckets.append(
                {
                    "bucket": label,
                    "count": 0,
                    "predicted": None,
                    "predicted_percentage": "N/A",
                    "actual": None,
                    "actual_percentage": "N/A",
                    "gap_percentage_points": "N/A",
                }
            )
            continue

        count = len(in_bucket)
        predicted = sum(float(row["confidence"]) for row in in_bucket) / count
        actual = sum(1 for row in in_bucket if row["prediction_correct"]) / count

        buckets.append(
            {
                "bucket": label,
                "count": count,
                "predicted": predicted,
                "predicted_percentage": percentage(predicted),
                "actual": actual,
                "actual_percentage": percentage(actual),
                "gap_percentage_points": f"{(actual - predicted) * 100.0:+.1f} pts",
            }
        )

    return buckets


def build_model_summary(scored_rows: list[dict[str, Any]]) -> dict[str, Any]:
    fight_count = len(scored_rows)
    correct_count = sum(1 for row in scored_rows if row["prediction_correct"])
    accuracy = correct_count / fight_count if fight_count else None
    avg_confidence = average([row.get("confidence") for row in scored_rows])
    avg_brier = average([row.get("brier_score") for row in scored_rows])
    avg_log_loss = average([row.get("log_loss") for row in scored_rows])

    return {
        "scored_fights": fight_count,
        "correct_predictions": correct_count,
        "wrong_predictions": fight_count - correct_count,
        "accuracy": accuracy,
        "accuracy_percentage": percentage(accuracy),
        "average_confidence": avg_confidence,
        "average_confidence_percentage": percentage(avg_confidence),
        "brier_score": avg_brier,
        "log_loss": avg_log_loss,
        "calibration_gap": None
        if accuracy is None or avg_confidence is None
        else accuracy - avg_confidence,
        "calibration_gap_percentage_points": "N/A"
        if accuracy is None or avg_confidence is None
        else f"{(accuracy - avg_confidence) * 100.0:+.1f} pts",
        "calibration_buckets": build_calibration_buckets(scored_rows),
    }


def build_prediction_model_summaries(predictions_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """
    Returns one row per model that has saved prospective predictions.

    This lets the Evaluation tab reserve space for every model currently being
    tracked, even before any of those saved predictions have completed results.
    """
    if predictions_df.empty or "model_name" not in predictions_df.columns:
        return {}

    working_df = predictions_df.copy()

    if "prediction_available" in working_df.columns:
        working_df = working_df[
            working_df["prediction_available"].apply(parse_bool)
        ].copy()

    working_df["model_name"] = working_df["model_name"].apply(clean_text)
    working_df = working_df[working_df["model_name"] != ""].copy()

    if working_df.empty:
        return {}

    current_model_type = clean_text(load_current_provenance().get("model_type", ""))
    summaries: dict[str, dict[str, Any]] = {}

    for model_name, model_df in working_df.groupby("model_name", sort=True):
        unique_fights = (
            int(model_df["fight_url"].apply(normalize_fight_url).nunique())
            if "fight_url" in model_df.columns
            else int(len(model_df))
        )

        was_snapshot_best_model = (
            bool(model_df["is_best_model"].apply(parse_bool).any())
            if "is_best_model" in model_df.columns
            else False
        )

        summaries[model_name] = {
            "model_name": model_name,
            "saved_prediction_rows": int(len(model_df)),
            "saved_unique_fights": unique_fights,
            "is_current_best_model": bool(
                current_model_type and model_name == current_model_type
            ),
            "was_snapshot_best_model": was_snapshot_best_model,
            "scored_fights": 0,
            "correct_predictions": 0,
            "wrong_predictions": 0,
            "accuracy": None,
            "accuracy_percentage": "N/A",
            "average_confidence": None,
            "average_confidence_percentage": "N/A",
            "brier_score": None,
            "log_loss": None,
            "calibration_gap": None,
            "calibration_gap_percentage_points": "N/A",
            "status": "waiting_for_results",
        }

    return summaries


def merge_scored_model_summary(
    prediction_summary: dict[str, Any],
    scored_summary: dict[str, Any],
) -> dict[str, Any]:
    merged = {**prediction_summary, **scored_summary}

    saved_unique_fights = optional_float(merged.get("saved_unique_fights"))
    scored_fights = optional_float(merged.get("scored_fights"))

    if saved_unique_fights is not None and scored_fights is not None:
        merged["pending_fights"] = max(0, int(saved_unique_fights - scored_fights))
    else:
        merged["pending_fights"] = None

    merged["status"] = "scored" if merged.get("scored_fights", 0) else "waiting_for_results"

    return merged


def build_model_snapshot_evaluation() -> dict[str, Any]:
    predictions_df = saved_model_predictions_repository.read_all_df()
    event_fights_df = event_fights_repository.read_all_df()

    if predictions_df.empty:
        return {
            "source_file": str(SAVED_MODEL_PREDICTIONS_CSV),
            "prediction_rows": 0,
            "scored_fights": 0,
            "unique_scored_fights": 0,
            "model_count": 0,
            "models": [],
            "recent_scored_fights": [],
            "message": "No saved all-model prediction snapshots were found.",
        }

    model_summaries = build_prediction_model_summaries(predictions_df)
    actual_lookup = build_actual_result_lookup(event_fights_df)
    scored_rows = []

    for _, row in predictions_df.iterrows():
        scored_row = score_prediction_row(row=row, actual_lookup=actual_lookup)
        if scored_row is not None:
            scored_rows.append(scored_row)

    if scored_rows:
        scored_df = pd.DataFrame(scored_rows)
        current_model_type = clean_text(load_current_provenance().get("model_type", ""))

        for model_name, model_df in scored_df.groupby("model_name", sort=True):
            clean_model_name = clean_text(model_name)
            was_snapshot_best_model = bool(model_df["is_best_model"].any())
            scored_summary = {
                "model_name": clean_model_name,
                "is_current_best_model": bool(
                    current_model_type and clean_model_name == current_model_type
                ),
                "was_snapshot_best_model": was_snapshot_best_model,
                **build_model_summary(model_df.to_dict("records")),
            }

            base_summary = model_summaries.get(
                clean_model_name,
                {
                    "model_name": clean_model_name,
                    "saved_prediction_rows": 0,
                    "saved_unique_fights": 0,
                    "is_current_best_model": False,
                    "was_snapshot_best_model": False,
                },
            )

            model_summaries[clean_model_name] = merge_scored_model_summary(
                prediction_summary=base_summary,
                scored_summary=scored_summary,
            )

        models = list(model_summaries.values())
        models = sorted(
            models,
            key=lambda row: (
                1 if row.get("scored_fights", 0) else 2,
                row["brier_score"] if row.get("brier_score") is not None else 999,
                row["log_loss"] if row.get("log_loss") is not None else 999,
                -(row.get("accuracy") or 0),
                clean_text(row.get("model_name", "")),
            ),
        )

        # Prospective calibration curve for the CURRENT production model (by recipe,
        # not the stale per-snapshot is_best_model flag, which reflects whatever was
        # best at save time).
        current_model_type = clean_text(load_current_provenance().get("model_type", ""))
        scored_models = [model for model in models if model.get("scored_fights")]
        calibration_model = (
            next(
                (m for m in scored_models if clean_text(m.get("model_name", "")) == current_model_type),
                None,
            )
            or next((m for m in scored_models if m.get("is_current_best_model")), None)
            or (scored_models[0] if scored_models else None)
        )

        return {
            "source_file": str(SAVED_MODEL_PREDICTIONS_CSV),
            "prediction_rows": int(len(predictions_df)),
            "scored_fights": int(len(scored_df)),
            "unique_scored_fights": int(scored_df["fight_url"].nunique())
            if "fight_url" in scored_df.columns
            else int(len(scored_df)),
            "model_count": len(models),
            "models": models,
            "prospective_calibration": calibration_model.get("calibration_buckets", [])
            if calibration_model
            else [],
            "prospective_calibration_model": calibration_model["model_name"]
            if calibration_model
            else "",
            "prospective_calibration_fights": calibration_model.get("scored_fights", 0)
            if calibration_model
            else 0,
            "recent_scored_fights": scored_df.sort_values("event_date", ascending=False)
            .head(25)
            .to_dict("records"),
        }

    models = sorted(
        model_summaries.values(),
        key=lambda row: clean_text(row.get("model_name", "")),
    )

    return {
        "source_file": str(SAVED_MODEL_PREDICTIONS_CSV),
        "prediction_rows": int(len(predictions_df)),
        "scored_fights": 0,
        "unique_scored_fights": 0,
        "model_count": len(models),
        "models": models,
        "recent_scored_fights": [],
        "message": "Saved all-model predictions exist, but no matching completed results were found yet.",
    }
