from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.services.prediction_grading import (
    brier_for_outcome,
    build_edge_analysis,
    fight_quality,
    grade_predictions,
)
from app.models.model_version import (
    MODEL_VERSION,
    estimate_version_for_date,
    load_current_provenance,
)
from app.repositories import event_fights_repository, saved_predictions_repository


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

EVENT_FIGHTS_CSV = RAW_DATA_DIR / "event_fights.csv"
SAVED_CARD_PREDICTIONS_CSV = PROCESSED_DATA_DIR / "saved_card_predictions.csv"


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def normalize_fight_url(value: Any) -> str:
    if value is None:
        return ""

    normalized = " ".join(str(value).split())

    normalized = normalized.replace("https://www.", "https://")
    normalized = normalized.replace("http://www.", "http://")

    return normalized.rstrip("/")

def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    value_text = clean_text(value).lower()

    return value_text in {"true", "1", "yes"}


def classify_actual_outcome(row: pd.Series) -> str:
    winner = clean_text(row.get("winner", ""))

    if winner:
        return "winner"

    result_1 = clean_text(row.get("result_1", ""))
    result_2 = clean_text(row.get("result_2", ""))
    method = clean_text(row.get("method", ""))

    combined = f"{result_1} {result_2} {method}".lower()
    combined = combined.replace(".", "").replace("-", " ")

    if "no contest" in combined or "overturned" in combined:
        return "no_contest"

    if "nc" in set(combined.split()):
        return "no_contest"

    return ""


def optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None

def read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def make_event_id_from_url(event_url: Any) -> str:
    event_url = clean_text(event_url)

    if not event_url:
        return ""

    return event_url.rstrip("/").split("/")[-1]


def load_saved_predictions() -> pd.DataFrame:
    return saved_predictions_repository.read_all_df()


def load_actual_results() -> pd.DataFrame:
    return event_fights_repository.read_all_df()


