from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, top_k_accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"

METHOD_TRAINING_DATA_CSV = PROCESSED_DATA_DIR / "method_training_data.csv"

BROAD_MODEL_PATH = MODELS_DIR / "method_broad_model.joblib"
DETAILED_MODEL_PATH = MODELS_DIR / "method_detailed_model.joblib"
FEATURES_PATH = MODELS_DIR / "method_model_features.json"
METRICS_PATH = MODELS_DIR / "method_model_metrics.json"


RANDOM_STATE = 42
TEST_FRACTION = 0.20


EXCLUDED_FEATURE_COLUMNS = {
    "fight_url",
    "event_name",
    "event_date",
    "event_date_parsed",
    "fighter_a",
    "fighter_b",
    "winner",
    "loser",
    "method",
    "broad_method",
    "detailed_method",
}


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())

def format_date(value: Any) -> str:
    parsed_date = pd.to_datetime(value, errors="coerce")

    if pd.isna(parsed_date):
        return ""

    return parsed_date.strftime("%B %d, %Y")

def load_method_training_data() -> pd.DataFrame:
    if not METHOD_TRAINING_DATA_CSV.exists():
        raise FileNotFoundError(
            f"Missing {METHOD_TRAINING_DATA_CSV}. "
            "Run python -m app.features.build_method_training_data first."
        )

    df = pd.read_csv(METHOD_TRAINING_DATA_CSV)

    required_columns = [
        "fight_url",
        "event_date",
        "weight_class",
        "broad_method",
        "detailed_method",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "method_training_data.csv is missing required columns: "
            + ", ".join(missing_columns)
        )

    df["event_date_parsed"] = pd.to_datetime(df["event_date"], errors="coerce")
    df = df[df["event_date_parsed"].notna()].copy()

    df["broad_method"] = df["broad_method"].apply(clean_text)
    df["detailed_method"] = df["detailed_method"].apply(clean_text)

    df = df[
        df["broad_method"].ne("")
        & df["detailed_method"].ne("")
    ].copy()

    return df.sort_values("event_date_parsed").reset_index(drop=True)


def chronological_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    split_index = int(len(df) * (1.0 - TEST_FRACTION))

    train_df = df.iloc[:split_index].copy()
    test_df = df.iloc[split_index:].copy()

    return train_df, test_df


def infer_feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    categorical_features = []

    if "weight_class" in df.columns:
        categorical_features.append("weight_class")

    numeric_features = []

    for column in df.columns:
        if column in EXCLUDED_FEATURE_COLUMNS:
            continue

        if column in categorical_features:
            continue

        numeric_values = pd.to_numeric(df[column], errors="coerce")

        if numeric_values.notna().sum() > 0:
            numeric_features.append(column)

    return numeric_features, categorical_features


def build_preprocessor(
    numeric_features: list[str],
    categorical_features: list[str],
    scale_numeric: bool,
) -> ColumnTransformer:
    if scale_numeric:
        numeric_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
    else:
        numeric_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
            ]
        )

    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_transformer, numeric_features),
            ("categorical", categorical_transformer, categorical_features),
        ]
    )


