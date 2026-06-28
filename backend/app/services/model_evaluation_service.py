from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"

TRAINING_MATCHUPS_CSV = PROCESSED_DATA_DIR / "training_matchups.csv"
BEST_MODEL_PATH = MODELS_DIR / "best_winner_model.joblib"
FEATURES_PATH = MODELS_DIR / "model_features.json"
METRICS_PATH = MODELS_DIR / "calibrated_model_metrics.json"


MAJOR_WEIGHT_CLASSES = [
    "Women's Strawweight",
    "Women's Flyweight",
    "Women's Bantamweight",
    "Women's Featherweight",
    "Flyweight",
    "Bantamweight",
    "Featherweight",
    "Lightweight",
    "Welterweight",
    "Middleweight",
    "Light Heavyweight",
    "Heavyweight",
]


CONFIDENCE_BUCKETS = [
    {
        "label": "Very close / low confidence",
        "min": 0.50,
        "max": 0.55,
    },
    {
        "label": "Slight lean",
        "min": 0.55,
        "max": 0.60,
    },
    {
        "label": "Moderate lean",
        "min": 0.60,
        "max": 0.65,
    },
    {
        "label": "Strong lean",
        "min": 0.65,
        "max": 0.70,
    },
    {
        "label": "High confidence",
        "min": 0.70,
        "max": 1.01,
    },
]

FAVORITE_THRESHOLDS = [
    0.50,
    0.55,
    0.60,
    0.65,
    0.70,
    0.75,
]

def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def format_percent(value: float | None) -> str:
    if value is None or pd.isna(value):
        return ""

    return f"{value * 100.0:.1f}%"


def load_training_matchups() -> pd.DataFrame:
    if not TRAINING_MATCHUPS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {TRAINING_MATCHUPS_CSV}. Run the update pipeline first."
        )

    df = pd.read_csv(TRAINING_MATCHUPS_CSV)

    if "event_date" not in df.columns:
        raise ValueError("training_matchups.csv must include event_date.")

    if "target" not in df.columns:
        raise ValueError("training_matchups.csv must include target.")

    df["event_date_parsed"] = pd.to_datetime(df["event_date"], errors="coerce")
    df = df[df["event_date_parsed"].notna()].copy()

    return df


def load_model_and_features():
    if not BEST_MODEL_PATH.exists():
        raise FileNotFoundError(f"Missing {BEST_MODEL_PATH}. Train the model first.")

    if not FEATURES_PATH.exists():
        raise FileNotFoundError(f"Missing {FEATURES_PATH}. Train the model first.")

    model = joblib.load(BEST_MODEL_PATH)

    with open(FEATURES_PATH, "r", encoding="utf-8") as file:
        feature_payload = json.load(file)

    numeric_features = feature_payload["numeric_features"]
    categorical_features = feature_payload["categorical_features"]

    return model, numeric_features, categorical_features