def build_actual_result_lookup(event_fights_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """
    Builds a lookup by fight_url.

    event_fights.csv contains completed fight rows with winner/loser.
    saved_card_predictions.csv contains the future-card fight_url.
    So fight_url is the cleanest join key.
    """
    if event_fights_df.empty:
        return {}

    required_columns = {"fight_url"}

    if not required_columns.issubset(event_fights_df.columns):
        return {}

    df = event_fights_df.copy()

    for column in ["winner", "loser", "result_1", "result_2", "method"]:
        if column not in df.columns:
            df[column] = ""

    df["winner_clean"] = df["winner"].apply(clean_text)
    df["loser_clean"] = df["loser"].apply(clean_text)
    df["actual_outcome"] = df.apply(classify_actual_outcome, axis=1)

    df = df[
        (df["winner_clean"] != "")
        | (df["actual_outcome"] != "")
    ].copy()

    lookup: dict[str, dict[str, Any]] = {}

    for _, row in df.iterrows():
        fight_url = normalize_fight_url(row.get("fight_url", ""))

        if not fight_url:
            continue

        lookup[fight_url] = {
            "event_id": make_event_id_from_url(row.get("event_url", "")),
            "event_name": clean_text(row.get("event_name", "")),
            "event_date": clean_text(row.get("event_date", "")),
            "event_location": clean_text(row.get("event_location", "")),
            "fight_url": fight_url,
            "fighter_1": clean_text(row.get("fighter_1", "")),
            "fighter_2": clean_text(row.get("fighter_2", "")),
            "result_1": clean_text(row.get("result_1", "")),
            "result_2": clean_text(row.get("result_2", "")),
            "winner": clean_text(row.get("winner", "")),
            "loser": clean_text(row.get("loser", "")),
            "method": clean_text(row.get("method", "")),
            "round": clean_text(row.get("round", "")),
            "time": clean_text(row.get("time", "")),
            "weight_class": clean_text(row.get("weight_class", "")),
            "actual_outcome": clean_text(row.get("actual_outcome", "")),
        }

    return lookup


def build_completed_event_url_lookup(event_fights_df: pd.DataFrame) -> set[str]:
    if event_fights_df.empty or "event_url" not in event_fights_df.columns:
        return set()

    return set(
        event_fights_df["event_url"]
        .dropna()
        .apply(normalize_fight_url)
    )


def build_fight_result_row(
    saved_row: pd.Series,
    actual_lookup: dict[str, dict[str, Any]],
    completed_event_urls: set[str],
) -> dict[str, Any]:
    fight_url = normalize_fight_url(saved_row.get("fight_url", ""))
    event_url = normalize_fight_url(saved_row.get("event_url", ""))
    actual = actual_lookup.get(fight_url)

    prediction_available = parse_bool(saved_row.get("prediction_available", False))
    predicted_winner = clean_text(saved_row.get("predicted_winner", ""))

    actual_winner = ""
    actual_loser = ""
    actual_method = ""
    actual_round = ""
    actual_time = ""
    actual_outcome = ""

    if actual is not None:
        actual_winner = clean_text(actual.get("winner", ""))
        actual_loser = clean_text(actual.get("loser", ""))
        actual_method = clean_text(actual.get("method", ""))
        actual_round = clean_text(actual.get("round", ""))
        actual_time = clean_text(actual.get("time", ""))
        actual_outcome = clean_text(actual.get("actual_outcome", ""))
    elif event_url and event_url in completed_event_urls:
        actual_outcome = "cancelled"

    actual_result_available = bool(actual_winner or actual_outcome)

    prediction_correct = None

    if prediction_available and actual_winner and predicted_winner:
        prediction_correct = predicted_winner == actual_winner

    odds_available = parse_bool(saved_row.get("odds_available", False))
    market_favorite = clean_text(saved_row.get("market_favorite", ""))

    market_correct = None

    if odds_available and actual_winner and market_favorite:
        market_correct = market_favorite == actual_winner

    # Probability-aware grading: how much probability did each side place on the
    # fighter who actually won?
    fighter_1_name = clean_text(saved_row.get("fighter_1", ""))
    fighter_2_name = clean_text(saved_row.get("fighter_2", ""))
    actual_winner_clean = clean_text(actual_winner)

    fighter_1_probability = optional_float(saved_row.get("fighter_1_probability"))
    fighter_2_probability = optional_float(saved_row.get("fighter_2_probability"))
    model_confidence = optional_float(saved_row.get("confidence"))

    fighter_1_market_probability = optional_float(saved_row.get("fighter_1_market_probability"))
    fighter_2_market_probability = optional_float(saved_row.get("fighter_2_market_probability"))

    model_p_winner = None
    market_p_winner = None

    if actual_winner_clean and prediction_available:
        if actual_winner_clean == fighter_1_name:
            model_p_winner = fighter_1_probability
        elif actual_winner_clean == fighter_2_name:
            model_p_winner = fighter_2_probability

    if actual_winner_clean and odds_available:
        if actual_winner_clean == fighter_1_name:
            market_p_winner = fighter_1_market_probability
        elif actual_winner_clean == fighter_2_name:
            market_p_winner = fighter_2_market_probability

    model_brier = brier_for_outcome(model_p_winner) if model_p_winner is not None else None
    model_quality = fight_quality(model_p_winner) if model_p_winner is not None else None

    # Did the model pick the same fighter the market favored? Edge can only exist
    # where these disagree.
    agree_with_market = None
    if odds_available and predicted_winner and market_favorite:
        agree_with_market = predicted_winner == market_favorite

    return {
        "saved_at": clean_text(saved_row.get("saved_at", "")),

        "fight_id": clean_text(saved_row.get("fight_id", "")),
        "fight_url": fight_url,
        "fighter_1": clean_text(saved_row.get("fighter_1", "")),
        "fighter_2": clean_text(saved_row.get("fighter_2", "")),
        "weight_class": clean_text(saved_row.get("weight_class", "")),
        "scheduled_rounds": optional_int(saved_row.get("scheduled_rounds")),
        "is_main_event": parse_bool(saved_row.get("is_main_event", False)),

        "prediction_available": prediction_available,
        "predicted_winner": predicted_winner,
        "fighter_1_percentage": clean_text(saved_row.get("fighter_1_percentage", "")),
        "fighter_2_percentage": clean_text(saved_row.get("fighter_2_percentage", "")),
        "confidence_percentage": clean_text(saved_row.get("confidence_percentage", "")),
        "confidence_label": clean_text(saved_row.get("confidence_label", "")),
        "model_name": clean_text(saved_row.get("model_name", "")),
        "model_version": clean_text(saved_row.get("model_version", "")),
        "model_recipe_hash": clean_text(saved_row.get("model_recipe_hash", "")),

        "fighter_1_probability": fighter_1_probability,
        "fighter_2_probability": fighter_2_probability,
        "model_confidence": model_confidence,
        "model_p_winner": model_p_winner,
        "model_brier": model_brier,
        "model_quality": model_quality,
        "market_p_winner": market_p_winner,
        "agree_with_market": agree_with_market,

        "actual_result_available": actual_result_available,
        "actual_winner": actual_winner,
        "actual_loser": actual_loser,
        "actual_method": actual_method,
        "actual_round": actual_round,
        "actual_time": actual_time,
        "actual_outcome": actual_outcome,
        "actual_is_no_contest": actual_outcome == "no_contest",
        "actual_is_cancelled": actual_outcome == "cancelled",

        "prediction_correct": prediction_correct,

        # Saved market odds snapshot
        "odds_available": odds_available,
        "odds_bookmaker": clean_text(saved_row.get("odds_bookmaker", "")),
        "odds_last_update": clean_text(saved_row.get("odds_last_update", "")),
        "bookmakers_matched": optional_int(saved_row.get("bookmakers_matched")),

        "fighter_1_odds_american": optional_int(
            saved_row.get("fighter_1_odds_american")
        ),
        "fighter_2_odds_american": optional_int(
            saved_row.get("fighter_2_odds_american")
        ),

        "fighter_1_market_probability": optional_float(
            saved_row.get("fighter_1_market_probability")
        ),
        "fighter_2_market_probability": optional_float(
            saved_row.get("fighter_2_market_probability")
        ),
        "fighter_1_market_percentage": clean_text(
            saved_row.get("fighter_1_market_percentage", "")
        ),
        "fighter_2_market_percentage": clean_text(
            saved_row.get("fighter_2_market_percentage", "")
        ),

        "market_favorite": market_favorite,
        "market_favorite_probability": optional_float(
            saved_row.get("market_favorite_probability")
        ),
        "market_favorite_percentage": clean_text(
            saved_row.get("market_favorite_percentage", "")
        ),
        "market_correct": market_correct,

        "error_json": clean_text(saved_row.get("error_json", "")),
    }


def build_grading_entries(fights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One grading entry per scored, predicted fight (used per-card and overall)."""
    entries: list[dict[str, Any]] = []

    for fight in fights:
        if not fight.get("actual_result_available") or not fight.get("prediction_available"):
            continue
        if fight.get("model_p_winner") is None:
            continue

        entries.append(
            {
                "model_p_winner": fight.get("model_p_winner"),
                "model_confidence": fight.get("model_confidence"),
                "model_correct": fight.get("prediction_correct"),
                "market_p_winner": fight.get("market_p_winner"),
                "market_correct": fight.get("market_correct"),
                "agree_with_market": fight.get("agree_with_market"),
            }
        )

    return entries


def summarize_card_fights(fights: list[dict[str, Any]]) -> dict[str, Any]:
    completed_fights = [
        fight for fight in fights
        if fight["actual_result_available"]
    ]

    predicted_completed_fights = [
        fight for fight in completed_fights
        if fight["prediction_available"] and fight["prediction_correct"] is not None
    ]

    correct_predictions = [
        fight for fight in predicted_completed_fights
        if fight["prediction_correct"] is True
    ]

    market_completed_fights = [
        fight for fight in completed_fights
        if fight.get("odds_available") and fight.get("market_correct") is not None
    ]

    correct_market_favorites = [
        fight for fight in market_completed_fights
        if fight["market_correct"] is True
    ]

    if not completed_fights:
        status = "waiting_for_results"
    elif len(completed_fights) < len(fights):
        status = "partially_completed"
    else:
        status = "completed"

    accuracy = None

    if predicted_completed_fights:
        accuracy = len(correct_predictions) / len(predicted_completed_fights)

    market_accuracy = None

    if market_completed_fights:
        market_accuracy = len(correct_market_favorites) / len(market_completed_fights)

    return {
        "status": status,
        "fight_count": len(fights),
        "actual_result_count": len(completed_fights),
        "predicted_completed_count": len(predicted_completed_fights),
        "correct_prediction_count": len(correct_predictions),
        "accuracy": accuracy,
        "accuracy_percentage": f"{accuracy * 100.0:.1f}%" if accuracy is not None else "",
        "market_completed_count": len(market_completed_fights),
        "correct_market_count": len(correct_market_favorites),
        "market_accuracy": market_accuracy,
        "market_accuracy_percentage": f"{market_accuracy * 100.0:.1f}%"
        if market_accuracy is not None
        else "",
        "grading": grade_predictions(build_grading_entries(fights)),
    }


def get_recent_cards(include_waiting: bool = True) -> dict[str, Any]:
    saved_df = load_saved_predictions()
    event_fights_df = load_actual_results()

    if saved_df.empty:
        return {
            "card_count": 0,
            "cards": [],
        }

    actual_lookup = build_actual_result_lookup(event_fights_df)
    completed_event_urls = build_completed_event_url_lookup(event_fights_df)

    cards: list[dict[str, Any]] = []

    current_provenance = load_current_provenance()
    current_recipe = clean_text(current_provenance.get("recipe_hash", ""))
    current_version = clean_text(current_provenance.get("model_version", "")) or MODEL_VERSION

    for event_id, card_df in saved_df.groupby("event_id", sort=False):
        first_row = card_df.iloc[0]

        fights = [
            build_fight_result_row(
                saved_row=row,
                actual_lookup=actual_lookup,
                completed_event_urls=completed_event_urls,
            )
            for _, row in card_df.iterrows()
        ]

        summary = summarize_card_fights(fights)

        if not include_waiting and summary["status"] == "waiting_for_results":
            continue

        snapshot_recipe = next(
            (f["model_recipe_hash"] for f in fights if f.get("model_recipe_hash")), ""
        )
        snapshot_version = next(
            (f["model_version"] for f in fights if f.get("model_version")), ""
        )
        version_estimated = False

        if snapshot_recipe:
            snapshot_generation = (
                "current" if current_recipe and snapshot_recipe == current_recipe else "older"
            )
        else:
            # Snapshot predates provenance stamping: estimate its version from when
            # it was saved, against the recipe history.
            snapshot_version = estimate_version_for_date(clean_text(first_row.get("saved_at", "")))
            version_estimated = True

            if not snapshot_version:
                snapshot_generation = "unknown"
            else:
                snapshot_generation = "current" if snapshot_version == current_version else "older"

        cards.append(
            {
                "event_id": clean_text(event_id),
                "event_name": clean_text(first_row.get("event_name", "")),
                "event_date": clean_text(first_row.get("event_date", "")),
                "event_location": clean_text(first_row.get("event_location", "")),
                "event_url": clean_text(first_row.get("event_url", "")),
                "saved_at": clean_text(first_row.get("saved_at", "")),
                "snapshot_model_version": snapshot_version,
                "snapshot_generation": snapshot_generation,
                "snapshot_version_estimated": version_estimated,
                **summary,
                "fights": fights,
            }
        )

    cards = sorted(
        cards,
        key=lambda card: pd.to_datetime(card["event_date"], errors="coerce"),
        reverse=True,
    )

    # Overall = every scored fight across every card. This is the statistically
    # meaningful grade; any single card (~10 fights) is mostly variance.
    overall_entries: list[dict[str, Any]] = []
    for card in cards:
        overall_entries.extend(build_grading_entries(card["fights"]))

    overall = grade_predictions(overall_entries)
    overall["graded_card_count"] = sum(
        1 for card in cards if card.get("grading", {}).get("scored_fights")
    )
    overall["edge"] = build_edge_analysis(overall_entries)

    return {
        "card_count": len(cards),
        "overall": overall,
        "current_model": {
            "model_version": clean_text(current_provenance.get("model_version", "")),
            "recipe_hash": current_recipe,
            "model_type": clean_text(current_provenance.get("model_type", "")),
            "trained_at": clean_text(current_provenance.get("trained_at", "")),
            "git_commit": clean_text(current_provenance.get("git_commit", "")),
        },
        "cards": cards,
    }


def get_recent_card(event_id: str) -> dict[str, Any]:
    cards_payload = get_recent_cards(include_waiting=True)

    for card in cards_payload["cards"]:
        if str(card["event_id"]) == str(event_id):
            return card

    raise ValueError(f"Saved prediction card not found: {event_id}")
