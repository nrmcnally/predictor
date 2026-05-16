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
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


try:
    from xgboost import XGBClassifier

    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"

TRAINING_MATCHUPS_CSV = PROCESSED_DATA_DIR / "training_matchups.csv"

BEST_MODEL_PATH = MODELS_DIR / "best_winner_model.joblib"
METRICS_PATH = MODELS_DIR / "baseline_model_metrics.json"
FEATURES_PATH = MODELS_DIR / "model_features.json"


RANDOM_STATE = 42
TEST_SIZE = 0.20


def load_training_matchups() -> pd.DataFrame:
    """
    Loads the model-ready matchup rows.

    Each fight appears twice:
        Fighter A perspective
        Fighter B perspective
    """
    if not TRAINING_MATCHUPS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {TRAINING_MATCHUPS_CSV}. "
            "Run build_matchups.py first."
        )

    df = pd.read_csv(TRAINING_MATCHUPS_CSV)

    df["event_date_parsed"] = pd.to_datetime(df["event_date"], errors="coerce")

    df = df[df["event_date_parsed"].notna()].copy()

    return df


def get_feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """
    Selects the columns we allow the model to use.

    For this first model, we use:

    1. diff_* numeric columns
       Example:
           diff_prior_win_rate
           diff_avg_td_landed_per_15

    2. weight_class as a categorical feature

    We intentionally do NOT use:
        - fighter names
        - opponent names
        - current fight method
        - current fight result
        - current fight round/time
    """
    numeric_features = [
        column
        for column in df.columns
        if column.startswith("diff_")
        and pd.api.types.is_numeric_dtype(df[column])
    ]

    categorical_features = ["weight_class"]

    return numeric_features, categorical_features


def chronological_train_test_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Splits by fight, not by individual row.

    This is important because every fight appears twice:
        Fighter A vs Fighter B
        Fighter B vs Fighter A

    Both mirrored rows from the same fight must stay in the same split.
    Otherwise, the model could indirectly train on the same matchup it is tested on.
    """
    fight_dates = (
        df[["fight_url", "event_date_parsed"]]
        .drop_duplicates()
        .sort_values("event_date_parsed")
        .reset_index(drop=True)
    )

    number_of_fights = len(fight_dates)

    if number_of_fights < 10:
        raise ValueError("Not enough fights to create a train/test split.")

    split_index = int(number_of_fights * (1.0 - TEST_SIZE))

    train_fight_urls = set(fight_dates.iloc[:split_index]["fight_url"])
    test_fight_urls = set(fight_dates.iloc[split_index:]["fight_url"])

    train_df = df[df["fight_url"].isin(train_fight_urls)].copy()
    test_df = df[df["fight_url"].isin(test_fight_urls)].copy()

    return train_df, test_df


def build_preprocessor(
    numeric_features: list[str],
    categorical_features: list[str],
    scale_numeric: bool,
) -> ColumnTransformer:
    """
    Builds preprocessing for numeric and categorical features.

    Numeric columns:
        Missing values are filled with the median.

    Categorical columns:
        Missing values are filled with the most common value.
        Then one-hot encoding converts text categories into numeric columns.
    """
    if scale_numeric:
        numeric_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
    else:
        numeric_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
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


def build_models(
    numeric_features: list[str],
    categorical_features: list[str],
) -> dict[str, Pipeline]:
    """
    Creates the models we want to compare.
    """
    models: dict[str, Pipeline] = {}

    logistic_preprocessor = build_preprocessor(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        scale_numeric=True,
    )

    tree_preprocessor = build_preprocessor(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        scale_numeric=False,
    )

    models["logistic_regression"] = Pipeline(
        steps=[
            ("preprocessor", logistic_preprocessor),
            (
                "model",
                LogisticRegression(
                    max_iter=3000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )

    models["random_forest"] = Pipeline(
        steps=[
            ("preprocessor", tree_preprocessor),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=400,
                    max_depth=None,
                    min_samples_leaf=8,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    if XGBOOST_AVAILABLE:
        models["xgboost"] = Pipeline(
            steps=[
                ("preprocessor", tree_preprocessor),
                (
                    "model",
                    XGBClassifier(
                        n_estimators=500,
                        max_depth=3,
                        learning_rate=0.03,
                        subsample=0.90,
                        colsample_bytree=0.90,
                        objective="binary:logistic",
                        eval_metric="logloss",
                        random_state=RANDOM_STATE,
                        n_jobs=-1,
                    ),
                ),
            ]
        )
    else:
        print("XGBoost is not installed. Skipping XGBoost model.")

    return models


def evaluate_model(model: Pipeline, X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, float]:
    """
    Evaluates a model on the test set.

    accuracy:
        How often the winner pick is correct.

    log_loss:
        Penalizes confident wrong predictions.

    brier_score:
        Measures probability quality.
        Lower is better.

    roc_auc:
        Measures how well the model ranks winners above losers.
    """
    predicted_labels = model.predict(X_test)
    predicted_probabilities = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y_test, predicted_labels)),
        "log_loss": float(log_loss(y_test, predicted_probabilities)),
        "brier_score": float(brier_score_loss(y_test, predicted_probabilities)),
        "roc_auc": float(roc_auc_score(y_test, predicted_probabilities)),
    }

    return metrics


def print_metrics_table(results: dict[str, dict[str, float]]) -> None:
    print()
    print("Model comparison:")
    print("-" * 72)
    print(f"{'model':<24} {'accuracy':>10} {'log_loss':>10} {'brier':>10} {'roc_auc':>10}")
    print("-" * 72)

    for model_name, metrics in results.items():
        print(
            f"{model_name:<24} "
            f"{metrics['accuracy']:>10.4f} "
            f"{metrics['log_loss']:>10.4f} "
            f"{metrics['brier_score']:>10.4f} "
            f"{metrics['roc_auc']:>10.4f}"
        )

    print("-" * 72)


def choose_best_model_name(results: dict[str, dict[str, float]]) -> str:
    """
    Chooses the model that is most useful for the actual web app.

    Since the app will output percentages, we care about probability quality,
    not only raw winner-pick accuracy.

    Priority:
        1. Lower Brier score
        2. Lower log loss
        3. Higher accuracy
        4. Higher ROC AUC
    """
    return sorted(
        results.keys(),
        key=lambda model_name: (
            results[model_name]["brier_score"],
            results[model_name]["log_loss"],
            -results[model_name]["accuracy"],
            -results[model_name]["roc_auc"],
        ),
    )[0]


def save_outputs(
    best_model_name: str,
    best_model: Pipeline,
    results: dict[str, dict[str, float]],
    numeric_features: list[str],
    categorical_features: list[str],
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> None:
    """
    Saves:
        1. The best trained model
        2. The metrics
        3. The feature list used by the model
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump(best_model, BEST_MODEL_PATH)

    metrics_payload: dict[str, Any] = {
        "best_model_name": best_model_name,
        "selection_priority": [
            "lowest_brier_score",
            "lowest_log_loss",
            "highest_accuracy",
            "highest_roc_auc",
        ],
        "results": results,
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "train_fights": int(train_df["fight_url"].nunique()),
        "test_fights": int(test_df["fight_url"].nunique()),
        "train_date_min": str(train_df["event_date_parsed"].min().date()),
        "train_date_max": str(train_df["event_date_parsed"].max().date()),
        "test_date_min": str(test_df["event_date_parsed"].min().date()),
        "test_date_max": str(test_df["event_date_parsed"].max().date()),
    }

    with open(METRICS_PATH, "w", encoding="utf-8") as file:
        json.dump(metrics_payload, file, indent=2)

    features_payload = {
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
    }

    with open(FEATURES_PATH, "w", encoding="utf-8") as file:
        json.dump(features_payload, file, indent=2)