def build_candidate_models(
    numeric_features: list[str],
    categorical_features: list[str],
) -> dict[str, Pipeline]:
    return {
        "logistic_regression": Pipeline(
            steps=[
                (
                    "preprocess",
                    build_preprocessor(
                        numeric_features=numeric_features,
                        categorical_features=categorical_features,
                        scale_numeric=True,
                    ),
                ),
                (
                    "classifier",
                    # No class_weight on purpose: balancing the classes flattens the
                    # base rates and makes the predicted probabilities dishonest
                    # (e.g. Decision shown ~35% when it actually happens ~51% of the
                    # time). The method panel reports probabilities, so it must reflect
                    # true frequencies. Verified: removing this cut broad log-loss
                    # 1.175 -> 1.004 and aligned predicted vs actual class rates.
                    LogisticRegression(
                        max_iter=4000,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
        "random_forest": Pipeline(
            steps=[
                (
                    "preprocess",
                    build_preprocessor(
                        numeric_features=numeric_features,
                        categorical_features=categorical_features,
                        scale_numeric=False,
                    ),
                ),
                (
                    "classifier",
                    # See the note on the logistic model: no class balancing, so the
                    # predicted probabilities stay faithful to real method base rates.
                    RandomForestClassifier(
                        n_estimators=500,
                        min_samples_leaf=5,
                        n_jobs=-1,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
    }


def safe_top_k_accuracy(
    y_true: pd.Series,
    probabilities,
    classes: list[str],
    k: int,
) -> float | None:
    if len(classes) <= 1:
        return None

    k = min(k, len(classes))

    try:
        return float(
            top_k_accuracy_score(
                y_true,
                probabilities,
                k=k,
                labels=classes,
            )
        )
    except Exception:
        return None


def evaluate_model(
    model: Pipeline,
    test_df: pd.DataFrame,
    target_column: str,
    feature_columns: list[str],
) -> dict[str, Any]:
    X_test = test_df[feature_columns].copy()
    y_test = test_df[target_column].copy()

    classes = list(model.named_steps["classifier"].classes_)

    # If a very rare class appears only in test and not in train, the model cannot
    # score it properly. This should be rare, but this filter prevents metric errors.
    scorable_mask = y_test.isin(classes)
    X_test = X_test[scorable_mask].copy()
    y_test = y_test[scorable_mask].copy()

    predictions = model.predict(X_test)
    probabilities = model.predict_proba(X_test)

    accuracy = accuracy_score(y_test, predictions)

    try:
        model_log_loss = log_loss(
            y_test,
            probabilities,
            labels=classes,
        )
    except Exception:
        model_log_loss = None

    top_2_accuracy = safe_top_k_accuracy(
        y_true=y_test,
        probabilities=probabilities,
        classes=classes,
        k=2,
    )

    top_3_accuracy = safe_top_k_accuracy(
        y_true=y_test,
        probabilities=probabilities,
        classes=classes,
        k=3,
    )

    return {
        "accuracy": float(accuracy),
        "log_loss": float(model_log_loss) if model_log_loss is not None else None,
        "top_2_accuracy": top_2_accuracy,
        "top_3_accuracy": top_3_accuracy,
        "scored_rows": int(len(y_test)),
        "classes": classes,
    }


def train_for_target(
    df: pd.DataFrame,
    target_column: str,
    numeric_features: list[str],
    categorical_features: list[str],
) -> dict[str, Any]:
    train_df, test_df = chronological_split(df)

    feature_columns = numeric_features + categorical_features

    X_train = train_df[feature_columns].copy()
    y_train = train_df[target_column].copy()

    candidate_models = build_candidate_models(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    results = {}
    fitted_models = {}

    print()
    print(f"Training method models for target: {target_column}")
    print("=" * 80)
    print(f"Train rows: {len(train_df)}")
    print(f"Test rows:  {len(test_df)}")
    print(f"Classes:    {sorted(y_train.unique().tolist())}")
    print()

    for model_name, model in candidate_models.items():
        print(f"Training {model_name}...")

        model.fit(X_train, y_train)

        metrics = evaluate_model(
            model=model,
            test_df=test_df,
            target_column=target_column,
            feature_columns=feature_columns,
        )

        results[model_name] = metrics
        fitted_models[model_name] = model

        print(
            f"{model_name}: "
            f"accuracy={metrics['accuracy']:.4f}, "
            f"log_loss={metrics['log_loss'] if metrics['log_loss'] is not None else 'N/A'}, "
            f"top_2={metrics['top_2_accuracy'] if metrics['top_2_accuracy'] is not None else 'N/A'}, "
            f"top_3={metrics['top_3_accuracy'] if metrics['top_3_accuracy'] is not None else 'N/A'}"
        )

    def selection_key(item: tuple[str, dict[str, Any]]) -> tuple[float, float]:
        _, metrics = item

        logloss = metrics["log_loss"]

        if logloss is None:
            logloss = 999.0

        # lowest log loss first, then highest accuracy
        return (float(logloss), -float(metrics["accuracy"]))

    best_model_name, best_metrics = sorted(results.items(), key=selection_key)[0]
    best_model = fitted_models[best_model_name]

    train_date_min = train_df["event_date_parsed"].min()
    train_date_max = train_df["event_date_parsed"].max()
    test_date_min = test_df["event_date_parsed"].min()
    test_date_max = test_df["event_date_parsed"].max()
    test_counts = test_df[target_column].value_counts()
    majority_class = str(test_counts.index[0]) if not test_counts.empty else ""
    majority_accuracy = (
        float(test_counts.iloc[0] / test_counts.sum()) if not test_counts.empty else None
    )
    accuracy_uplift = (
        float(best_metrics["accuracy"] - majority_accuracy)
        if majority_accuracy is not None
        else None
    )

    return {
        "target_column": target_column,
        "best_model_name": best_model_name,
        "best_model": best_model,
        "results": results,
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "train_date_min": format_date(train_date_min),
        "train_date_max": format_date(train_date_max),
        "test_date_min": format_date(test_date_min),
        "test_date_max": format_date(test_date_max),
        "best_metrics": best_metrics,
        "majority_baseline": {
            "class": majority_class,
            "accuracy": majority_accuracy,
            "model_accuracy_uplift": accuracy_uplift,
        },
        "evidence": {
            "level": "established" if len(test_df) >= 500 else "moderate",
            "label": (
                "Established historical sample"
                if len(test_df) >= 500
                else "Moderate historical sample"
            ),
            "message": "Chronological holdout; compare accuracy with the majority-class baseline.",
        },
    }


def save_outputs(
    broad_result: dict[str, Any],
    detailed_result: dict[str, Any],
    numeric_features: list[str],
    categorical_features: list[str],
) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump(broad_result["best_model"], BROAD_MODEL_PATH)
    joblib.dump(detailed_result["best_model"], DETAILED_MODEL_PATH)

    feature_payload = {
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "feature_columns": numeric_features + categorical_features,
        "broad_model_path": str(BROAD_MODEL_PATH),
        "detailed_model_path": str(DETAILED_MODEL_PATH),
        "broad_classes": list(
            broad_result["best_model"].named_steps["classifier"].classes_
        ),
        "detailed_classes": list(
            detailed_result["best_model"].named_steps["classifier"].classes_
        ),
    }

    with open(FEATURES_PATH, "w", encoding="utf-8") as file:
        json.dump(feature_payload, file, indent=2)

    metrics_payload = {
        "selection_priority": [
            "lowest_log_loss",
            "highest_accuracy",
        ],
        "broad": {
            key: value
            for key, value in broad_result.items()
            if key != "best_model"
        },
        "detailed": {
            key: value
            for key, value in detailed_result.items()
            if key != "best_model"
        },
    }

    with open(METRICS_PATH, "w", encoding="utf-8") as file:
        json.dump(metrics_payload, file, indent=2)


def print_summary(result: dict[str, Any]) -> None:
    print()
    print(f"Summary for {result['target_column']}")
    print("-" * 80)
    print(f"Best model: {result['best_model_name']}")
    print(f"Best metrics: {result['best_metrics']}")


def main() -> None:
    df = load_method_training_data()

    numeric_features, categorical_features = infer_feature_columns(df)

    print()
    print("Loaded method training data")
    print("=" * 80)
    print(f"Rows: {len(df)}")
    print(f"Numeric features: {len(numeric_features)}")
    print(f"Categorical features: {categorical_features}")
    print()

    broad_result = train_for_target(
        df=df,
        target_column="broad_method",
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    detailed_result = train_for_target(
        df=df,
        target_column="detailed_method",
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    save_outputs(
        broad_result=broad_result,
        detailed_result=detailed_result,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    print_summary(broad_result)
    print_summary(detailed_result)

    print()
    print("Saved method models")
    print("=" * 80)
    print(f"Broad model:    {BROAD_MODEL_PATH}")
    print(f"Detailed model: {DETAILED_MODEL_PATH}")
    print(f"Features:       {FEATURES_PATH}")
    print(f"Metrics:        {METRICS_PATH}")


if __name__ == "__main__":
    main()
