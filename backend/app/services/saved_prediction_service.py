from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.odds_service import FUTURE_FIGHT_ODDS_CSV

from app.services.future_card_service import (
    get_future_card_predictions,
    get_future_cards,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"

SAVED_CARD_PREDICTIONS_CSV = PROCESSED_DATA_DIR / "saved_card_predictions.csv"
CALIBRATED_METRICS_PATH = MODELS_DIR / "calibrated_model_metrics.json"


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

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_model_metadata() -> dict[str, Any]:
    if not CALIBRATED_METRICS_PATH.exists():
        return {
            "best_model_name": "",
            "metrics": {},
        }

    with open(CALIBRATED_METRICS_PATH, "r", encoding="utf-8") as file:
        metrics_payload = json.load(file)

    best_model_name = metrics_payload.get("best_model_name", "")

    return {
        "best_model_name": best_model_name,
        "metrics": metrics_payload.get("results", {}).get(best_model_name, {}),
    }


def read_saved_predictions() -> pd.DataFrame:
    if not SAVED_CARD_PREDICTIONS_CSV.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(SAVED_CARD_PREDICTIONS_CSV)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def write_saved_predictions(df: pd.DataFrame) -> None:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(SAVED_CARD_PREDICTIONS_CSV, index=False)


def build_saved_prediction_rows_for_card(event_id: str) -> list[dict[str, Any]]:
    card = get_future_card_predictions(event_id)
    model_metadata = load_model_metadata()
    odds_lookup = load_future_odds_lookup()

    saved_at = now_iso()

    rows: list[dict[str, Any]] = []

    for fight in card["fights"]:
        prediction_available = bool(fight.get("prediction_available"))
        prediction = fight.get("prediction") or {}
        error = fight.get("error")
        odds_data = odds_lookup.get(normalize_fight_url(fight["fight_url"]), {})

        row = {
            "saved_at": saved_at,

            "event_id": card["event_id"],
            "event_name": card["event_name"],
            "event_date": card["event_date"],
            "event_location": card["event_location"],
            "event_url": card["event_url"],

            "fight_id": fight["fight_id"],
            "fight_url": fight["fight_url"],
            "fighter_1": fight["fighter_1"],
            "fighter_2": fight["fighter_2"],
            "weight_class": fight["weight_class"],

            "prediction_available": prediction_available,
            "error_json": json.dumps(error) if error else "",

            "predicted_winner": prediction.get("predicted_winner", ""),
            "fighter_1_probability": None,
            "fighter_2_probability": None,
            "fighter_1_percentage": "",
            "fighter_2_percentage": "",
            "confidence": prediction.get("confidence"),
            "confidence_percentage": prediction.get("confidence_percentage", ""),
            "confidence_label": prediction.get("confidence_label", ""),

            "model_name": model_metadata["best_model_name"],
            "model_metrics_json": json.dumps(model_metadata["metrics"]),

            "basic_matchup_edges_json": json.dumps(
                prediction.get("basic_matchup_edges", [])
            ),

            "odds_available": odds_data.get("odds_available", False),
            "odds_bookmaker": odds_data.get("odds_bookmaker", ""),
            "odds_last_update": odds_data.get("odds_last_update", ""),
            "bookmakers_matched": odds_data.get("bookmakers_matched"),
            "fighter_1_odds_american": odds_data.get("fighter_1_odds_american"),
            "fighter_2_odds_american": odds_data.get("fighter_2_odds_american"),
            "fighter_1_market_probability": odds_data.get("fighter_1_market_probability"),
            "fighter_2_market_probability": odds_data.get("fighter_2_market_probability"),
            "fighter_1_market_percentage": odds_data.get("fighter_1_market_percentage", ""),
            "fighter_2_market_percentage": odds_data.get("fighter_2_market_percentage", ""),
            "market_favorite": odds_data.get("market_favorite", ""),
            "market_favorite_probability": odds_data.get("market_favorite_probability"),
            "market_favorite_percentage": odds_data.get("market_favorite_percentage", ""),
        }

        if prediction_available:
            # The prediction service uses fighter_a/fighter_b.
            # For future-card rows, fighter_1 is passed as fighter_a and fighter_2 as fighter_b.
            row["fighter_1_probability"] = prediction.get("fighter_a_probability")
            row["fighter_2_probability"] = prediction.get("fighter_b_probability")
            row["fighter_1_percentage"] = prediction.get("fighter_a_percentage", "")
            row["fighter_2_percentage"] = prediction.get("fighter_b_percentage", "")

        rows.append(row)

    return rows


def save_predictions_for_card(event_id: str) -> dict[str, Any]:
    existing_df = read_saved_predictions()

    new_rows = build_saved_prediction_rows_for_card(event_id)
    new_df = pd.DataFrame(new_rows)

    if existing_df.empty:
        combined_df = new_df
    else:
        # Replace previous saved predictions for this card.
        # This keeps one latest saved snapshot per event/fight instead of growing duplicates.
        existing_df = existing_df[
            existing_df["event_id"].astype(str) != str(event_id)
        ].copy()

        combined_df = pd.concat(
            [existing_df, new_df],
            ignore_index=True,
        )

    write_saved_predictions(combined_df)

    prediction_available_count = int(new_df["prediction_available"].sum()) if not new_df.empty else 0

    return {
        "event_id": event_id,
        "saved_rows": int(len(new_df)),
        "prediction_available_count": prediction_available_count,
        "prediction_unavailable_count": int(len(new_df) - prediction_available_count),
        "output_file": str(SAVED_CARD_PREDICTIONS_CSV),
    }


def save_predictions_for_all_future_cards() -> dict[str, Any]:
    cards = get_future_cards()

    saved_cards = []
    total_rows = 0
    total_available = 0
    total_unavailable = 0

    for card in cards:
        event_id = card["event_id"]

        result = save_predictions_for_card(event_id)

        saved_cards.append(result)
        total_rows += result["saved_rows"]
        total_available += result["prediction_available_count"]
        total_unavailable += result["prediction_unavailable_count"]

    return {
        "cards_saved": len(saved_cards),
        "total_rows": total_rows,
        "total_prediction_available": total_available,
        "total_prediction_unavailable": total_unavailable,
        "cards": saved_cards,
        "output_file": str(SAVED_CARD_PREDICTIONS_CSV),
    }


def get_saved_card_predictions() -> dict[str, Any]:
    df = read_saved_predictions()

    if df.empty:
        return {
            "saved_prediction_count": 0,
            "cards": [],
        }

    cards = []

    for event_id, card_df in df.groupby("event_id", sort=False):
        first_row = card_df.iloc[0]

        fights = []

        for _, row in card_df.iterrows():
            fights.append(
                {
                    "saved_at": clean_text(row.get("saved_at", "")),
                    "fight_id": clean_text(row.get("fight_id", "")),
                    "fighter_1": clean_text(row.get("fighter_1", "")),
                    "fighter_2": clean_text(row.get("fighter_2", "")),
                    "weight_class": clean_text(row.get("weight_class", "")),
                    "prediction_available": bool(row.get("prediction_available", False)),
                    "predicted_winner": clean_text(row.get("predicted_winner", "")),
                    "fighter_1_percentage": clean_text(row.get("fighter_1_percentage", "")),
                    "fighter_2_percentage": clean_text(row.get("fighter_2_percentage", "")),
                    "confidence_percentage": clean_text(row.get("confidence_percentage", "")),
                    "confidence_label": clean_text(row.get("confidence_label", "")),
                    "model_name": clean_text(row.get("model_name", "")),
                    "error_json": clean_text(row.get("error_json", "")),
                }
            )

        cards.append(
            {
                "event_id": clean_text(event_id),
                "event_name": clean_text(first_row.get("event_name", "")),
                "event_date": clean_text(first_row.get("event_date", "")),
                "event_location": clean_text(first_row.get("event_location", "")),
                "saved_at": clean_text(first_row.get("saved_at", "")),
                "fight_count": int(len(card_df)),
                "prediction_available_count": int(card_df["prediction_available"].sum()),
                "fights": fights,
            }
        )

    return {
        "saved_prediction_count": int(len(df)),
        "cards": cards,
    }

def load_future_odds_lookup() -> dict[str, dict[str, Any]]:
    if not FUTURE_FIGHT_ODDS_CSV.exists():
        return {}

    try:
        odds_df = pd.read_csv(FUTURE_FIGHT_ODDS_CSV)
    except Exception:
        return {}

    if odds_df.empty or "fight_url" not in odds_df.columns:
        return {}

    odds_lookup = {}

    for _, row in odds_df.iterrows():
        fight_url = normalize_fight_url(row.get("fight_url", ""))

        if not fight_url:
            continue

        odds_lookup[fight_url] = {
            "odds_available": bool(row.get("odds_available", False)),
            "odds_bookmaker": clean_text(row.get("odds_bookmaker", "")),
            "odds_last_update": clean_text(row.get("odds_last_update", "")),
            "bookmakers_matched": row.get("bookmakers_matched"),
            "fighter_1_odds_american": row.get("fighter_1_odds_american"),
            "fighter_2_odds_american": row.get("fighter_2_odds_american"),
            "fighter_1_market_probability": row.get("fighter_1_market_probability"),
            "fighter_2_market_probability": row.get("fighter_2_market_probability"),
            "fighter_1_market_percentage": clean_text(row.get("fighter_1_market_percentage", "")),
            "fighter_2_market_percentage": clean_text(row.get("fighter_2_market_percentage", "")),
            "market_favorite": clean_text(row.get("market_favorite", "")),
            "market_favorite_probability": row.get("market_favorite_probability"),
            "market_favorite_percentage": clean_text(row.get("market_favorite_percentage", "")),
        }

    return odds_lookup