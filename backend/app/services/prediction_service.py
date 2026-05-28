from __future__ import annotations

import json
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.features.add_weight_size_features import (
    WEIGHT_SIZE_FEATURE_COLUMNS,
    build_division_average_lookup,
    build_profile_lookup,
    build_weight_size_feature_row,
    load_fight_stats as load_weight_size_fight_stats,
    load_fighter_profiles as load_weight_size_fighter_profiles,
    normalize_name as normalize_weight_size_name,
    sorted_fight_stats,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"

CURRENT_FIGHTER_FEATURES_CSV = PROCESSED_DATA_DIR / "current_fighter_features.csv"
BEST_MODEL_PATH = MODELS_DIR / "best_winner_model.joblib"
FEATURES_PATH = MODELS_DIR / "model_features.json"
MODEL_REGISTRY_PATH = MODELS_DIR / "model_registry.json"
WINNER_MODELS_DIR = MODELS_DIR / "winner_models"


class FighterNotFoundError(ValueError):
    def __init__(self, fighter_name: str, suggestions: list[str]):
        self.fighter_name = fighter_name
        self.suggestions = suggestions

        message = f"Could not find fighter: {fighter_name}"

        if suggestions:
            message += "\n\nDid you mean one of these?\n"
            message += "\n".join(f"- {name}" for name in suggestions)

        super().__init__(message)


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def normalize_name(value: Any) -> str:
    return clean_text(value).lower()


def safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_percent(value: float) -> str:
    return f"{value * 100.0:.1f}%"


def get_confidence_label(confidence: float) -> str:
    if confidence < 0.55:
        return "Very close / low confidence"

    if confidence < 0.60:
        return "Slight lean"

    if confidence < 0.65:
        return "Moderate lean"

    if confidence < 0.70:
        return "Strong lean"

    return "High confidence"


@lru_cache(maxsize=1)
def load_current_features() -> pd.DataFrame:
    if not CURRENT_FIGHTER_FEATURES_CSV.exists():
        raise FileNotFoundError(
            f"Missing {CURRENT_FIGHTER_FEATURES_CSV}. "
            "Run build_current_fighter_features.py first."
        )

    df = pd.read_csv(CURRENT_FIGHTER_FEATURES_CSV)
    df["fighter_key"] = df["fighter"].apply(normalize_name)

    return df


@lru_cache(maxsize=1)
def load_model_and_features():
    if not BEST_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Missing {BEST_MODEL_PATH}. "
            "Run train_calibrated_models.py first."
        )

    if not FEATURES_PATH.exists():
        raise FileNotFoundError(
            f"Missing {FEATURES_PATH}. "
            "Run train_calibrated_models.py first."
        )

    model = joblib.load(BEST_MODEL_PATH)

    with open(FEATURES_PATH, "r", encoding="utf-8") as file:
        feature_payload = json.load(file)

    numeric_features = feature_payload["numeric_features"]
    categorical_features = feature_payload["categorical_features"]

    return model, numeric_features, categorical_features


@lru_cache(maxsize=1)
def load_all_prediction_models_and_features():
    """
    Loads every saved winner model plus the feature list used at training time.

    Newer training runs save a model_registry.json and one joblib file per model
    in models/winner_models/. Older projects only have best_winner_model.joblib,
    so this function falls back to that single model when the registry is absent.
    """
    if not FEATURES_PATH.exists():
        raise FileNotFoundError(
            f"Missing {FEATURES_PATH}. "
            "Run train_calibrated_models.py first."
        )

    with open(FEATURES_PATH, "r", encoding="utf-8") as file:
        feature_payload = json.load(file)

    numeric_features = feature_payload["numeric_features"]
    categorical_features = feature_payload["categorical_features"]

    models: dict[str, Any] = {}
    model_metadata: dict[str, Any] = {}
    best_model_name = "best_winner_model"

    if MODEL_REGISTRY_PATH.exists():
        with open(MODEL_REGISTRY_PATH, "r", encoding="utf-8") as file:
            registry_payload = json.load(file)

        best_model_name = clean_text(registry_payload.get("best_model_name", ""))
        registry_models = registry_payload.get("models", {})

        for model_name, metadata in registry_models.items():
            relative_path = clean_text(metadata.get("path", ""))
            model_path = MODELS_DIR / relative_path if relative_path else WINNER_MODELS_DIR / f"{model_name}.joblib"

            if not model_path.exists():
                continue

            models[model_name] = joblib.load(model_path)
            model_metadata[model_name] = metadata

    if not models:
        if not BEST_MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Missing {BEST_MODEL_PATH}. "
                "Run train_calibrated_models.py first."
            )

        models[best_model_name] = joblib.load(BEST_MODEL_PATH)
        model_metadata[best_model_name] = {
            "model_name": best_model_name,
            "path": str(BEST_MODEL_PATH),
            "is_best_model": True,
            "metrics": {},
        }

    return models, model_metadata, best_model_name, numeric_features, categorical_features


