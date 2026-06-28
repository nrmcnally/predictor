from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
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

from app.features.fight_context_features import FIGHT_CONTEXT_NUMERIC_FEATURES
from app.models.model_version import build_provenance, compute_training_data_hash
from app.repositories import model_runs_repository


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
CALIBRATED_METRICS_PATH = MODELS_DIR / "calibrated_model_metrics.json"
FEATURES_PATH = MODELS_DIR / "model_features.json"
MODEL_REGISTRY_PATH = MODELS_DIR / "model_registry.json"
WINNER_MODELS_DIR = MODELS_DIR / "winner_models"

RANDOM_STATE = 42


def load_training_matchups() -> pd.DataFrame:
    if not TRAINING_MATCHUPS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {TRAINING_MATCHUPS_CSV}. Run build_matchups.py first."
        )

    df = pd.read_csv(TRAINING_MATCHUPS_CSV).copy()
    df["event_date_parsed"] = pd.to_datetime(df["event_date"], errors="coerce")
    df = df[df["event_date_parsed"].notna()].copy()

    # This removes the harmless fragmentation warning.
    return df.copy()


# Features that the data pipeline produces and keeps, but that are intentionally
# held OUT of the model. The cardio/fade features (round-derived) were validated on
# the walk-forward harness (2026-06-26) and did not help the production model
# (accuracy -0.14 pts, Brier/log-loss slightly worse, within noise). They are kept
# in the snapshots/matchups for future iteration (better metrics, or a tree model),
# but excluded here so they don't degrade the current model. Remove a name from this
# set to re-enable it for an experiment.
MODEL_EXCLUDED_FEATURE_COLUMNS = {
    "diff_prior_avg_cardio_sig_output_slope",
    "diff_prior_avg_cardio_late_round_share",
    "diff_prior_avg_cardio_rounds_logged",
    "diff_prior_cardio_fights",
}


def get_feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    numeric_features = [
        column
        for column in df.columns
        if (
            column.startswith("diff_")
            or column in FIGHT_CONTEXT_NUMERIC_FEATURES
        )
        and column not in MODEL_EXCLUDED_FEATURE_COLUMNS
        and pd.api.types.is_numeric_dtype(df[column])
    ]

    categorical_features = ["weight_class"]

    return numeric_features, categorical_features


