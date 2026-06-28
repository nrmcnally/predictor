from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.services.prediction_service import (
    clean_text,
    file_aware_cache,
    get_fighter_row,
    load_current_features,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = PROJECT_ROOT / "models"

BROAD_MODEL_PATH = MODELS_DIR / "method_broad_model.joblib"
DETAILED_MODEL_PATH = MODELS_DIR / "method_detailed_model.joblib"
FEATURES_PATH = MODELS_DIR / "method_model_features.json"


def optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_percent(value: float) -> str:
    return f"{value * 100.0:.1f}%"


@file_aware_cache(lambda: [BROAD_MODEL_PATH, DETAILED_MODEL_PATH, FEATURES_PATH])
def load_method_models_and_features():
    if not BROAD_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Missing {BROAD_MODEL_PATH}. Run python -m app.models.train_method_models first."
        )

    if not DETAILED_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Missing {DETAILED_MODEL_PATH}. Run python -m app.models.train_method_models first."
        )

    if not FEATURES_PATH.exists():
        raise FileNotFoundError(
            f"Missing {FEATURES_PATH}. Run python -m app.models.train_method_models first."
        )

    broad_model = joblib.load(BROAD_MODEL_PATH)
    detailed_model = joblib.load(DETAILED_MODEL_PATH)

    with open(FEATURES_PATH, "r", encoding="utf-8") as file:
        feature_payload = json.load(file)

    feature_columns = feature_payload["feature_columns"]
    numeric_features = feature_payload["numeric_features"]
    categorical_features = feature_payload["categorical_features"]

    return broad_model, detailed_model, feature_columns, numeric_features, categorical_features


def clear_method_prediction_cache() -> None:
    load_method_models_and_features.cache_clear()


def get_row_value(row: pd.Series, column: str) -> float | None:
    return optional_float(row.get(column))


def build_method_feature_row(
    fighter_a_row: pd.Series,
    fighter_b_row: pd.Series,
    weight_class: str,
    feature_columns: list[str],
) -> pd.DataFrame:
    """
    Build one orientation-invariant feature row for method prediction.

    The method training dataset used:
      - abs_diff_<feature>
      - mean_<feature>
      - max_<feature>
      - min_<feature>
      - weight_class

    So here we recreate those same columns from current fighter features.
    """
    row: dict[str, Any] = {}

    for feature_column in feature_columns:
        if feature_column == "weight_class":
            row[feature_column] = weight_class
            continue

        if feature_column.startswith("abs_diff_"):
            base_column = feature_column.replace("abs_diff_", "", 1)

            fighter_a_value = get_row_value(fighter_a_row, base_column)
            fighter_b_value = get_row_value(fighter_b_row, base_column)

            if fighter_a_value is None or fighter_b_value is None:
                row[feature_column] = None
            else:
                row[feature_column] = abs(fighter_a_value - fighter_b_value)

            continue

        if feature_column.startswith("mean_"):
            base_column = feature_column.replace("mean_", "", 1)

            fighter_a_value = get_row_value(fighter_a_row, base_column)
            fighter_b_value = get_row_value(fighter_b_row, base_column)

            values = [
                value
                for value in [fighter_a_value, fighter_b_value]
                if value is not None
            ]

            row[feature_column] = sum(values) / len(values) if values else None
            continue

        if feature_column.startswith("max_"):
            base_column = feature_column.replace("max_", "", 1)

            fighter_a_value = get_row_value(fighter_a_row, base_column)
            fighter_b_value = get_row_value(fighter_b_row, base_column)

            values = [
                value
                for value in [fighter_a_value, fighter_b_value]
                if value is not None
            ]

            row[feature_column] = max(values) if values else None
            continue

        if feature_column.startswith("min_"):
            base_column = feature_column.replace("min_", "", 1)

            fighter_a_value = get_row_value(fighter_a_row, base_column)
            fighter_b_value = get_row_value(fighter_b_row, base_column)

            values = [
                value
                for value in [fighter_a_value, fighter_b_value]
                if value is not None
            ]

            row[feature_column] = min(values) if values else None
            continue

        # Defensive fallback. The model pipeline has imputers, so None is okay.
        row[feature_column] = None

    return pd.DataFrame([row], columns=feature_columns)


def probabilities_to_rows(model, probabilities) -> list[dict[str, Any]]:
    classes = list(model.named_steps["classifier"].classes_)

    rows = []

    for label, probability in zip(classes, probabilities):
        probability = float(probability)

        rows.append(
            {
                "label": clean_text(label),
                "probability": probability,
                "percentage": format_percent(probability),
            }
        )

    return sorted(
        rows,
        key=lambda row: row["probability"],
        reverse=True,
    )


def predict_method_data(
    fighter_a: str,
    fighter_b: str,
    weight_class: str,
) -> dict[str, Any]:
    features_df = load_current_features()

    fighter_a_row = get_fighter_row(features_df, fighter_a)
    fighter_b_row = get_fighter_row(features_df, fighter_b)

    fighter_a_clean = clean_text(fighter_a_row["fighter"])
    fighter_b_clean = clean_text(fighter_b_row["fighter"])

    (
        broad_model,
        detailed_model,
        feature_columns,
        numeric_features,
        categorical_features,
    ) = load_method_models_and_features()

    feature_row = build_method_feature_row(
        fighter_a_row=fighter_a_row,
        fighter_b_row=fighter_b_row,
        weight_class=weight_class,
        feature_columns=feature_columns,
    )

    broad_probabilities = broad_model.predict_proba(feature_row[feature_columns])[0]
    detailed_probabilities = detailed_model.predict_proba(feature_row[feature_columns])[0]

    broad_rows = probabilities_to_rows(
        model=broad_model,
        probabilities=broad_probabilities,
    )

    detailed_rows = probabilities_to_rows(
        model=detailed_model,
        probabilities=detailed_probabilities,
    )

    return {
        "fighter_a": fighter_a_clean,
        "fighter_b": fighter_b_clean,
        "weight_class": weight_class,
        "predicted_broad_method": broad_rows[0]["label"] if broad_rows else "",
        "predicted_broad_method_probability": broad_rows[0]["probability"]
        if broad_rows
        else None,
        "predicted_broad_method_percentage": broad_rows[0]["percentage"]
        if broad_rows
        else "",
        "predicted_detailed_method": detailed_rows[0]["label"] if detailed_rows else "",
        "predicted_detailed_method_probability": detailed_rows[0]["probability"]
        if detailed_rows
        else None,
        "predicted_detailed_method_percentage": detailed_rows[0]["percentage"]
        if detailed_rows
        else "",
        "broad_method_probabilities": broad_rows,
        "detailed_method_probabilities": detailed_rows,
        "model_note": (
            "Method prediction is separate from winner prediction. "
            "Detailed method probabilities should be treated as directional flavor, "
            "not a guaranteed exact finish prediction."
        ),
        "feature_count": {
            "total": len(feature_columns),
            "numeric": len(numeric_features),
            "categorical": len(categorical_features),
        },
    }