from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.services.model_market_evaluation_service import add_actual_result_columns


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"

SAVED_CARD_PREDICTIONS_CSV = PROCESSED_DATA_DIR / "saved_card_predictions.csv"
MARKET_SHADOW_MODELS_DIR = MODELS_DIR / "market_shadow_models"
MARKET_SHADOW_REGISTRY_PATH = MODELS_DIR / "market_shadow_model_registry.json"
MARKET_SHADOW_METRICS_PATH = MODELS_DIR / "market_shadow_model_metrics.json"

RANDOM_STATE = 42

MARKET_ONLY_NUMERIC_FEATURES = [
    "market_fighter_1_probability",
    "market_fighter_2_probability",
    "market_confidence",
    "market_favorite_is_fighter_1",
]

MODEL_MARKET_NUMERIC_FEATURES = [
    "market_fighter_1_probability",
    "market_fighter_2_probability",
    "market_confidence",
    "market_favorite_is_fighter_1",
    "model_fighter_1_probability",
    "model_fighter_2_probability",
    "model_confidence",
    "model_favorite_is_fighter_1",
    "model_market_agree",
    "model_market_probability_delta",
    "model_confidence_delta",
]

CATEGORICAL_FEATURES = ["weight_class"]

MODEL_SPECS = [
    {
        "model_name": "shadow_market_logistic_regression",
        "description": "Market-only logistic regression trained from saved pre-event odds snapshots.",
        "numeric_features": MARKET_ONLY_NUMERIC_FEATURES,
        "calibration_method": "none",
        "minimum_rows": 12,
    },
    {
        "model_name": "shadow_model_market_logistic_regression",
        "description": "Logistic regression trained from the app probability plus saved market odds.",
        "numeric_features": MODEL_MARKET_NUMERIC_FEATURES,
        "calibration_method": "none",
        "minimum_rows": 12,
    },
    {
        "model_name": "shadow_model_market_calibrated_logistic_regression",
        "description": "Platt/sigmoid-calibrated logistic regression trained from model plus market features.",
        "numeric_features": MODEL_MARKET_NUMERIC_FEATURES,
        "calibration_method": "sigmoid",
        "minimum_rows": 24,
    },
    {
        "model_name": "shadow_model_market_isotonic_logistic_regression",
        "description": "Isotonic-calibrated logistic regression trained from model plus market features.",
        "numeric_features": MODEL_MARKET_NUMERIC_FEATURES,
        "calibration_method": "isotonic",
        "minimum_rows": 24,
    },
]


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def normalize_name(value: Any) -> str:
    return clean_text(value).lower()


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if value is None or pd.isna(value):
        return False

    return clean_text(value).lower() in {"true", "1", "yes", "y"}