def chronological_train_calibration_test_split(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Chronological split by fight.

    Oldest 70%: train
    Next 10%: calibration
    Newest 20%: final test

    We split by fight_url so mirrored rows stay together.
    """
    fight_dates = (
        df[["fight_url", "event_date_parsed"]]
        .drop_duplicates()
        .sort_values("event_date_parsed")
        .reset_index(drop=True)
    )

    number_of_fights = len(fight_dates)

    train_end = int(number_of_fights * 0.70)
    calibration_end = int(number_of_fights * 0.80)

    train_fight_urls = set(fight_dates.iloc[:train_end]["fight_url"])
    calibration_fight_urls = set(fight_dates.iloc[train_end:calibration_end]["fight_url"])
    test_fight_urls = set(fight_dates.iloc[calibration_end:]["fight_url"])

    train_df = df[df["fight_url"].isin(train_fight_urls)].copy()
    calibration_df = df[df["fight_url"].isin(calibration_fight_urls)].copy()
    test_df = df[df["fight_url"].isin(test_fight_urls)].copy()

    return train_df, calibration_df, test_df


def build_preprocessor(
    numeric_features: list[str],
    categorical_features: list[str],
    scale_numeric: bool,
) -> ColumnTransformer:
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


def build_base_models(
    numeric_features: list[str],
    categorical_features: list[str],
) -> dict[str, Pipeline]:
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
                    n_estimators=500,
                    max_depth=None,
                    min_samples_leaf=8,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    models["extra_trees"] = Pipeline(
        steps=[
            ("preprocessor", tree_preprocessor),
            (
                "model",
                ExtraTreesClassifier(
                    n_estimators=600,
                    max_depth=None,
                    min_samples_leaf=8,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    models["hist_gradient_boosting"] = Pipeline(
        steps=[
            ("preprocessor", tree_preprocessor),
            (
                "model",
                HistGradientBoostingClassifier(
                    max_iter=350,
                    learning_rate=0.035,
                    max_leaf_nodes=15,
                    min_samples_leaf=20,
                    l2_regularization=0.05,
                    random_state=RANDOM_STATE,
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
                        n_estimators=600,
                        max_depth=3,
                        learning_rate=0.025,
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

    return models


def make_calibrated_model(
    fitted_model: Pipeline,
    method: str = "sigmoid",
) -> CalibratedClassifierCV:
    """
    Builds a calibrated version of an already-fitted model.

    Newer scikit-learn versions removed cv="prefit".
    The replacement is FrozenEstimator.

    Older scikit-learn versions may not have FrozenEstimator,
    so we keep a fallback for cv="prefit".
    """
    try:
        from sklearn.frozen import FrozenEstimator

        return CalibratedClassifierCV(
            estimator=FrozenEstimator(fitted_model),
            method=method,
        )

    except ImportError:
        # Older scikit-learn fallback.
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


def evaluate_model(
    model,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, float]:
    probabilities = model.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= 0.50).astype(int)

    return {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "log_loss": float(log_loss(y_test, probabilities)),
        "brier_score": float(brier_score_loss(y_test, probabilities)),
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
    }


def build_confidence_bucket_report(
    model,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> list[dict[str, Any]]:
    probabilities = model.predict_proba(X_test)[:, 1]

    rows = []

    eval_df = pd.DataFrame(
        {
            "probability": probabilities,
            "target": y_test.values,
        }
    )

    eval_df["confidence"] = eval_df["probability"].apply(
        lambda probability: max(probability, 1.0 - probability)
    )

    eval_df["predicted_label"] = (eval_df["probability"] >= 0.50).astype(int)
    eval_df["correct"] = (eval_df["predicted_label"] == eval_df["target"]).astype(int)

    buckets = [
        (0.50, 0.55),
        (0.55, 0.60),
        (0.60, 0.65),
        (0.65, 0.70),
        (0.70, 0.75),
        (0.75, 0.80),
        (0.80, 1.01),
    ]

    for lower, upper in buckets:
        bucket_df = eval_df[
            (eval_df["confidence"] >= lower)
            & (eval_df["confidence"] < upper)
        ]

        if bucket_df.empty:
            rows.append(
                {
                    "bucket": f"{lower:.2f}-{upper:.2f}",
                    "rows": 0,
                    "accuracy": None,
                    "avg_confidence": None,
                }
            )
            continue

        rows.append(
            {
                "bucket": f"{lower:.2f}-{upper:.2f}",
                "rows": int(len(bucket_df)),
                "accuracy": float(bucket_df["correct"].mean()),
                "avg_confidence": float(bucket_df["confidence"].mean()),
            }
        )

    return rows


def is_shadow_model_name(model_name: str) -> bool:
    return model_name.startswith("shadow_")


def calibration_method_for_model(model_name: str) -> str:
    if model_name.startswith("calibrated_"):
        return "sigmoid"

    if model_name.startswith("shadow_isotonic_"):
        return "isotonic"

    return "none"


def base_model_type(model_name: str) -> str:
    for prefix in ("calibrated_", "shadow_isotonic_"):
        if model_name.startswith(prefix):
            return model_name[len(prefix):]
    return model_name


def choose_best_model_name(results: dict[str, dict[str, float]]) -> str:
    """
    App-focused selection.

    Priority:
        1. Lower Brier score
        2. Lower log loss
        3. Higher accuracy
        4. Higher ROC AUC
    """
    primary_candidate_names = [
        model_name
        for model_name in results.keys()
        if not is_shadow_model_name(model_name)
    ]

    if not primary_candidate_names:
        primary_candidate_names = list(results.keys())

    return sorted(
        primary_candidate_names,
        key=lambda model_name: (
            results[model_name]["brier_score"],
            results[model_name]["log_loss"],
            -results[model_name]["accuracy"],
            -results[model_name]["roc_auc"],
        ),
    )[0]


def print_metrics_table(results: dict[str, dict[str, float]]) -> None:
    print()
    print("Model comparison:")
    print("-" * 82)
    print(
        f"{'model':<34} "
        f"{'accuracy':>10} "
        f"{'log_loss':>10} "
        f"{'brier':>10} "
        f"{'roc_auc':>10}"
    )
    print("-" * 82)

    for model_name, metrics in results.items():
        print(
            f"{model_name:<34} "
            f"{metrics['accuracy']:>10.4f} "
            f"{metrics['log_loss']:>10.4f} "
            f"{metrics['brier_score']:>10.4f} "
            f"{metrics['roc_auc']:>10.4f}"
        )

    print("-" * 82)


def save_outputs(
    best_model_name: str,
    best_model,
    fitted_models: dict[str, Any],
    results: dict[str, dict[str, float]],
    bucket_reports: dict[str, list[dict[str, Any]]],
    numeric_features: list[str],
    categorical_features: list[str],
    train_df: pd.DataFrame,
    calibration_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    WINNER_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump(best_model, BEST_MODEL_PATH)

    model_registry: dict[str, dict[str, Any]] = {}

    for model_name, model in sorted(fitted_models.items()):
        model_path = WINNER_MODELS_DIR / f"{model_name}.joblib"
        joblib.dump(model, model_path)
        model_registry[model_name] = {
            "model_name": model_name,
            "path": str(model_path.relative_to(MODELS_DIR)),
            "is_best_model": model_name == best_model_name,
            "is_shadow_model": is_shadow_model_name(model_name),
            "training_role": (
                "shadow_experiment"
                if is_shadow_model_name(model_name)
                else "primary_candidate"
            ),
            "calibration_method": calibration_method_for_model(model_name),
            "metrics": results.get(model_name, {}),
        }

    metrics_payload = {
        "best_model_name": best_model_name,
        "available_model_names": sorted(fitted_models.keys()),
        "primary_candidate_model_names": sorted(
            [
                model_name
                for model_name in fitted_models.keys()
                if not is_shadow_model_name(model_name)
            ]
        ),
        "shadow_model_names": sorted(
            [
                model_name
                for model_name in fitted_models.keys()
                if is_shadow_model_name(model_name)
            ]
        ),
        "model_registry_path": str(MODEL_REGISTRY_PATH),
        "selection_priority": [
            "lowest_brier_score",
            "lowest_log_loss",
            "highest_accuracy",
            "highest_roc_auc",
        ],
        "results": results,
        "confidence_bucket_reports": bucket_reports,
        "train_rows": int(len(train_df)),
        "calibration_rows": int(len(calibration_df)),
        "test_rows": int(len(test_df)),
        "train_fights": int(train_df["fight_url"].nunique()),
        "calibration_fights": int(calibration_df["fight_url"].nunique()),
        "test_fights": int(test_df["fight_url"].nunique()),
        "train_date_min": str(train_df["event_date_parsed"].min().date()),
        "train_date_max": str(train_df["event_date_parsed"].max().date()),
        "calibration_date_min": str(calibration_df["event_date_parsed"].min().date()),
        "calibration_date_max": str(calibration_df["event_date_parsed"].max().date()),
        "test_date_min": str(test_df["event_date_parsed"].min().date()),
        "test_date_max": str(test_df["event_date_parsed"].max().date()),
        # The exact fights the model was never trained or calibrated on. The
        # Evaluation tab scores against precisely this set, so its metrics can't be
        # inflated by accidentally including train/calibration fights.
        "test_fight_urls": sorted(test_df["fight_url"].astype(str).unique().tolist()),
        # Version/provenance: human version + recipe hash + git/lineage. Saved
        # predictions are stamped with this so grading knows which generation made them.
        "provenance": build_provenance(
            numeric_features=numeric_features,
            categorical_features=categorical_features,
            model_type=base_model_type(best_model_name),
            calibration_method=calibration_method_for_model(best_model_name),
        ),
    }

    # #17 real reproducibility: fingerprint the exact training data the model was fit
    # on, stamp it into provenance, and record the run in the model_runs audit table.
    feature_columns = numeric_features + categorical_features
    training_data_hash = compute_training_data_hash(train_df, feature_columns)
    metrics_payload["provenance"]["training_data_hash"] = training_data_hash

    with open(CALIBRATED_METRICS_PATH, "w", encoding="utf-8") as file:
        json.dump(metrics_payload, file, indent=2)

    registry_payload = {
        "best_model_name": best_model_name,
        "models_dir": str(WINNER_MODELS_DIR),
        "models": model_registry,
    }

    with open(MODEL_REGISTRY_PATH, "w", encoding="utf-8") as file:
        json.dump(registry_payload, file, indent=2)

    features_payload = {
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
    }

    with open(FEATURES_PATH, "w", encoding="utf-8") as file:
        json.dump(features_payload, file, indent=2)

    provenance = metrics_payload["provenance"]
    model_runs_repository.record_run(
        {
            "trained_at": provenance.get("trained_at", ""),
            "model_version": provenance.get("model_version", ""),
            "recipe_hash": provenance.get("recipe_hash", ""),
            "git_commit": provenance.get("git_commit", ""),
            "git_dirty": provenance.get("git_dirty", False),
            "model_type": provenance.get("model_type", ""),
            "calibration_method": provenance.get("calibration_method", ""),
            "best_model_name": best_model_name,
            "training_data_hash": training_data_hash,
            "training_rows": int(len(train_df)),
            "training_fights": int(train_df["fight_url"].nunique()),
            "feature_count": len(feature_columns),
        }
    )


def main() -> None:
    print("Loading matchup rows...")
    df = load_training_matchups()

    numeric_features, categorical_features = get_feature_columns(df)
    feature_columns = numeric_features + categorical_features

    print(f"Loaded {len(df)} matchup rows.")
    print(f"Unique fights: {df['fight_url'].nunique()}")
    print(f"Numeric features: {len(numeric_features)}")
    print(f"Categorical features: {categorical_features}")

    train_df, calibration_df, test_df = chronological_train_calibration_test_split(df)

    print()
    print("Chronological split:")
    print(
        f"Train:       {len(train_df)} rows, "
        f"{train_df['fight_url'].nunique()} fights, "
        f"{train_df['event_date_parsed'].min().date()} to "
        f"{train_df['event_date_parsed'].max().date()}"
    )
    print(
        f"Calibration: {len(calibration_df)} rows, "
        f"{calibration_df['fight_url'].nunique()} fights, "
        f"{calibration_df['event_date_parsed'].min().date()} to "
        f"{calibration_df['event_date_parsed'].max().date()}"
    )
    print(
        f"Test:        {len(test_df)} rows, "
        f"{test_df['fight_url'].nunique()} fights, "
        f"{test_df['event_date_parsed'].min().date()} to "
        f"{test_df['event_date_parsed'].max().date()}"
    )

    X_train = train_df[feature_columns]
    y_train = train_df["target"]

    X_calibration = calibration_df[feature_columns]
    y_calibration = calibration_df["target"]

    X_test = test_df[feature_columns]
    y_test = test_df["target"]

    base_models = build_base_models(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    fitted_models: dict[str, Any] = {}
    results: dict[str, dict[str, float]] = {}
    bucket_reports: dict[str, list[dict[str, Any]]] = {}

    for model_name, model in base_models.items():
        print()
        print(f"Training {model_name}...")

        model.fit(X_train, y_train)

        uncalibrated_metrics = evaluate_model(model, X_test, y_test)
        results[model_name] = uncalibrated_metrics
        fitted_models[model_name] = model
        bucket_reports[model_name] = build_confidence_bucket_report(
            model,
            X_test,
            y_test,
        )

        print(
            f"{model_name} "
            f"accuracy={uncalibrated_metrics['accuracy']:.4f}, "
            f"log_loss={uncalibrated_metrics['log_loss']:.4f}, "
            f"brier={uncalibrated_metrics['brier_score']:.4f}, "
            f"roc_auc={uncalibrated_metrics['roc_auc']:.4f}"
        )

        calibrated_model_name = f"calibrated_{model_name}"

        print(f"Calibrating {model_name}...")

        calibrated_model = make_calibrated_model(model)
        calibrated_model.fit(X_calibration, y_calibration)

        calibrated_metrics = evaluate_model(calibrated_model, X_test, y_test)

        results[calibrated_model_name] = calibrated_metrics
        fitted_models[calibrated_model_name] = calibrated_model
        bucket_reports[calibrated_model_name] = build_confidence_bucket_report(
            calibrated_model,
            X_test,
            y_test,
        )

        print(
            f"{calibrated_model_name} "
            f"accuracy={calibrated_metrics['accuracy']:.4f}, "
            f"log_loss={calibrated_metrics['log_loss']:.4f}, "
            f"brier={calibrated_metrics['brier_score']:.4f}, "
            f"roc_auc={calibrated_metrics['roc_auc']:.4f}"
        )

        shadow_isotonic_model_name = f"shadow_isotonic_{model_name}"

        print(f"Shadow isotonic calibration for {model_name}...")

        shadow_isotonic_model = make_calibrated_model(
            fitted_model=model,
            method="isotonic",
        )
        shadow_isotonic_model.fit(X_calibration, y_calibration)

        shadow_isotonic_metrics = evaluate_model(shadow_isotonic_model, X_test, y_test)

        results[shadow_isotonic_model_name] = shadow_isotonic_metrics
        fitted_models[shadow_isotonic_model_name] = shadow_isotonic_model
        bucket_reports[shadow_isotonic_model_name] = build_confidence_bucket_report(
            shadow_isotonic_model,
            X_test,
            y_test,
        )

        print(
            f"{shadow_isotonic_model_name} "
            f"accuracy={shadow_isotonic_metrics['accuracy']:.4f}, "
            f"log_loss={shadow_isotonic_metrics['log_loss']:.4f}, "
            f"brier={shadow_isotonic_metrics['brier_score']:.4f}, "
            f"roc_auc={shadow_isotonic_metrics['roc_auc']:.4f}"
        )

    print_metrics_table(results)

    best_model_name = choose_best_model_name(results)
    best_model = fitted_models[best_model_name]

    print()
    print(f"Best model for app predictions: {best_model_name}")

    print()
    print("Confidence bucket report for best model:")
    for row in bucket_reports[best_model_name]:
        print(row)

    save_outputs(
        best_model_name=best_model_name,
        best_model=best_model,
        fitted_models=fitted_models,
        results=results,
        bucket_reports=bucket_reports,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        train_df=train_df,
        calibration_df=calibration_df,
        test_df=test_df,
    )

    print()
    print(f"Saved best model to: {BEST_MODEL_PATH}")
    print(f"Saved all winner models to: {WINNER_MODELS_DIR}")
    print(f"Saved model registry to: {MODEL_REGISTRY_PATH}")
    print(f"Saved calibrated metrics to: {CALIBRATED_METRICS_PATH}")
    print(f"Saved features to: {FEATURES_PATH}")


if __name__ == "__main__":
    main()
