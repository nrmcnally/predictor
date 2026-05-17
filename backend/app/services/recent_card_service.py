from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


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
    return read_csv_or_empty(SAVED_CARD_PREDICTIONS_CSV)


def load_actual_results() -> pd.DataFrame:
    return read_csv_or_empty(EVENT_FIGHTS_CSV)


def build_actual_result_lookup(event_fights_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """
    Builds a lookup by fight_url.

    event_fights.csv contains completed fight rows with winner/loser.
    saved_card_predictions.csv contains the future-card fight_url.
    So fight_url is the cleanest join key.
    """
    if event_fights_df.empty:
        return {}

    required_columns = {"fight_url", "winner", "loser"}

    if not required_columns.issubset(event_fights_df.columns):
        return {}

    df = event_fights_df.copy()

    df["winner_clean"] = df["winner"].apply(clean_text)
    df["loser_clean"] = df["loser"].apply(clean_text)

    df = df[
        (df["winner_clean"] != "")
        & (df["loser_clean"] != "")
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
            "winner": clean_text(row.get("winner", "")),
            "loser": clean_text(row.get("loser", "")),
            "method": clean_text(row.get("method", "")),
            "round": clean_text(row.get("round", "")),
            "time": clean_text(row.get("time", "")),
            "weight_class": clean_text(row.get("weight_class", "")),
        }

    return lookup


def build_fight_result_row(
    saved_row: pd.Series,
    actual_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    fight_url = normalize_fight_url(saved_row.get("fight_url", ""))
    actual = actual_lookup.get(fight_url)

    prediction_available = parse_bool(saved_row.get("prediction_available", False))
    predicted_winner = clean_text(saved_row.get("predicted_winner", ""))

    actual_winner = ""
    actual_loser = ""
    actual_method = ""
    actual_round = ""
    actual_time = ""

    if actual is not None:
        actual_winner = clean_text(actual.get("winner", ""))
        actual_loser = clean_text(actual.get("loser", ""))
        actual_method = clean_text(actual.get("method", ""))
        actual_round = clean_text(actual.get("round", ""))
        actual_time = clean_text(actual.get("time", ""))

    actual_result_available = bool(actual_winner)

    prediction_correct = None

    if prediction_available and actual_result_available and predicted_winner:
        prediction_correct = predicted_winner == actual_winner

    return {
        "saved_at": clean_text(saved_row.get("saved_at", "")),

        "fight_id": clean_text(saved_row.get("fight_id", "")),
        "fight_url": fight_url,
        "fighter_1": clean_text(saved_row.get("fighter_1", "")),
        "fighter_2": clean_text(saved_row.get("fighter_2", "")),
        "weight_class": clean_text(saved_row.get("weight_class", "")),

        "prediction_available": prediction_available,
        "predicted_winner": predicted_winner,
        "fighter_1_percentage": clean_text(saved_row.get("fighter_1_percentage", "")),
        "fighter_2_percentage": clean_text(saved_row.get("fighter_2_percentage", "")),
        "confidence_percentage": clean_text(saved_row.get("confidence_percentage", "")),
        "confidence_label": clean_text(saved_row.get("confidence_label", "")),
        "model_name": clean_text(saved_row.get("model_name", "")),

        "actual_result_available": actual_result_available,
        "actual_winner": actual_winner,
        "actual_loser": actual_loser,
        "actual_method": actual_method,
        "actual_round": actual_round,
        "actual_time": actual_time,

        "prediction_correct": prediction_correct,
        "error_json": clean_text(saved_row.get("error_json", "")),
    }


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

    if not completed_fights:
        status = "waiting_for_results"
    elif len(completed_fights) < len(fights):
        status = "partially_completed"
    else:
        status = "completed"

    accuracy = None

    if predicted_completed_fights:
        accuracy = len(correct_predictions) / len(predicted_completed_fights)

    return {
        "status": status,
        "fight_count": len(fights),
        "actual_result_count": len(completed_fights),
        "predicted_completed_count": len(predicted_completed_fights),
        "correct_prediction_count": len(correct_predictions),
        "accuracy": accuracy,
        "accuracy_percentage": f"{accuracy * 100.0:.1f}%" if accuracy is not None else "",
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

    cards: list[dict[str, Any]] = []

    for event_id, card_df in saved_df.groupby("event_id", sort=False):
        first_row = card_df.iloc[0]

        fights = [
            build_fight_result_row(saved_row=row, actual_lookup=actual_lookup)
            for _, row in card_df.iterrows()
        ]

        summary = summarize_card_fights(fights)

        if not include_waiting and summary["status"] == "waiting_for_results":
            continue

        cards.append(
            {
                "event_id": clean_text(event_id),
                "event_name": clean_text(first_row.get("event_name", "")),
                "event_date": clean_text(first_row.get("event_date", "")),
                "event_location": clean_text(first_row.get("event_location", "")),
                "event_url": clean_text(first_row.get("event_url", "")),
                "saved_at": clean_text(first_row.get("saved_at", "")),
                **summary,
                "fights": fights,
            }
        )

    cards = sorted(
        cards,
        key=lambda card: pd.to_datetime(card["event_date"], errors="coerce"),
        reverse=True,
    )

    return {
        "card_count": len(cards),
        "cards": cards,
    }


def get_recent_card(event_id: str) -> dict[str, Any]:
    cards_payload = get_recent_cards(include_waiting=True)

    for card in cards_payload["cards"]:
        if str(card["event_id"]) == str(event_id):
            return card

    raise ValueError(f"Saved prediction card not found: {event_id}")