def optional_probability(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    if number > 1.0:
        number = number / 100.0

    return float(min(max(number, 0.0), 1.0))


def normalize_probability_pair(
    first_probability: Any,
    second_probability: Any,
) -> tuple[float | None, float | None]:
    first = optional_probability(first_probability)
    second = optional_probability(second_probability)

    if first is None and second is None:
        return None, None

    if first is None and second is not None:
        first = 1.0 - second

    if second is None and first is not None:
        second = 1.0 - first

    if first is None or second is None:
        return None, None

    total = first + second

    if total <= 0:
        return 0.5, 0.5

    return first / total, second / total


def read_saved_card_predictions() -> pd.DataFrame:
    if not SAVED_CARD_PREDICTIONS_CSV.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(SAVED_CARD_PREDICTIONS_CSV)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def build_target(row: pd.Series) -> int | None:
    actual_winner = normalize_name(row.get("actual_winner", ""))
    fighter_1 = normalize_name(row.get("fighter_1", ""))
    fighter_2 = normalize_name(row.get("fighter_2", ""))

    if not actual_winner:
        return None

    if actual_winner == fighter_1:
        return 1

    if actual_winner == fighter_2:
        return 0

    return None


def build_market_training_frame() -> pd.DataFrame:
    saved_df = read_saved_card_predictions()

    if saved_df.empty:
        return pd.DataFrame()

    df = add_actual_result_columns(saved_df)

    for column in [
        "prediction_available",
        "odds_available",
        "fighter_1_probability",
        "fighter_2_probability",
        "confidence",
        "fighter_1_market_probability",
        "fighter_2_market_probability",
        "market_favorite",
        "actual_winner",
        "fighter_1",
        "fighter_2",
        "weight_class",
        "event_date",
        "saved_at",
        "fight_url",
    ]:
        if column not in df.columns:
            df[column] = None

    df = df[df["prediction_available"].apply(parse_bool)].copy()
    df = df[df["odds_available"].apply(parse_bool)].copy()

    if df.empty:
        return df

    market_probabilities = df.apply(
        lambda row: normalize_probability_pair(
            row.get("fighter_1_market_probability"),
            row.get("fighter_2_market_probability"),
        ),
        axis=1,
        result_type="expand",
    )
    df["market_fighter_1_probability"] = market_probabilities[0]
    df["market_fighter_2_probability"] = market_probabilities[1]

    model_probabilities = df.apply(
        lambda row: normalize_probability_pair(
            row.get("fighter_1_probability"),
            row.get("fighter_2_probability"),
        ),
        axis=1,
        result_type="expand",
    )
    df["model_fighter_1_probability"] = model_probabilities[0]
    df["model_fighter_2_probability"] = model_probabilities[1]

    df["target"] = df.apply(build_target, axis=1)

    df = df[
        df["target"].notna()
        & df["market_fighter_1_probability"].notna()
        & df["market_fighter_2_probability"].notna()
    ].copy()

    if df.empty:
        return df

    df["target"] = df["target"].astype(int)
    df["weight_class"] = df["weight_class"].apply(clean_text)
    df["event_date_parsed"] = pd.to_datetime(df["event_date"], errors="coerce")
    df["saved_at_parsed"] = pd.to_datetime(df["saved_at"], errors="coerce")

    df["market_confidence"] = df[
        ["market_fighter_1_probability", "market_fighter_2_probability"]
    ].max(axis=1)

    market_favorite_norm = df["market_favorite"].apply(normalize_name)
    fighter_1_norm = df["fighter_1"].apply(normalize_name)
    df["market_favorite_is_fighter_1"] = (
        market_favorite_norm.eq(fighter_1_norm)
        | (
            market_favorite_norm.eq("")
            & df["market_fighter_1_probability"].ge(df["market_fighter_2_probability"])
        )
    ).astype(int)

    df["model_confidence"] = df["confidence"].apply(optional_probability)
    missing_model_confidence = df["model_confidence"].isna()
    df.loc[missing_model_confidence, "model_confidence"] = df.loc[
        missing_model_confidence,
        ["model_fighter_1_probability", "model_fighter_2_probability"],
    ].max(axis=1)

    df["model_favorite_is_fighter_1"] = (
        df["model_fighter_1_probability"].ge(df["model_fighter_2_probability"])
    ).astype("Int64")
    df["model_market_agree"] = (
        df["model_favorite_is_fighter_1"].eq(df["market_favorite_is_fighter_1"])
    ).astype("Int64")
    df["model_market_probability_delta"] = (
        df["model_fighter_1_probability"] - df["market_fighter_1_probability"]
    )
    df["model_confidence_delta"] = df["model_confidence"] - df["market_confidence"]

    df["fight_url_norm"] = df["fight_url"].apply(clean_text).str.rstrip("/")
    df = df.sort_values(
        ["event_date_parsed", "saved_at_parsed"],
        na_position="first",
    ).drop_duplicates("fight_url_norm", keep="last")

    return df.reset_index(drop=True)


def build_preprocessor(
    numeric_features: list[str],
    categorical_features: list[str],
) -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, numeric_features),
            ("categorical", categorical_pipeline, categorical_features),
        ]
    )


