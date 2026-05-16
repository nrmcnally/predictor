from __future__ import annotations

import json
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"

CURRENT_FIGHTER_FEATURES_CSV = PROCESSED_DATA_DIR / "current_fighter_features.csv"
BEST_MODEL_PATH = MODELS_DIR / "best_winner_model.joblib"
FEATURES_PATH = MODELS_DIR / "model_features.json"


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

        fighter_a_value = fighter_a_row.get(base_column, pd.NA)
        fighter_b_value = fighter_b_row.get(base_column, pd.NA)

        row[feature] = fighter_a_value - fighter_b_value

    for feature in categorical_features:
        if feature == "weight_class":
            row[feature] = weight_class
        else:
            row[feature] = pd.NA

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
    
    return [
        build_edge(
            label="Elo edge",
            fighter_a_value=fighter_a_row.get("prior_elo", pd.NA),
            fighter_b_value=fighter_b_row.get("prior_elo", pd.NA),
            unit="pts",
        ),
        build_edge(
            label="Experience edge",
            fighter_a_value=fighter_a_row.get("prior_fights", pd.NA),
            fighter_b_value=fighter_b_row.get("prior_fights", pd.NA),
            unit="fights",
        ),
        build_edge(
            label="Win-rate edge",
            fighter_a_value=fighter_a_row.get("prior_win_rate", pd.NA),
            fighter_b_value=fighter_b_row.get("prior_win_rate", pd.NA),
        ),
        build_edge(
            label="Reach edge",
            fighter_a_value=fighter_a_row.get("reach_inches", pd.NA),
            fighter_b_value=fighter_b_row.get("reach_inches", pd.NA),
            unit="in",
        ),
        build_edge(
            label="Height edge",
            fighter_a_value=fighter_a_row.get("height_inches", pd.NA),
            fighter_b_value=fighter_b_row.get("height_inches", pd.NA),
            unit="in",
        ),
        build_edge(
            label="Striking differential edge",
            fighter_a_value=fighter_a_row.get("avg_sig_str_differential_per_15", pd.NA),
            fighter_b_value=fighter_b_row.get("avg_sig_str_differential_per_15", pd.NA),
            unit="sig str/15",
        ),
        build_edge(
            label="Takedown differential edge",
            fighter_a_value=fighter_a_row.get("avg_td_landed_per_15", pd.NA),
            fighter_b_value=fighter_b_row.get("avg_td_landed_per_15", pd.NA),
            unit="TD/15",
        ),
    ]

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

def predict_fight_data(
    fighter_a: str,
    fighter_b: str,
    weight_class: str,
) -> dict[str, Any]:
    features_df = load_current_features()
    model, numeric_features, categorical_features = load_model_and_features()

    fighter_a_row = get_fighter_row(features_df, fighter_a)
    fighter_b_row = get_fighter_row(features_df, fighter_b)

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

    return {
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
        "basic_matchup_edges": basic_matchup_edges,
        "matchup_insights": matchup_insights,
    }

def clear_prediction_cache() -> None:
    """
    Clears cached model/current-feature data after retraining or rebuilding data.

    This matters when the API server is already running and we update files.
    Without clearing these caches, the API may keep using the old model/data.
    """
    load_current_features.cache_clear()
    load_model_and_features.cache_clear()