def search_fighters(query: str, limit: int = 10) -> list[str]:
    features_df = load_current_features()

    query = clean_text(query)

    if not query:
        return []

    names = features_df["fighter"].dropna().astype(str).tolist()

    exact_contains_matches = [
        name for name in names
        if query.lower() in name.lower()
    ]

    if exact_contains_matches:
        return exact_contains_matches[:limit]

    return get_close_matches(
        query,
        names,
        n=limit,
        cutoff=0.45,
    )


def get_available_weight_classes() -> list[str]:
    # Common UFCStats weight-class labels.
    return [
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
        "Open Weight",
        "Catch Weight",
    ]


def get_fighter_row(features_df: pd.DataFrame, fighter_name: str) -> pd.Series:
    fighter_key = normalize_name(fighter_name)

    matches = features_df[features_df["fighter_key"] == fighter_key]

    if len(matches) == 1:
        return matches.iloc[0]

    if len(matches) > 1:
        return matches.sort_values("prior_fights", ascending=False).iloc[0]

    available_names = features_df["fighter"].dropna().astype(str).tolist()

    suggestions = get_close_matches(
        fighter_name,
        available_names,
        n=8,
        cutoff=0.55,
    )

    raise FighterNotFoundError(
        fighter_name=fighter_name,
        suggestions=suggestions,
    )


@lru_cache(maxsize=1)
def load_weight_size_prediction_context():
    """
    Loads context needed to recalculate weight/size features at prediction time.

    current_fighter_features.csv represents each fighter's latest known feature row.
    For a future matchup, the requested prediction weight class can differ from
    the fighter's most recent historical division. We recalculate these columns
    against the requested matchup division so weight-class movement is modeled
    as transition/context, not as a literal stale body-weight penalty.
    """
    try:
        profiles_df = load_weight_size_fighter_profiles()
        fight_stats_df = load_weight_size_fight_stats()
    except FileNotFoundError:
        return {}, {}, {}

    profile_lookup = build_profile_lookup(profiles_df)
    division_average_lookup = build_division_average_lookup(
        profiles_df=profiles_df,
        fight_stats_df=fight_stats_df,
    )

    historical_classes_by_fighter: dict[str, list[str]] = {}

    for _, fight_row in sorted_fight_stats(fight_stats_df).iterrows():
        fighter = clean_text(fight_row.get("fighter", ""))
        historical_weight_class = clean_text(fight_row.get("weight_class", ""))

        if not fighter or not historical_weight_class:
            continue

        fighter_key = normalize_weight_size_name(fighter)
        historical_classes_by_fighter.setdefault(fighter_key, []).append(historical_weight_class)

    return profile_lookup, division_average_lookup, historical_classes_by_fighter


def apply_prediction_weight_class_context(
    fighter_row: pd.Series,
    prediction_weight_class: str,
) -> pd.Series:
    """
    Returns a copy of a fighter's current feature row adjusted for this matchup's
    requested weight class.

    This keeps height/reach/skill/Elo current, but recalculates columns like
    current_vs_recent_weight_class_lbs_delta using the prediction weight class.
    That way a fighter moving from 170 to 185 is treated as moving up in class,
    not as literally still being a 170 lb fighter in a 185 lb matchup.
    """
    row = fighter_row.copy()
    fighter = clean_text(row.get("fighter", ""))
    prediction_weight_class = clean_text(prediction_weight_class)

    if not fighter or not prediction_weight_class:
        return row

    profile_lookup, division_average_lookup, historical_classes_by_fighter = (
        load_weight_size_prediction_context()
    )

    history = historical_classes_by_fighter.get(
        normalize_weight_size_name(fighter),
        [],
    )

    feature_values = build_weight_size_feature_row(
        fighter=fighter,
        current_weight_class=prediction_weight_class,
        historical_weight_classes=history,
        profile_lookup=profile_lookup,
        division_average_lookup=division_average_lookup,
    )

    for column in WEIGHT_SIZE_FEATURE_COLUMNS:
        if column not in feature_values:
            continue

        value = feature_values[column]
        row[column] = np.nan if value is None else value

    row["weight_class"] = prediction_weight_class

    return row