def load_saved_metrics() -> dict[str, Any]:
    if not METRICS_PATH.exists():
        return {}

    with open(METRICS_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def chronological_test_split(
    df: pd.DataFrame,
    test_fraction: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Splits by unique fight_url when available so both row orientations of the same
    fight stay together.
    """
    test_fraction = max(0.05, min(float(test_fraction), 0.50))

    if "fight_url" not in df.columns:
        sorted_df = df.sort_values("event_date_parsed").reset_index(drop=True)
        split_index = int(len(sorted_df) * (1.0 - test_fraction))

        return (
            sorted_df.iloc[:split_index].copy(),
            sorted_df.iloc[split_index:].copy(),
        )

    fight_dates = (
        df.groupby("fight_url", as_index=False)["event_date_parsed"]
        .min()
        .sort_values("event_date_parsed")
        .reset_index(drop=True)
    )

    split_index = int(len(fight_dates) * (1.0 - test_fraction))

    train_fight_urls = set(fight_dates.iloc[:split_index]["fight_url"].astype(str))
    test_fight_urls = set(fight_dates.iloc[split_index:]["fight_url"].astype(str))

    train_df = df[df["fight_url"].astype(str).isin(train_fight_urls)].copy()
    test_df = df[df["fight_url"].astype(str).isin(test_fight_urls)].copy()

    return train_df, test_df


def get_confidence_bucket(confidence: float) -> str:
    for bucket in CONFIDENCE_BUCKETS:
        if bucket["min"] <= confidence < bucket["max"]:
            return bucket["label"]

    return "Unknown"


def safe_metric(metric_name: str, y_true, probabilities, predictions=None):
    try:
        if metric_name == "accuracy":
            return accuracy_score(y_true, predictions)

        if metric_name == "brier":
            return brier_score_loss(y_true, probabilities)

        if metric_name == "log_loss":
            return log_loss(y_true, probabilities, labels=[0, 1])

        if metric_name == "roc_auc":
            return roc_auc_score(y_true, probabilities)

    except Exception:
        return None

    return None


def add_row_level_prediction_columns(
    test_df: pd.DataFrame,
    model,
    numeric_features: list[str],
    categorical_features: list[str],
) -> pd.DataFrame:
    feature_columns = numeric_features + categorical_features

    missing_features = [
        column for column in feature_columns if column not in test_df.columns
    ]

    if missing_features:
        raise ValueError(
            "training_matchups.csv is missing model features: "
            + ", ".join(missing_features[:20])
        )

    X_test = test_df[feature_columns].copy()
    probabilities = model.predict_proba(X_test)[:, 1]

    evaluated_df = test_df.copy()
    evaluated_df["fighter_a_win_probability"] = probabilities
    evaluated_df["predicted_target"] = (
        evaluated_df["fighter_a_win_probability"] >= 0.5
    ).astype(int)

    evaluated_df["row_model_confidence"] = evaluated_df[
        "fighter_a_win_probability"
    ].apply(lambda probability: max(probability, 1.0 - probability))

    evaluated_df["row_prediction_correct"] = (
        evaluated_df["predicted_target"].astype(int)
        == evaluated_df["target"].astype(int)
    )

    evaluated_df["year"] = evaluated_df["event_date_parsed"].dt.year.astype(str)

    return evaluated_df


def summarize_row_level_metrics(row_level_df: pd.DataFrame) -> dict[str, Any]:
    if row_level_df.empty:
        return {
            "row_count": 0,
            "row_accuracy": None,
            "row_accuracy_percentage": "",
            "brier_score": None,
            "log_loss": None,
            "roc_auc": None,
        }

    y_true = row_level_df["target"].astype(int)
    probabilities = row_level_df["fighter_a_win_probability"].astype(float)
    predictions = row_level_df["predicted_target"].astype(int)

    row_accuracy = safe_metric(
        metric_name="accuracy",
        y_true=y_true,
        probabilities=probabilities,
        predictions=predictions,
    )

    brier = safe_metric(
        metric_name="brier",
        y_true=y_true,
        probabilities=probabilities,
    )

    logloss = safe_metric(
        metric_name="log_loss",
        y_true=y_true,
        probabilities=probabilities,
    )

    auc = safe_metric(
        metric_name="roc_auc",
        y_true=y_true,
        probabilities=probabilities,
    )

    return {
        "row_count": int(len(row_level_df)),
        "row_accuracy": float(row_accuracy) if row_accuracy is not None else None,
        "row_accuracy_percentage": format_percent(row_accuracy),
        "brier_score": float(brier) if brier is not None else None,
        "log_loss": float(logloss) if logloss is not None else None,
        "roc_auc": float(auc) if auc is not None else None,
    }


def build_fight_level_predictions(row_level_df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts two-row matchup orientation data into one row per fight.

    For each fight, the row where target == 1 is the actual winner as fighter_a.
    The row where target == 0 is usually the reverse orientation.

    We compare:
      model score for actual winner orientation
      vs.
      model score for actual loser orientation

    This better matches the app's two-perspective prediction style.
    """
    if row_level_df.empty:
        return pd.DataFrame()

    if "fight_url" not in row_level_df.columns:
        fight_df = row_level_df.copy()

        fight_df["predicted_winner"] = fight_df.apply(
            lambda row: row.get("fighter_a", "")
            if int(row["predicted_target"]) == 1
            else row.get("fighter_b", ""),
            axis=1,
        )

        fight_df["actual_winner"] = fight_df.apply(
            lambda row: row.get("fighter_a", "")
            if int(row["target"]) == 1
            else row.get("fighter_b", ""),
            axis=1,
        )

        fight_df["prediction_correct"] = (
            fight_df["predicted_winner"] == fight_df["actual_winner"]
        )

        fight_df["model_confidence"] = fight_df["row_model_confidence"]
        fight_df["confidence_bucket"] = fight_df["model_confidence"].apply(
            get_confidence_bucket
        )

        return fight_df

    rows = []

    for fight_url, group_df in row_level_df.groupby("fight_url"):
        winner_rows = group_df[group_df["target"].astype(int) == 1].copy()
        loser_rows = group_df[group_df["target"].astype(int) == 0].copy()

        if winner_rows.empty:
            continue

        winner_row = winner_rows.iloc[0]
        loser_row = loser_rows.iloc[0] if not loser_rows.empty else None

        winner_direct_probability = float(winner_row["fighter_a_win_probability"])

        if loser_row is not None:
            loser_direct_probability = float(loser_row["fighter_a_win_probability"])
        else:
            loser_direct_probability = 1.0 - winner_direct_probability

        total_probability = winner_direct_probability + loser_direct_probability

        if total_probability <= 0:
            actual_winner_probability = winner_direct_probability
        else:
            actual_winner_probability = winner_direct_probability / total_probability

        actual_winner = clean_text(winner_row.get("fighter_a", ""))
        actual_loser = clean_text(winner_row.get("fighter_b", ""))

        prediction_correct = actual_winner_probability >= 0.5

        predicted_winner = actual_winner if prediction_correct else actual_loser
        model_confidence = max(actual_winner_probability, 1.0 - actual_winner_probability)

        rows.append(
            {
                "fight_url": clean_text(fight_url),
                "event_date": clean_text(winner_row.get("event_date", "")),
                "event_date_parsed": winner_row.get("event_date_parsed"),
                "event_name": clean_text(winner_row.get("event_name", "")),
                "weight_class": clean_text(winner_row.get("weight_class", "")),
                "fighter_a": actual_winner,
                "fighter_b": actual_loser,
                "actual_winner": actual_winner,
                "predicted_winner": predicted_winner,
                "prediction_correct": bool(prediction_correct),
                "actual_winner_probability": float(actual_winner_probability),
                "model_confidence": float(model_confidence),
                "confidence_bucket": get_confidence_bucket(model_confidence),
                "year": str(winner_row.get("event_date_parsed").year)
                if pd.notna(winner_row.get("event_date_parsed"))
                else "",
            }
        )

    return pd.DataFrame(rows)


def summarize_fight_predictions(fight_df: pd.DataFrame) -> dict[str, Any]:
    if fight_df.empty:
        return {
            "fight_count": 0,
            "accuracy": None,
            "accuracy_percentage": "",
            "average_confidence": None,
            "average_confidence_percentage": "",
        }

    accuracy = float(fight_df["prediction_correct"].mean())
    average_confidence = float(fight_df["model_confidence"].mean())

    return {
        "fight_count": int(len(fight_df)),
        "accuracy": accuracy,
        "accuracy_percentage": format_percent(accuracy),
        "average_confidence": average_confidence,
        "average_confidence_percentage": format_percent(average_confidence),
    }


def summarize_by_column(
    fight_df: pd.DataFrame,
    column: str,
    sort_by_name: bool = False,
) -> list[dict[str, Any]]:
    if fight_df.empty or column not in fight_df.columns:
        return []

    rows = []

    for value, group_df in fight_df.groupby(column, dropna=False):
        summary = summarize_fight_predictions(group_df)

        rows.append(
            {
                "name": clean_text(value),
                **summary,
            }
        )

    if sort_by_name:
        rows = sorted(rows, key=lambda row: row["name"], reverse=True)
    else:
        rows = sorted(rows, key=lambda row: row["fight_count"], reverse=True)

    return rows


def summarize_by_confidence_bucket(fight_df: pd.DataFrame) -> list[dict[str, Any]]:
    if fight_df.empty:
        return []

    rows = []

    for bucket in CONFIDENCE_BUCKETS:
        group_df = fight_df[
            (fight_df["model_confidence"] >= bucket["min"])
            & (fight_df["model_confidence"] < bucket["max"])
        ].copy()

        summary = summarize_fight_predictions(group_df)

        rows.append(
            {
                "name": bucket["label"],
                "min_confidence": bucket["min"],
                "max_confidence": bucket["max"],
                **summary,
            }
        )

    return rows

def summarize_by_favorite_threshold(fight_df: pd.DataFrame) -> list[dict[str, Any]]:
    if fight_df.empty:
        return []

    rows = []

    for threshold in FAVORITE_THRESHOLDS:
        group_df = fight_df[fight_df["model_confidence"] >= threshold].copy()

        summary = summarize_fight_predictions(group_df)

        correct_count = 0
        wrong_count = 0

        if not group_df.empty:
            correct_count = int(group_df["prediction_correct"].sum())
            wrong_count = int((~group_df["prediction_correct"]).sum())

        rows.append(
            {
                "name": f"{threshold * 100:.0f}%+ favorites",
                "threshold": threshold,
                "fight_count": summary["fight_count"],
                "correct_count": correct_count,
                "wrong_count": wrong_count,
                "accuracy": summary["accuracy"],
                "accuracy_percentage": summary["accuracy_percentage"],
                "average_confidence": summary["average_confidence"],
                "average_confidence_percentage": summary["average_confidence_percentage"],
            }
        )

    return rows

def sample_recent_predictions(
    fight_df: pd.DataFrame,
    limit: int = 25,
) -> list[dict[str, Any]]:
    if fight_df.empty:
        return []

    sample_df = fight_df.sort_values("event_date_parsed", ascending=False).head(limit)

    rows = []

    for _, row in sample_df.iterrows():
        confidence = float(row["model_confidence"])
        actual_winner_probability = float(row["actual_winner_probability"])

        rows.append(
            {
                "event_date": clean_text(row.get("event_date", "")),
                "event_name": clean_text(row.get("event_name", "")),
                "weight_class": clean_text(row.get("weight_class", "")),
                "fighter_a": clean_text(row.get("fighter_a", "")),
                "fighter_b": clean_text(row.get("fighter_b", "")),
                "predicted_winner": clean_text(row.get("predicted_winner", "")),
                "actual_winner": clean_text(row.get("actual_winner", "")),
                "prediction_correct": bool(row.get("prediction_correct", False)),
                "actual_winner_probability": actual_winner_probability,
                "actual_winner_percentage": format_percent(actual_winner_probability),
                "confidence": confidence,
                "confidence_percentage": format_percent(confidence),
                "confidence_bucket": clean_text(row.get("confidence_bucket", "")),
            }
        )

    return rows

def sample_confident_predictions(
    fight_df: pd.DataFrame,
    prediction_correct: bool,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if fight_df.empty:
        return []

    filtered_df = fight_df[
        fight_df["prediction_correct"] == prediction_correct
    ].copy()

    if filtered_df.empty:
        return []

    sample_df = filtered_df.sort_values(
        ["model_confidence", "event_date_parsed"],
        ascending=[False, False],
    ).head(limit)

    rows = []

    for _, row in sample_df.iterrows():
        confidence = float(row["model_confidence"])
        actual_winner_probability = float(row["actual_winner_probability"])

        rows.append(
            {
                "event_date": clean_text(row.get("event_date", "")),
                "event_name": clean_text(row.get("event_name", "")),
                "weight_class": clean_text(row.get("weight_class", "")),
                "fighter_a": clean_text(row.get("fighter_a", "")),
                "fighter_b": clean_text(row.get("fighter_b", "")),
                "predicted_winner": clean_text(row.get("predicted_winner", "")),
                "actual_winner": clean_text(row.get("actual_winner", "")),
                "prediction_correct": bool(row.get("prediction_correct", False)),
                "actual_winner_probability": actual_winner_probability,
                "actual_winner_percentage": format_percent(actual_winner_probability),
                "confidence": confidence,
                "confidence_percentage": format_percent(confidence),
                "confidence_bucket": clean_text(row.get("confidence_bucket", "")),
            }
        )

    return rows

def resolve_holdout(
    df: pd.DataFrame,
    saved_metrics: dict[str, Any],
    test_fraction: float,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    Returns (train_df, holdout_df, source) where holdout_df is the model's true
    out-of-sample test set. Resolution order, most precise first:

      1. the exact test_fight_urls saved at train time (bulletproof);
      2. the saved test_date_min boundary (reconstructs the chronological holdout
         for models trained before fight_urls were persisted);
      3. a clamped chronological split (never larger than the standard training
         test size), so even with neither saved it cannot pull train/calibration
         fights into the holdout.

    This replaces the old behaviour where the holdout was recomputed straight from
    the `test_fraction` control, which let a caller silently include fights the
    model had trained or calibrated on and inflate the reported metrics.
    """
    if "fight_url" in df.columns:
        saved_urls = saved_metrics.get("test_fight_urls") or []

        if saved_urls:
            url_set = {str(url) for url in saved_urls}
            mask = df["fight_url"].astype(str).isin(url_set)
            holdout_df = df[mask].copy()

            if not holdout_df.empty:
                return df[~mask].copy(), holdout_df, "saved_holdout"

    test_date_min = saved_metrics.get("test_date_min")

    if test_date_min:
        boundary = pd.to_datetime(test_date_min, errors="coerce")

        if pd.notna(boundary):
            mask = df["event_date_parsed"] >= boundary
            holdout_df = df[mask].copy()

            if not holdout_df.empty:
                return df[~mask].copy(), holdout_df, "saved_date_boundary"

    safe_fraction = min(test_fraction, 0.20)
    train_df, holdout_df = chronological_test_split(df, safe_fraction)
    return train_df, holdout_df, "chronological_fraction"


def get_model_evaluation(
    test_fraction: float = 0.20,
    recent_prediction_limit: int = 25,
) -> dict[str, Any]:
    df = load_training_matchups()
    model, numeric_features, categorical_features = load_model_and_features()
    saved_metrics = load_saved_metrics()

    train_df, test_df, holdout_source = resolve_holdout(
        df=df,
        saved_metrics=saved_metrics,
        test_fraction=test_fraction,
    )

    row_level_df = add_row_level_prediction_columns(
        test_df=test_df,
        model=model,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    fight_level_df = build_fight_level_predictions(row_level_df)

    fight_summary = summarize_fight_predictions(fight_level_df)
    row_metrics = summarize_row_level_metrics(row_level_df)

    overall_summary = {
        **fight_summary,
        **row_metrics,
    }

    major_weight_fights_df = fight_level_df[
        fight_level_df["weight_class"].isin(MAJOR_WEIGHT_CLASSES)
    ].copy()

    if not fight_level_df.empty:
        test_date_min = fight_level_df["event_date_parsed"].min()
        test_date_max = fight_level_df["event_date_parsed"].max()
    else:
        test_date_min = pd.NaT
        test_date_max = pd.NaT

    return {
        "metadata": {
            "source_file": str(TRAINING_MATCHUPS_CSV),
            "model_file": str(BEST_MODEL_PATH),
            "features_file": str(FEATURES_PATH),
            "holdout_source": holdout_source,
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "test_fights": int(len(fight_level_df)),
            "test_date_min": test_date_min.strftime("%B %d, %Y")
            if pd.notna(test_date_min)
            else "",
            "test_date_max": test_date_max.strftime("%B %d, %Y")
            if pd.notna(test_date_max)
            else "",
            "saved_metrics_file": str(METRICS_PATH),
            "saved_best_model_name": saved_metrics.get("best_model_name", ""),
            "metric_note": (
                "Scored on the model's true chronological holdout — the fights it was never "
                "trained or calibrated on — so these numbers are not affected by any test-window "
                "control. Fight accuracy and confidence use one row per fight with two-perspective "
                "normalization; Brier score, log loss, and ROC AUC are row-level."
            ),
        },
        "overall": overall_summary,
        "by_weight_class": summarize_by_column(
            major_weight_fights_df,
            "weight_class",
        ),
        "by_year": summarize_by_column(
            fight_level_df,
            "year",
            sort_by_name=True,
        ),
        "by_confidence_bucket": summarize_by_confidence_bucket(fight_level_df),
        "by_favorite_threshold": summarize_by_favorite_threshold(fight_level_df),
        "recent_predictions": sample_recent_predictions(
            fight_df=fight_level_df,
            limit=recent_prediction_limit,
        ),
        "most_confident_correct": sample_confident_predictions(
        fight_df=fight_level_df,
        prediction_correct=True,
        limit=10,
        ),
        "most_confident_wrong": sample_confident_predictions(
            fight_df=fight_level_df,
            prediction_correct=False,
            limit=10,
        ),
    }