def main() -> None:
    print("Loading training matchup rows...")
    df = load_training_matchups()

    numeric_features, categorical_features = get_feature_columns(df)

    print(f"Loaded {len(df)} matchup rows.")
    print(f"Unique fights: {df['fight_url'].nunique()}")
    print(f"Numeric features: {len(numeric_features)}")
    print(f"Categorical features: {categorical_features}")

    train_df, test_df = chronological_train_test_split(df)

    print()
    print("Chronological split:")
    print(
        f"Train: {len(train_df)} rows, "
        f"{train_df['fight_url'].nunique()} fights, "
        f"{train_df['event_date_parsed'].min().date()} to "
        f"{train_df['event_date_parsed'].max().date()}"
    )
    print(
        f"Test:  {len(test_df)} rows, "
        f"{test_df['fight_url'].nunique()} fights, "
        f"{test_df['event_date_parsed'].min().date()} to "
        f"{test_df['event_date_parsed'].max().date()}"
    )

    feature_columns = numeric_features + categorical_features

    X_train = train_df[feature_columns]
    y_train = train_df["target"]

    X_test = test_df[feature_columns]
    y_test = test_df["target"]

    models = build_models(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    results: dict[str, dict[str, float]] = {}
    fitted_models: dict[str, Pipeline] = {}

    for model_name, model in models.items():
        print()
        print(f"Training {model_name}...")

        model.fit(X_train, y_train)

        metrics = evaluate_model(model, X_test, y_test)

        results[model_name] = metrics
        fitted_models[model_name] = model

        print(
            f"{model_name} "
            f"accuracy={metrics['accuracy']:.4f}, "
            f"log_loss={metrics['log_loss']:.4f}, "
            f"brier={metrics['brier_score']:.4f}, "
            f"roc_auc={metrics['roc_auc']:.4f}"
        )

    print_metrics_table(results)

    best_model_name = choose_best_model_name(results)
    best_model = fitted_models[best_model_name]

    print()
    print(f"Best model for app predictions: {best_model_name}")

    save_outputs(
        best_model_name=best_model_name,
        best_model=best_model,
        results=results,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        train_df=train_df,
        test_df=test_df,
    )

    print()
    print(f"Saved best model to: {BEST_MODEL_PATH}")
    print(f"Saved metrics to: {METRICS_PATH}")
    print(f"Saved features to: {FEATURES_PATH}")


if __name__ == "__main__":
    main()