def build_logistic_pipeline(
    numeric_features: list[str],
    categorical_features: list[str],
) -> Pipeline:
    return Pipeline(
        steps=[
            (
                "preprocessor",
                build_preprocessor(
                    numeric_features=numeric_features,
                    categorical_features=categorical_features,
                ),
            ),
            (
                "model",
                LogisticRegression(
                    max_iter=3000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def make_calibrated_model(
    fitted_model: Pipeline,
    method: str,
    cv_folds: int | None = None,
) -> CalibratedClassifierCV:
    try:
        from sklearn.frozen import FrozenEstimator

        return CalibratedClassifierCV(
            estimator=FrozenEstimator(fitted_model),
            method=method,
            cv=cv_folds,
        )

    except ImportError:
        try:
            return CalibratedClassifierCV(
                estimator=fitted_model,
                method=method,
                cv="prefit",
            )
        except TypeError:
            return CalibratedClassifierCV(
                base_estimator=fitted_model,
                method=method,
                cv="prefit",
            )


def has_two_classes(df: pd.DataFrame) -> bool:
    return int(df["target"].nunique()) >= 2


def filter_training_rows(
    df: pd.DataFrame,
    numeric_features: list[str],
) -> pd.DataFrame:
    required_columns = [*numeric_features, "weight_class", "target"]
    model_df = df.dropna(subset=required_columns).copy()
    return model_df.reset_index(drop=True)


def split_chronological_holdout(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(df) < 20:
        return df.iloc[0:0].copy(), df.iloc[0:0].copy()

    sorted_df = df.sort_values(
        ["event_date_parsed", "saved_at_parsed"],
        na_position="first",
    ).reset_index(drop=True)

    test_rows = max(6, int(round(len(sorted_df) * 0.25)))

    if len(sorted_df) - test_rows < 12:
        return df.iloc[0:0].copy(), df.iloc[0:0].copy()

    return sorted_df.iloc[:-test_rows].copy(), sorted_df.iloc[-test_rows:].copy()


def split_stratified_calibration(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(df) < 16 or not has_two_classes(df):
        raise ValueError("Not enough rows/classes for calibration.")

    minimum_class_count = int(df["target"].value_counts().min())

    if minimum_class_count < 3:
        raise ValueError("Not enough examples per class for calibration.")

    calibration_fraction = min(0.35, max(0.20, 6 / len(df)))

    train_df, calibration_df = train_test_split(
        df,
        test_size=calibration_fraction,
        random_state=RANDOM_STATE,
        stratify=df["target"],
    )

    if not has_two_classes(train_df) or not has_two_classes(calibration_df):
        raise ValueError("Calibration split did not preserve both classes.")

    if int(calibration_df["target"].value_counts().min()) < 2:
        raise ValueError("Calibration split has fewer than two examples per class.")

    return train_df.copy(), calibration_df.copy()


def fit_model_from_spec(
    df: pd.DataFrame,
    numeric_features: list[str],
    calibration_method: str,
) -> Pipeline | CalibratedClassifierCV:
    if not has_two_classes(df):
        raise ValueError("Training data must contain both classes.")

    feature_columns = [*numeric_features, *CATEGORICAL_FEATURES]

    if calibration_method == "none":
        model = build_logistic_pipeline(
            numeric_features=numeric_features,
            categorical_features=CATEGORICAL_FEATURES,
        )
        model.fit(df[feature_columns], df["target"])
        return model

    train_df, calibration_df = split_stratified_calibration(df)

    base_model = build_logistic_pipeline(
        numeric_features=numeric_features,
        categorical_features=CATEGORICAL_FEATURES,
    )
    base_model.fit(train_df[feature_columns], train_df["target"])

    cv_folds = min(5, int(calibration_df["target"].value_counts().min()))

    calibrated_model = make_calibrated_model(
        fitted_model=base_model,
        method=calibration_method,
        cv_folds=cv_folds,
    )
    calibrated_model.fit(calibration_df[feature_columns], calibration_df["target"])

    return calibrated_model


def evaluate_probabilities(
    probabilities: list[float],
    targets: list[int],
) -> dict[str, Any]:
    if not probabilities or not targets:
        return {}

    clipped_probabilities = [
        float(min(max(probability, 1e-15), 1.0 - 1e-15))
        for probability in probabilities
    ]
    predictions = [1 if probability >= 0.50 else 0 for probability in probabilities]

    metrics: dict[str, Any] = {
        "accuracy": float(accuracy_score(targets, predictions)),
        "log_loss": float(log_loss(targets, clipped_probabilities, labels=[0, 1])),
        "brier_score": float(brier_score_loss(targets, probabilities)),
        "roc_auc": None,
    }

    if len(set(targets)) >= 2:
        metrics["roc_auc"] = float(roc_auc_score(targets, probabilities))

    return metrics


def evaluate_model(
    model,
    df: pd.DataFrame,
    feature_columns: list[str],
) -> dict[str, Any]:
    probabilities = model.predict_proba(df[feature_columns])[:, 1].tolist()
    targets = df["target"].astype(int).tolist()
    return evaluate_probabilities(probabilities=probabilities, targets=targets)


def build_validation_metrics(
    df: pd.DataFrame,
    numeric_features: list[str],
    calibration_method: str,
) -> dict[str, Any]:
    train_df, test_df = split_chronological_holdout(df)

    if train_df.empty or test_df.empty:
        return {
            "validation_status": "insufficient_holdout_data",
            "validation_rows": 0,
        }

    if not has_two_classes(train_df):
        return {
            "validation_status": "insufficient_holdout_classes",
            "validation_rows": int(len(test_df)),
        }

    try:
        model = fit_model_from_spec(
            df=train_df,
            numeric_features=numeric_features,
            calibration_method=calibration_method,
        )
    except ValueError as error:
        return {
            "validation_status": "skipped",
            "validation_rows": int(len(test_df)),
            "skip_reason": str(error),
        }

    feature_columns = [*numeric_features, *CATEGORICAL_FEATURES]
    metrics = evaluate_model(model=model, df=test_df, feature_columns=feature_columns)

    return {
        **metrics,
        "validation_status": "chronological_holdout",
        "validation_rows": int(len(test_df)),
        "validation_start_date": str(test_df["event_date_parsed"].min().date()),
        "validation_end_date": str(test_df["event_date_parsed"].max().date()),
    }


def build_class_balance(df: pd.DataFrame) -> dict[str, Any]:
    value_counts = df["target"].value_counts().to_dict()

    return {
        "fighter_1_wins": int(value_counts.get(1, 0)),
        "fighter_2_wins": int(value_counts.get(0, 0)),
        "fighter_1_win_rate": (
            float(value_counts.get(1, 0) / len(df))
            if len(df)
            else None
        ),
    }


def build_baseline_registry_entry(df: pd.DataFrame) -> dict[str, Any]:
    probabilities = df["market_fighter_1_probability"].astype(float).tolist()
    targets = df["target"].astype(int).tolist()

    return {
        "model_name": "shadow_market_implied_probability",
        "path": "",
        "is_best_model": False,
        "is_shadow_model": True,
        "model_type": "market_probability_baseline",
        "calibration_method": "market_implied",
        "feature_columns": MARKET_ONLY_NUMERIC_FEATURES + CATEGORICAL_FEATURES,
        "numeric_features": MARKET_ONLY_NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "description": "Untrained shadow baseline that uses saved market implied probabilities directly.",
        "metrics": {
            **evaluate_probabilities(probabilities=probabilities, targets=targets),
            "training_rows": int(len(df)),
            "validation_status": "all_scored_market_rows",
            **build_class_balance(df),
        },
    }


def train_and_save_spec(
    df: pd.DataFrame,
    spec: dict[str, Any],
) -> dict[str, Any] | None:
    model_name = clean_text(spec["model_name"])
    numeric_features = list(spec["numeric_features"])
    calibration_method = clean_text(spec["calibration_method"])
    minimum_rows = int(spec["minimum_rows"])

    model_df = filter_training_rows(df, numeric_features=numeric_features)

    if len(model_df) < minimum_rows:
        print(
            f"Skipping {model_name}: {len(model_df)} rows available, "
            f"{minimum_rows} required."
        )
        return None

    if not has_two_classes(model_df):
        print(f"Skipping {model_name}: only one target class is available.")
        return None

    validation_metrics = build_validation_metrics(
        df=model_df,
        numeric_features=numeric_features,
        calibration_method=calibration_method,
    )

    try:
        model = fit_model_from_spec(
            df=model_df,
            numeric_features=numeric_features,
            calibration_method=calibration_method,
        )
    except ValueError as error:
        print(f"Skipping {model_name}: {error}")
        return None

    model_path = MARKET_SHADOW_MODELS_DIR / f"{model_name}.joblib"
    joblib.dump(model, model_path)

    print(f"Saved {model_name} to {model_path}")

    return {
        "model_name": model_name,
        "path": str(model_path.relative_to(MODELS_DIR)),
        "is_best_model": False,
        "is_shadow_model": True,
        "model_type": "market_shadow_model",
        "calibration_method": calibration_method,
        "feature_columns": [*numeric_features, *CATEGORICAL_FEATURES],
        "numeric_features": numeric_features,
        "categorical_features": CATEGORICAL_FEATURES,
        "description": clean_text(spec["description"]),
        "metrics": {
            **validation_metrics,
            "training_rows": int(len(model_df)),
            **build_class_balance(model_df),
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def main() -> None:
    print("Loading saved pre-event predictions with market odds...")
    training_df = build_market_training_frame()

    MARKET_SHADOW_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    registry_models: dict[str, dict[str, Any]] = {}

    if training_df.empty:
        metrics_payload = {
            "available": False,
            "message": "No scored saved predictions with market odds are available yet.",
            "training_rows": 0,
            "models": {},
        }
        registry_payload = {
            "available": False,
            "models_dir": str(MARKET_SHADOW_MODELS_DIR),
            "models": {},
        }

        write_json(MARKET_SHADOW_METRICS_PATH, metrics_payload)
        write_json(MARKET_SHADOW_REGISTRY_PATH, registry_payload)
        print(metrics_payload["message"])
        return

    print(f"Market shadow training rows: {len(training_df)}")
    print(f"Unique fights: {training_df['fight_url_norm'].nunique()}")
    print(f"Class balance: {build_class_balance(training_df)}")

    registry_models["shadow_market_implied_probability"] = (
        build_baseline_registry_entry(training_df)
    )

    for spec in MODEL_SPECS:
        registry_entry = train_and_save_spec(training_df, spec)

        if registry_entry is not None:
            registry_models[registry_entry["model_name"]] = registry_entry

    metrics_payload = {
        "available": True,
        "source_file": str(SAVED_CARD_PREDICTIONS_CSV),
        "registry_path": str(MARKET_SHADOW_REGISTRY_PATH),
        "training_rows": int(len(training_df)),
        "unique_fights": int(training_df["fight_url_norm"].nunique()),
        "date_min": str(training_df["event_date_parsed"].min().date()),
        "date_max": str(training_df["event_date_parsed"].max().date()),
        "class_balance": build_class_balance(training_df),
        "model_names": sorted(registry_models.keys()),
        "models": {
            model_name: model_payload.get("metrics", {})
            for model_name, model_payload in sorted(registry_models.items())
        },
    }

    registry_payload = {
        "available": True,
        "models_dir": str(MARKET_SHADOW_MODELS_DIR),
        "metrics_path": str(MARKET_SHADOW_METRICS_PATH),
        "models": registry_models,
    }

    write_json(MARKET_SHADOW_METRICS_PATH, metrics_payload)
    write_json(MARKET_SHADOW_REGISTRY_PATH, registry_payload)

    print(f"Saved market shadow registry to: {MARKET_SHADOW_REGISTRY_PATH}")
    print(f"Saved market shadow metrics to: {MARKET_SHADOW_METRICS_PATH}")


if __name__ == "__main__":
    main()
