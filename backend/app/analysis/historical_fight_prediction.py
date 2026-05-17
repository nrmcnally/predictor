from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]

TRAINING_MATCHUPS_CSV = PROJECT_ROOT / "data" / "processed" / "training_matchups.csv"
MODEL_FEATURES_JSON = PROJECT_ROOT / "models" / "model_features.json"

RANDOM_STATE = 42


EXCLUDED_FEATURE_COLUMNS = {
    "fight_url",
    "event_name",
    "event_date",
    "event_date_parsed",
    "event_location",
    "event_url",
    "fighter_a",
    "fighter_b",
    "target",
    "winner",
    "loser",
    "result",
    "method",
    "round",
    "time",
}


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def normalize_name(value: Any) -> str:
    return clean_text(value).lower()


def load_training_matchups() -> pd.DataFrame:
    if not TRAINING_MATCHUPS_CSV.exists():
        raise FileNotFoundError(f"Missing {TRAINING_MATCHUPS_CSV}")

    df = pd.read_csv(TRAINING_MATCHUPS_CSV)

    required_columns = {
        "fight_url",
        "event_date",
        "fighter_a",
        "fighter_b",
        "target",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            "training_matchups.csv is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    df["event_date_parsed"] = pd.to_datetime(df["event_date"], errors="coerce")
    df = df[df["event_date_parsed"].notna()].copy()

    return df.sort_values("event_date_parsed").reset_index(drop=True)


def load_feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    if MODEL_FEATURES_JSON.exists():
        with open(MODEL_FEATURES_JSON, "r", encoding="utf-8") as file:
            payload = json.load(file)

        numeric_features = payload.get("numeric_features", [])
        categorical_features = payload.get("categorical_features", [])

        numeric_features = [
            column for column in numeric_features
            if column in df.columns
        ]

        categorical_features = [
            column for column in categorical_features
            if column in df.columns
        ]

        if numeric_features or categorical_features:
            return numeric_features, categorical_features

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


def find_target_fight(
    df: pd.DataFrame,
    fighter_a: str,
    fighter_b: str,
    event_date: str | None,
) -> tuple[str, pd.Timestamp, pd.DataFrame]:
    fighter_a_normalized = normalize_name(fighter_a)
    fighter_b_normalized = normalize_name(fighter_b)

    df = df.copy()
    df["fighter_a_normalized"] = df["fighter_a"].apply(normalize_name)
    df["fighter_b_normalized"] = df["fighter_b"].apply(normalize_name)

    mask = (
        (
            (df["fighter_a_normalized"] == fighter_a_normalized)
            & (df["fighter_b_normalized"] == fighter_b_normalized)
        )
        | (
            (df["fighter_a_normalized"] == fighter_b_normalized)
            & (df["fighter_b_normalized"] == fighter_a_normalized)
        )
    )

    matches = df[mask].copy()

    if event_date:
        target_date = pd.to_datetime(event_date, errors="coerce")

        if pd.isna(target_date):
            raise ValueError(f"Could not parse event date: {event_date}")

        matches = matches[matches["event_date_parsed"].dt.date == target_date.date()].copy()

    if matches.empty:
        similar = df[
            df["fighter_a"].astype(str).str.contains(fighter_a, case=False, na=False)
            | df["fighter_b"].astype(str).str.contains(fighter_a, case=False, na=False)
            | df["fighter_a"].astype(str).str.contains(fighter_b, case=False, na=False)
            | df["fighter_b"].astype(str).str.contains(fighter_b, case=False, na=False)
        ][["event_date", "event_name", "fighter_a", "fighter_b", "fight_url"]].drop_duplicates()

        print()
        print("No exact fight found. Similar rows:")
        print(similar.tail(30).to_string(index=False))

        raise ValueError(f"Could not find fight: {fighter_a} vs {fighter_b}")

    fight_candidates = (
        matches[
            [
                "fight_url",
                "event_date_parsed",
                "event_date",
                "event_name",
                "fighter_a",
                "fighter_b",
            ]
        ]
        .drop_duplicates(subset=["fight_url"])
        .sort_values("event_date_parsed")
    )

    if len(fight_candidates) > 1:
        print()
        print("Multiple matching fights found. Using the most recent one.")
        print(fight_candidates.to_string(index=False))

    selected = fight_candidates.iloc[-1]

    fight_url = clean_text(selected["fight_url"])
    target_date = selected["event_date_parsed"]

    target_rows = matches[matches["fight_url"].astype(str).eq(fight_url)].copy()

    return fight_url, target_date, target_rows


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
    models: dict[str, Pipeline] = {
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
                    LogisticRegression(
                        max_iter=4000,
                        class_weight="balanced",
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
                    RandomForestClassifier(
                        n_estimators=500,
                        min_samples_leaf=5,
                        class_weight="balanced_subsample",
                        n_jobs=-1,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
    }

    if XGBClassifier is not None:
        models["xgboost"] = Pipeline(
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
                    XGBClassifier(
                        n_estimators=500,
                        max_depth=3,
                        learning_rate=0.03,
                        subsample=0.9,
                        colsample_bytree=0.9,
                        objective="binary:logistic",
                        eval_metric="logloss",
                        random_state=RANDOM_STATE,
                        n_jobs=-1,
                    ),
                ),
            ]
        )

    return models


def chronological_validation_split(
    df: pd.DataFrame,
    test_fraction: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    split_index = int(len(df) * (1.0 - test_fraction))

    train_df = df.iloc[:split_index].copy()
    validation_df = df.iloc[split_index:].copy()

    return train_df, validation_df


def get_probability_of_class_one(model: Pipeline, row_df: pd.DataFrame) -> float:
    classes = list(model.named_steps["classifier"].classes_)
    probabilities = model.predict_proba(row_df)[0]

    if 1 in classes:
        class_index = classes.index(1)
    elif 1.0 in classes:
        class_index = classes.index(1.0)
    else:
        class_index = list(classes).index(max(classes))

    return float(probabilities[class_index])


def predict_target_fight(
    model: Pipeline,
    target_rows: pd.DataFrame,
    feature_columns: list[str],
    fighter_a: str,
    fighter_b: str,
) -> dict[str, Any]:
    fighter_a_normalized = normalize_name(fighter_a)
    fighter_b_normalized = normalize_name(fighter_b)

    target_rows = target_rows.copy()
    target_rows["fighter_a_normalized"] = target_rows["fighter_a"].apply(normalize_name)
    target_rows["fighter_b_normalized"] = target_rows["fighter_b"].apply(normalize_name)

    forward_rows = target_rows[
        (target_rows["fighter_a_normalized"] == fighter_a_normalized)
        & (target_rows["fighter_b_normalized"] == fighter_b_normalized)
    ]

    reverse_rows = target_rows[
        (target_rows["fighter_a_normalized"] == fighter_b_normalized)
        & (target_rows["fighter_b_normalized"] == fighter_a_normalized)
    ]

    if forward_rows.empty:
        raise ValueError(f"Missing target row for {fighter_a} vs {fighter_b}")

    if reverse_rows.empty:
        raise ValueError(f"Missing target row for {fighter_b} vs {fighter_a}")

    forward_row = forward_rows.iloc[[0]][feature_columns].copy()
    reverse_row = reverse_rows.iloc[[0]][feature_columns].copy()

    fighter_a_direct_probability = get_probability_of_class_one(model, forward_row)
    fighter_b_direct_probability = get_probability_of_class_one(model, reverse_row)

    total = fighter_a_direct_probability + fighter_b_direct_probability

    if total <= 0:
        fighter_a_probability = fighter_a_direct_probability
        fighter_b_probability = 1.0 - fighter_a_probability
    else:
        fighter_a_probability = fighter_a_direct_probability / total
        fighter_b_probability = fighter_b_direct_probability / total

    predicted_winner = fighter_a if fighter_a_probability >= fighter_b_probability else fighter_b

    return {
        "fighter_a": fighter_a,
        "fighter_b": fighter_b,
        "fighter_a_direct_probability": fighter_a_direct_probability,
        "fighter_b_direct_probability": fighter_b_direct_probability,
        "fighter_a_probability": fighter_a_probability,
        "fighter_b_probability": fighter_b_probability,
        "fighter_a_percentage": f"{fighter_a_probability * 100.0:.1f}%",
        "fighter_b_percentage": f"{fighter_b_probability * 100.0:.1f}%",
        "predicted_winner": predicted_winner,
        "confidence": max(fighter_a_probability, fighter_b_probability),
        "confidence_percentage": f"{max(fighter_a_probability, fighter_b_probability) * 100.0:.1f}%",
    }


def evaluate_model(
    model: Pipeline,
    validation_df: pd.DataFrame,
    feature_columns: list[str],
) -> dict[str, Any]:
    X_validation = validation_df[feature_columns].copy()
    y_validation = validation_df["target"].astype(int).copy()

    predictions = model.predict(X_validation)
    probabilities = model.predict_proba(X_validation)

    classes = list(model.named_steps["classifier"].classes_)

    try:
        validation_log_loss = log_loss(
            y_validation,
            probabilities,
            labels=classes,
        )
    except Exception:
        validation_log_loss = None

    return {
        "accuracy": float(accuracy_score(y_validation, predictions)),
        "log_loss": float(validation_log_loss) if validation_log_loss is not None else None,
        "validation_rows": int(len(validation_df)),
    }


def selection_key(result: dict[str, Any]) -> tuple[float, float]:
    logloss = result["validation_metrics"]["log_loss"]

    if logloss is None:
        logloss = 999.0

    return (float(logloss), -float(result["validation_metrics"]["accuracy"]))


def run_historical_prediction(
    fighter_a: str,
    fighter_b: str,
    event_date: str | None,
    test_fraction: float,
) -> dict[str, Any]:
    df = load_training_matchups()

    fight_url, target_date, target_rows = find_target_fight(
        df=df,
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        event_date=event_date,
    )

    historical_df = df[df["event_date_parsed"] < target_date].copy()
    historical_df = historical_df[historical_df["target"].notna()].copy()
    historical_df["target"] = historical_df["target"].astype(int)

    if len(historical_df) < 500:
        raise ValueError(
            f"Only {len(historical_df)} historical rows before this event. "
            "That is probably too few for a useful replay."
        )

    numeric_features, categorical_features = load_feature_columns(historical_df)
    feature_columns = numeric_features + categorical_features

    historical_df = historical_df.dropna(subset=["target"]).copy()

    train_df, validation_df = chronological_validation_split(
        historical_df,
        test_fraction=test_fraction,
    )

    candidate_models = build_candidate_models(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    results = []

    for model_name, model in candidate_models.items():
        print()
        print(f"Training historical {model_name}...")

        model.fit(train_df[feature_columns], train_df["target"].astype(int))

        validation_metrics = evaluate_model(
            model=model,
            validation_df=validation_df,
            feature_columns=feature_columns,
        )

        # Refit on all data available before target fight, like a real pre-fight model.
        model.fit(historical_df[feature_columns], historical_df["target"].astype(int))

        target_prediction = predict_target_fight(
            model=model,
            target_rows=target_rows,
            feature_columns=feature_columns,
            fighter_a=fighter_a,
            fighter_b=fighter_b,
        )

        results.append(
            {
                "model_name": model_name,
                "validation_metrics": validation_metrics,
                "target_prediction": target_prediction,
            }
        )

    results = sorted(results, key=selection_key)

    return {
        "target": {
            "fighter_a": fighter_a,
            "fighter_b": fighter_b,
            "fight_url": fight_url,
            "event_name": clean_text(target_rows.iloc[0].get("event_name", "")),
            "event_date": clean_text(target_rows.iloc[0].get("event_date", "")),
            "target_date_cutoff": target_date.strftime("%Y-%m-%d"),
        },
        "training": {
            "historical_rows_before_event": int(len(historical_df)),
            "train_rows": int(len(train_df)),
            "validation_rows": int(len(validation_df)),
            "numeric_features": int(len(numeric_features)),
            "categorical_features": categorical_features,
            "test_fraction": test_fraction,
        },
        "best_by_validation_log_loss": results[0]["model_name"],
        "results": results,
    }


def print_report(report: dict[str, Any]) -> None:
    print()
    print("=" * 80)
    print("Historical fight prediction replay")
    print("=" * 80)

    target = report["target"]
    training = report["training"]

    print(f"Fight: {target['fighter_a']} vs {target['fighter_b']}")
    print(f"Event: {target['event_name']}")
    print(f"Event date: {target['event_date']}")
    print(f"Training cutoff: before {target['target_date_cutoff']}")
    print()
    print(f"Historical rows before event: {training['historical_rows_before_event']}")
    print(f"Train rows: {training['train_rows']}")
    print(f"Validation rows: {training['validation_rows']}")
    print(f"Numeric features: {training['numeric_features']}")
    print(f"Categorical features: {training['categorical_features']}")
    print()
    print(f"Best model by validation log loss: {report['best_by_validation_log_loss']}")

    print()
    print("Model comparison")
    print("-" * 80)

    for result in report["results"]:
        model_name = result["model_name"]
        metrics = result["validation_metrics"]
        prediction = result["target_prediction"]

        print()
        print(model_name)
        print(f"  Validation accuracy: {metrics['accuracy'] * 100.0:.1f}%")
        print(
            "  Validation log loss: "
            + (
                f"{metrics['log_loss']:.4f}"
                if metrics["log_loss"] is not None
                else "N/A"
            )
        )
        print(f"  Predicted winner: {prediction['predicted_winner']}")
        print(f"  Confidence: {prediction['confidence_percentage']}")
        print(f"  {prediction['fighter_a']}: {prediction['fighter_a_percentage']}")
        print(f"  {prediction['fighter_b']}: {prediction['fighter_b_percentage']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay what the model would have predicted before a historical fight."
    )

    parser.add_argument(
        "--fighter-a",
        default="Tatsuro Taira",
        help="First fighter name.",
    )

    parser.add_argument(
        "--fighter-b",
        default="Brandon Moreno",
        help="Second fighter name.",
    )

    parser.add_argument(
        "--event-date",
        default=None,
        help="Optional event date filter, for example 2025-11-22.",
    )

    parser.add_argument(
        "--test-fraction",
        type=float,
        default=0.2,
        help="Chronological validation fraction used to compare models.",
    )

    parser.add_argument(
        "--save-json",
        default="",
        help="Optional path to save the replay report JSON.",
    )

    args = parser.parse_args()

    report = run_historical_prediction(
        fighter_a=args.fighter_a,
        fighter_b=args.fighter_b,
        event_date=args.event_date,
        test_fraction=args.test_fraction,
    )

    print_report(report)

    if args.save_json:
        output_path = Path(args.save_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(report, file, indent=2)

        print()
        print(f"Saved report: {output_path}")


if __name__ == "__main__":
    main()