def build_model_input_row(
    fighter_a_row: pd.Series,
    fighter_b_row: pd.Series,
    weight_class: str,
    numeric_features: list[str],
    categorical_features: list[str],
) -> pd.DataFrame:
    row: dict[str, Any] = {}

    for feature in numeric_features:
        if not feature.startswith("diff_"):
            continue

        base_column = feature.removeprefix("diff_")

        fighter_a_value = optional_float(fighter_a_row.get(base_column))
        fighter_b_value = optional_float(fighter_b_row.get(base_column))

        if fighter_a_value is None or fighter_b_value is None:
            row[feature] = np.nan
        else:
            row[feature] = fighter_a_value - fighter_b_value

    for feature in categorical_features:
        if feature == "weight_class":
            row[feature] = clean_text(weight_class)
        else:
            row[feature] = ""

    feature_order = numeric_features + categorical_features

    return pd.DataFrame([row], columns=feature_order)

def predict_direct_probability(
    model,
    fighter_a_row: pd.Series,
    fighter_b_row: pd.Series,
    weight_class: str,
    numeric_features: list[str],
    categorical_features: list[str],
) -> float:
    model_input = build_model_input_row(
        fighter_a_row=fighter_a_row,
        fighter_b_row=fighter_b_row,
        weight_class=weight_class,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    probability = model.predict_proba(model_input)[0][1]

    return float(probability)


def build_edge(
    label: str,
    fighter_a_value: Any,
    fighter_b_value: Any,
    unit: str = "",
) -> dict[str, Any]:
    a_value = safe_float(fighter_a_value)
    b_value = safe_float(fighter_b_value)

    if a_value is None or b_value is None:
        difference = None
    else:
        difference = a_value - b_value

    return {
        "label": label,
        "fighter_a_value": a_value,
        "fighter_b_value": b_value,
        "difference": difference,
        "unit": unit,
    }


def build_basic_matchup_edges(
    fighter_a_row: pd.Series,
    fighter_b_row: pd.Series,
) -> list[dict[str, Any]]:
    def make_edge(
        label: str,
        column: str,
        unit: str,
    ) -> dict[str, Any]:
        fighter_a_value = optional_float(fighter_a_row.get(column))
        fighter_b_value = optional_float(fighter_b_row.get(column))

        difference = None

        if fighter_a_value is not None and fighter_b_value is not None:
            difference = fighter_a_value - fighter_b_value

        return {
            "label": label,
            "fighter_a_value": fighter_a_value,
            "fighter_b_value": fighter_b_value,
            "difference": difference,
            "unit": unit,
        }

    def should_show_edge(edge: dict[str, Any], minimum_abs_difference: float | None = None) -> bool:
        if minimum_abs_difference is None:
            return True

        difference = edge.get("difference")

        if difference is None or pd.isna(difference):
            return False

        return abs(float(difference)) >= minimum_abs_difference

    core_edges = [
        make_edge(
            label="Elo edge",
            column="prior_elo",
            unit="pts",
        ),
        make_edge(
            label="Experience edge",
            column="prior_fights",
            unit="fights",
        ),
        make_edge(
            label="Win-rate edge",
            column="prior_win_rate",
            unit="",
        ),
        make_edge(
            label="Reach edge",
            column="reach_inches",
            unit="in",
        ),
        make_edge(
            label="Height edge",
            column="height_inches",
            unit="in",
        ),
    ]

    # Visible size edges are limited to actual size/size-for-division context.
    # Weight-class movement remains available to the model as a feature, but it
    # is intentionally hidden from the basic edge list because movement is
    # contextual/uncertain rather than a direct sided advantage.
    conditional_weight_size_edges = [
        (
            make_edge(
                label="Listed weight edge",
                column="listed_weight_lbs",
                unit="lbs",
            ),
            5.0,
        ),
        (
            make_edge(
                label="Size-for-division edge",
                column="listed_weight_vs_weight_class_avg_lbs",
                unit="lbs vs div avg",
            ),
            5.0,
        ),
        (
            make_edge(
                label="Height vs division edge",
                column="height_vs_weight_class_avg_inches",
                unit="in vs div avg",
            ),
            1.5,
        ),
        (
            make_edge(
                label="Reach vs division edge",
                column="reach_vs_weight_class_avg_inches",
                unit="in vs div avg",
            ),
            2.0,
        ),
    ]

    core_edges.extend(
        edge
        for edge, minimum_abs_difference in conditional_weight_size_edges
        if should_show_edge(edge, minimum_abs_difference)
    )

    core_edges.extend(
        [
            make_edge(
                label="Striking differential edge",
                column="avg_sig_str_differential_per_15",
                unit="sig str/15",
            ),
            make_edge(
                label="Takedown differential edge",
                column="avg_td_landed_per_15",
                unit="TD/15",
            ),
            make_edge(
                label="Age edge",
                column="age_years",
                unit="yrs",
            ),
        ]
    )

    return core_edges

def get_edge_by_label(
    edges: list[dict[str, Any]],
    label: str,
) -> dict[str, Any] | None:
    for edge in edges:
        if edge["label"] == label:
            return edge

    return None


def severity_from_value(
    absolute_value: float,
    moderate_threshold: float,
    strong_threshold: float,
) -> str:
    if absolute_value >= strong_threshold:
        return "strong"

    if absolute_value >= moderate_threshold:
        return "moderate"

    return "slight"


def format_signed_value(value: float, unit: str = "") -> str:
    sign = "+" if value > 0 else ""
    formatted_value = f"{sign}{value:.2f}"

    if unit:
        return f"{formatted_value} {unit}"

    return formatted_value

def optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def add_sided_insight(
    insights: dict[str, Any],
    fighter_a: str,
    fighter_b: str,
    edge: dict[str, Any] | None,
    minimum_threshold: float,
    moderate_threshold: float,
    strong_threshold: float,
    title: str,
    advantage_template: str,
    concern_template: str,
) -> None:
    """
    Converts one numeric edge into:
        - a strength for the advantaged fighter
        - a concern for the disadvantaged fighter

    Edges are stored as Fighter A minus Fighter B.
    Positive = Fighter A edge.
    Negative = Fighter B edge.
    """
    if edge is None:
        return

    difference = edge.get("difference")
    unit = edge.get("unit", "")

    if difference is None or pd.isna(difference):
        return

    difference = float(difference)
    absolute_difference = abs(difference)

    if absolute_difference < minimum_threshold:
        return

    severity = severity_from_value(
        absolute_value=absolute_difference,
        moderate_threshold=moderate_threshold,
        strong_threshold=strong_threshold,
    )

    advantaged_fighter = fighter_a if difference > 0 else fighter_b
    disadvantaged_fighter = fighter_b if difference > 0 else fighter_a

    advantaged_key = "fighter_a" if advantaged_fighter == fighter_a else "fighter_b"
    disadvantaged_key = "fighter_a" if disadvantaged_fighter == fighter_a else "fighter_b"

    signed_for_a = format_signed_value(difference, unit)
    signed_for_advantaged = format_signed_value(absolute_difference, unit)

    strength = {
        "title": title,
        "severity": severity,
        "edge_label": edge["label"],
        "value_for_fighter_a": signed_for_a,
        "description": advantage_template.format(
            advantaged_fighter=advantaged_fighter,
            disadvantaged_fighter=disadvantaged_fighter,
            value=signed_for_advantaged,
        ),
    }

    concern = {
        "title": title,
        "severity": severity,
        "edge_label": edge["label"],
        "value_for_fighter_a": signed_for_a,
        "description": concern_template.format(
            advantaged_fighter=advantaged_fighter,
            disadvantaged_fighter=disadvantaged_fighter,
            value=signed_for_advantaged,
        ),
    }

    insights[advantaged_key]["strengths"].append(strength)
    insights[disadvantaged_key]["concerns"].append(concern)


def build_matchup_insights(
    fighter_a: str,
    fighter_b: str,
    predicted_winner: str,
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    insights: dict[str, Any] = {
        "fighter_a": {
            "name": fighter_a,
            "strengths": [],
            "concerns": [],
        },
        "fighter_b": {
            "name": fighter_b,
            "strengths": [],
            "concerns": [],
        },
        "summary": [],
    }

    add_sided_insight(
        insights=insights,
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        edge=get_edge_by_label(edges, "Elo edge"),
        minimum_threshold=10.0,
        moderate_threshold=25.0,
        strong_threshold=50.0,
        title="Overall résumé / Elo edge",
        advantage_template=(
            "{advantaged_fighter} has a {value} Elo advantage, suggesting a stronger "
            "opponent-adjusted UFC résumé."
        ),
        concern_template=(
            "{disadvantaged_fighter} is giving up {value} in Elo, which may suggest "
            "a weaker opponent-adjusted résumé."
        ),
    )

    add_sided_insight(
        insights=insights,
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        edge=get_edge_by_label(edges, "Experience edge"),
        minimum_threshold=3.0,
        moderate_threshold=7.0,
        strong_threshold=12.0,
        title="UFC experience edge",
        advantage_template=(
            "{advantaged_fighter} has {value} more UFC fights, which may help with "
            "pace, composure, and familiarity with UFC-level opposition."
        ),
        concern_template=(
            "{disadvantaged_fighter} has {value} fewer UFC fights, so experience may "
            "be a concern."
        ),
    )

    add_sided_insight(
        insights=insights,
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        edge=get_edge_by_label(edges, "Win-rate edge"),
        minimum_threshold=0.05,
        moderate_threshold=0.10,
        strong_threshold=0.18,
        title="Historical win-rate edge",
        advantage_template=(
            "{advantaged_fighter} has a {value} win-rate edge in prior UFC fights."
        ),
        concern_template=(
            "{disadvantaged_fighter} trails by {value} in prior UFC win rate."
        ),
    )

    add_sided_insight(
        insights=insights,
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        edge=get_edge_by_label(edges, "Reach edge"),
        minimum_threshold=1.0,
        moderate_threshold=2.0,
        strong_threshold=4.0,
        title="Reach advantage",
        advantage_template=(
            "{advantaged_fighter} has a {value} reach advantage, which may help with "
            "range management and striking entries."
        ),
        concern_template=(
            "{disadvantaged_fighter} gives up {value} in reach, which may make range "
            "management harder."
        ),
    )

    add_sided_insight(
        insights=insights,
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        edge=get_edge_by_label(edges, "Height edge"),
        minimum_threshold=2.0,
        moderate_threshold=3.0,
        strong_threshold=5.0,
        title="Height advantage",
        advantage_template=(
            "{advantaged_fighter} has a {value} height advantage, which can matter "
            "for range, clinch frames, and defensive looks."
        ),
        concern_template=(
            "{disadvantaged_fighter} gives up {value} in height."
        ),
    )

    add_sided_insight(
        insights=insights,
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        edge=get_edge_by_label(edges, "Listed weight edge"),
        minimum_threshold=5.0,
        moderate_threshold=10.0,
        strong_threshold=20.0,
        title="Listed weight / size edge",
        advantage_template=(
            "{advantaged_fighter} is listed {value} heavier, which may indicate a "
            "size or strength edge if the listed weights are accurate."
        ),
        concern_template=(
            "{disadvantaged_fighter} is listed {value} lighter, which may matter in "
            "physical exchanges, clinches, and grappling sequences."
        ),
    )

    add_sided_insight(
        insights=insights,
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        edge=get_edge_by_label(edges, "Size-for-division edge"),
        minimum_threshold=5.0,
        moderate_threshold=10.0,
        strong_threshold=20.0,
        title="Size relative to division",
        advantage_template=(
            "{advantaged_fighter} profiles {value} larger relative to the division average, "
            "which may point to a size-for-weight-class advantage."
        ),
        concern_template=(
            "{disadvantaged_fighter} profiles {value} smaller relative to the division average."
        ),
    )

    add_sided_insight(
        insights=insights,
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        edge=get_edge_by_label(edges, "Height vs division edge"),
        minimum_threshold=1.5,
        moderate_threshold=2.5,
        strong_threshold=4.0,
        title="Height relative to division",
        advantage_template=(
            "{advantaged_fighter} is {value} taller relative to the division average, "
            "which can support range, clinch frames, and defensive looks."
        ),
        concern_template=(
            "{disadvantaged_fighter} is {value} shorter relative to the division average."
        ),
    )

    add_sided_insight(
        insights=insights,
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        edge=get_edge_by_label(edges, "Reach vs division edge"),
        minimum_threshold=2.0,
        moderate_threshold=3.0,
        strong_threshold=5.0,
        title="Reach relative to division",
        advantage_template=(
            "{advantaged_fighter} is {value} longer relative to the division average, "
            "which may help with distance management."
        ),
        concern_template=(
            "{disadvantaged_fighter} is {value} shorter in reach relative to the division average."
        ),
    )


    add_sided_insight(
        insights=insights,
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        edge=get_edge_by_label(edges, "Striking differential edge"),
        minimum_threshold=5.0,
        moderate_threshold=12.0,
        strong_threshold=25.0,
        title="Striking differential edge",
        advantage_template=(
            "{advantaged_fighter} has a {value} striking differential edge per 15 minutes, "
            "suggesting better historical striking output versus absorption."
        ),
        concern_template=(
            "{disadvantaged_fighter} trails by {value} in striking differential per 15 minutes."
        ),
    )

    add_sided_insight(
        insights=insights,
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        edge=get_edge_by_label(edges, "Takedown differential edge"),
        minimum_threshold=0.30,
        moderate_threshold=0.75,
        strong_threshold=1.50,
        title="Wrestling / takedown edge",
        advantage_template=(
            "{advantaged_fighter} has a {value} takedown edge per 15 minutes, which may "
            "point to a grappling-control advantage."
        ),
        concern_template=(
            "{disadvantaged_fighter} trails by {value} in takedowns per 15 minutes, which "
            "could be a grappling-control concern."
        ),
    )

    predicted_key = "fighter_a" if predicted_winner == fighter_a else "fighter_b"
    other_key = "fighter_b" if predicted_key == "fighter_a" else "fighter_a"

    predicted_strengths = insights[predicted_key]["strengths"]
    predicted_concerns = insights[predicted_key]["concerns"]
    other_strengths = insights[other_key]["strengths"]

    used_edge_labels = set()

    if predicted_strengths:
        top_strength = predicted_strengths[0]
        used_edge_labels.add(top_strength["edge_label"])

        insights["summary"].append(
            {
                "type": "supporting_reason",
                "text": (
                    f"Main support for {predicted_winner}: "
                    f"{top_strength['description']}"
                ),
            }
        )

    if predicted_concerns:
        top_concern = predicted_concerns[0]
        used_edge_labels.add(top_concern["edge_label"])

        insights["summary"].append(
            {
                "type": "caution",
                "text": (
                    f"Important caution for {predicted_winner}: "
                    f"{top_concern['description']}"
                ),
            }
        )

    unique_opposing_strength = None

    for strength in other_strengths:
        if strength["edge_label"] not in used_edge_labels:
            unique_opposing_strength = strength
            break

    if unique_opposing_strength is not None:
        insights["summary"].append(
            {
                "type": "opposing_path",
                "text": (
                    f"Additional path for the opponent: "
                    f"{unique_opposing_strength['description']}"
                ),
            }
        )

    if not insights["summary"]:
        insights["summary"].append(
            {
                "type": "close_fight",
                "text": (
                    "The model did not find many large statistical edges from the current "
                    "explanation rules, so this appears closer from the available data."
                ),
            }
        )
    return insights

def predict_fight_data_for_model(
    fighter_a: str,
    fighter_b: str,
    weight_class: str,
    model_name: str,
    model,
    numeric_features: list[str],
    categorical_features: list[str],
    include_explanations: bool = False,
) -> dict[str, Any]:
    features_df = load_current_features()

    fighter_a_row = get_fighter_row(features_df, fighter_a)
    fighter_b_row = get_fighter_row(features_df, fighter_b)

    fighter_a_row = apply_prediction_weight_class_context(
        fighter_row=fighter_a_row,
        prediction_weight_class=weight_class,
    )
    fighter_b_row = apply_prediction_weight_class_context(
        fighter_row=fighter_b_row,
        prediction_weight_class=weight_class,
    )

    fighter_a_direct_probability = predict_direct_probability(
        model=model,
        fighter_a_row=fighter_a_row,
        fighter_b_row=fighter_b_row,
        weight_class=weight_class,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    fighter_b_direct_probability = predict_direct_probability(
        model=model,
        fighter_a_row=fighter_b_row,
        fighter_b_row=fighter_a_row,
        weight_class=weight_class,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    total = fighter_a_direct_probability + fighter_b_direct_probability

    if total <= 0:
        fighter_a_probability = fighter_a_direct_probability
        fighter_b_probability = 1.0 - fighter_a_probability
    else:
        fighter_a_probability = fighter_a_direct_probability / total
        fighter_b_probability = fighter_b_direct_probability / total

    confidence = max(fighter_a_probability, fighter_b_probability)

    fighter_a_clean = clean_text(fighter_a_row["fighter"])
    fighter_b_clean = clean_text(fighter_b_row["fighter"])

    predicted_winner = (
        fighter_a_clean
        if fighter_a_probability >= fighter_b_probability
        else fighter_b_clean
    )

    prediction_payload: dict[str, Any] = {
        "model_name": model_name,
        "fighter_a": fighter_a_clean,
        "fighter_b": fighter_b_clean,
        "weight_class": weight_class,
        "fighter_a_probability": fighter_a_probability,
        "fighter_b_probability": fighter_b_probability,
        "fighter_a_percentage": format_percent(fighter_a_probability),
        "fighter_b_percentage": format_percent(fighter_b_probability),
        "fighter_a_direct_score": fighter_a_direct_probability,
        "fighter_b_direct_score": fighter_b_direct_probability,
        "predicted_winner": predicted_winner,
        "confidence": confidence,
        "confidence_percentage": format_percent(confidence),
        "confidence_label": get_confidence_label(confidence),
    }

    if include_explanations:
        basic_matchup_edges = build_basic_matchup_edges(
            fighter_a_row=fighter_a_row,
            fighter_b_row=fighter_b_row,
        )

        matchup_insights = build_matchup_insights(
            fighter_a=fighter_a_clean,
            fighter_b=fighter_b_clean,
            predicted_winner=predicted_winner,
            edges=basic_matchup_edges,
        )

        prediction_payload["basic_matchup_edges"] = basic_matchup_edges
        prediction_payload["matchup_insights"] = matchup_insights

    return prediction_payload


def build_probability_prediction_payload(
    *,
    model_name: str,
    fighter_a: str,
    fighter_b: str,
    weight_class: str,
    fighter_a_probability: float,
    fighter_b_probability: float,
    fighter_a_direct_score: float | None = None,
    fighter_b_direct_score: float | None = None,
) -> dict[str, Any]:
    fighter_a_probability = float(np.clip(fighter_a_probability, 0.0, 1.0))
    fighter_b_probability = float(np.clip(fighter_b_probability, 0.0, 1.0))

    total = fighter_a_probability + fighter_b_probability

    if total > 0:
        fighter_a_probability = fighter_a_probability / total
        fighter_b_probability = fighter_b_probability / total
    else:
        fighter_a_probability = 0.5
        fighter_b_probability = 0.5

    confidence = max(fighter_a_probability, fighter_b_probability)

    predicted_winner = (
        fighter_a
        if fighter_a_probability >= fighter_b_probability
        else fighter_b
    )

    return {
        "model_name": model_name,
        "fighter_a": fighter_a,
        "fighter_b": fighter_b,
        "weight_class": weight_class,
        "fighter_a_probability": fighter_a_probability,
        "fighter_b_probability": fighter_b_probability,
        "fighter_a_percentage": format_percent(fighter_a_probability),
        "fighter_b_percentage": format_percent(fighter_b_probability),
        "fighter_a_direct_score": (
            fighter_a_probability
            if fighter_a_direct_score is None
            else fighter_a_direct_score
        ),
        "fighter_b_direct_score": (
            fighter_b_probability
            if fighter_b_direct_score is None
            else fighter_b_direct_score
        ),
        "predicted_winner": predicted_winner,
        "confidence": confidence,
        "confidence_percentage": format_percent(confidence),
        "confidence_label": get_confidence_label(confidence),
    }


def calculate_elo_probability(
    fighter_a_elo: float | None,
    fighter_b_elo: float | None,
) -> float:
    """
    Standard Elo expected-score probability.

    Missing Elo values fall back to 1500 so the baseline remains available
    even for fighters with limited historical data.
    """
    fighter_a_elo = 1500.0 if fighter_a_elo is None else float(fighter_a_elo)
    fighter_b_elo = 1500.0 if fighter_b_elo is None else float(fighter_b_elo)

    return 1.0 / (1.0 + 10.0 ** ((fighter_b_elo - fighter_a_elo) / 400.0))


def predict_elo_baseline(
    fighter_a: str,
    fighter_b: str,
    weight_class: str,
) -> dict[str, Any]:
    """
    Simple non-ML benchmark based only on current prior Elo.

    This is intentionally included in all-model snapshots so the trained
    models can be compared against a transparent baseline over future fights.
    """
    features_df = load_current_features()

    fighter_a_row = get_fighter_row(features_df, fighter_a)
    fighter_b_row = get_fighter_row(features_df, fighter_b)

    fighter_a_row = apply_prediction_weight_class_context(
        fighter_row=fighter_a_row,
        prediction_weight_class=weight_class,
    )
    fighter_b_row = apply_prediction_weight_class_context(
        fighter_row=fighter_b_row,
        prediction_weight_class=weight_class,
    )

    fighter_a_clean = clean_text(fighter_a_row["fighter"])
    fighter_b_clean = clean_text(fighter_b_row["fighter"])

    fighter_a_elo = optional_float(fighter_a_row.get("prior_elo"))
    fighter_b_elo = optional_float(fighter_b_row.get("prior_elo"))

    fighter_a_probability = calculate_elo_probability(
        fighter_a_elo=fighter_a_elo,
        fighter_b_elo=fighter_b_elo,
    )

    return build_probability_prediction_payload(
        model_name="elo_baseline",
        fighter_a=fighter_a_clean,
        fighter_b=fighter_b_clean,
        weight_class=clean_text(weight_class),
        fighter_a_probability=fighter_a_probability,
        fighter_b_probability=1.0 - fighter_a_probability,
    )


def build_ensemble_average_prediction(
    model_predictions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Average a stable set of model probabilities into one ensemble prediction.

    We prefer calibrated models plus the Elo baseline. If those are not
    available for some reason, we fall back to all non-ensemble predictions.
    """
    if not model_predictions:
        return None

    preferred_model_names = [
        "calibrated_logistic_regression",
        "calibrated_random_forest",
        "calibrated_extra_trees",
        "calibrated_hist_gradient_boosting",
        "calibrated_xgboost",
        "elo_baseline",
    ]

    predictions_by_name = {
        clean_text(prediction.get("model_name", "")): prediction
        for prediction in model_predictions
    }

    selected_predictions = [
        predictions_by_name[model_name]
        for model_name in preferred_model_names
        if model_name in predictions_by_name
    ]

    if not selected_predictions:
        selected_predictions = [
            prediction
            for prediction in model_predictions
            if clean_text(prediction.get("model_name", "")) != "ensemble_average"
        ]

    fighter_a_probabilities = [
        optional_float(prediction.get("fighter_a_probability"))
        for prediction in selected_predictions
    ]
    fighter_b_probabilities = [
        optional_float(prediction.get("fighter_b_probability"))
        for prediction in selected_predictions
    ]

    fighter_a_probabilities = [
        value for value in fighter_a_probabilities if value is not None
    ]
    fighter_b_probabilities = [
        value for value in fighter_b_probabilities if value is not None
    ]

    if not fighter_a_probabilities or not fighter_b_probabilities:
        return None

    first_prediction = selected_predictions[0]
    fighter_a_probability = float(np.mean(fighter_a_probabilities))
    fighter_b_probability = float(np.mean(fighter_b_probabilities))

    ensemble_prediction = build_probability_prediction_payload(
        model_name="ensemble_average",
        fighter_a=clean_text(first_prediction.get("fighter_a", "")),
        fighter_b=clean_text(first_prediction.get("fighter_b", "")),
        weight_class=clean_text(first_prediction.get("weight_class", "")),
        fighter_a_probability=fighter_a_probability,
        fighter_b_probability=fighter_b_probability,
    )

    ensemble_prediction["ensemble_members"] = [
        clean_text(prediction.get("model_name", ""))
        for prediction in selected_predictions
    ]

    return ensemble_prediction


def predict_fight_data(
    fighter_a: str,
    fighter_b: str,
    weight_class: str,
) -> dict[str, Any]:
    model, numeric_features, categorical_features = load_model_and_features()

    return predict_fight_data_for_model(
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        weight_class=weight_class,
        model_name="best_winner_model",
        model=model,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        include_explanations=True,
    )


def predict_fight_all_models(
    fighter_a: str,
    fighter_b: str,
    weight_class: str,
) -> dict[str, Any]:
    models, model_metadata, best_model_name, numeric_features, categorical_features = (
        load_all_prediction_models_and_features()
    )

    model_predictions = []

    for model_name, model in sorted(models.items()):
        prediction = predict_fight_data_for_model(
            fighter_a=fighter_a,
            fighter_b=fighter_b,
            weight_class=weight_class,
            model_name=model_name,
            model=model,
            numeric_features=numeric_features,
            categorical_features=categorical_features,
            include_explanations=False,
        )

        prediction["is_best_model"] = model_name == best_model_name
        prediction["model_metrics"] = model_metadata.get(model_name, {}).get("metrics", {})
        model_predictions.append(prediction)

    elo_prediction = predict_elo_baseline(
        fighter_a=fighter_a,
        fighter_b=fighter_b,
        weight_class=weight_class,
    )
    elo_prediction["is_best_model"] = False
    elo_prediction["model_metrics"] = {
        "model_type": "baseline",
        "description": "Standard Elo expected-score probability using prior_elo.",
    }
    model_predictions.append(elo_prediction)

    ensemble_prediction = build_ensemble_average_prediction(model_predictions)

    if ensemble_prediction is not None:
        ensemble_prediction["is_best_model"] = False
        ensemble_prediction["model_metrics"] = {
            "model_type": "ensemble",
            "description": "Average of calibrated model probabilities plus Elo baseline when available.",
            "members": ensemble_prediction.get("ensemble_members", []),
        }
        model_predictions.append(ensemble_prediction)

    return {
        "fighter_a": clean_text(fighter_a),
        "fighter_b": clean_text(fighter_b),
        "weight_class": clean_text(weight_class),
        "best_model_name": best_model_name,
        "model_count": len(model_predictions),
        "model_predictions": model_predictions,
    }

def clear_prediction_cache() -> None:
    """
    Clears cached model/current-feature data after retraining or rebuilding data.

    This matters when the API server is already running and we update files.
    Without clearing these caches, the API may keep using the old model/data.
    """
    load_current_features.cache_clear()
    load_model_and_features.cache_clear()
    load_weight_size_prediction_context.cache_clear()