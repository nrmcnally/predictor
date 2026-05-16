from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from app.data.scrape_upcoming_cards import scrape_upcoming_cards, save_csvs
from app.services.prediction_service import FighterNotFoundError, predict_fight_data


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

UPCOMING_EVENTS_CSV = RAW_DATA_DIR / "upcoming_events.csv"
UPCOMING_FIGHTS_CSV = RAW_DATA_DIR / "upcoming_fights.csv"


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def refresh_upcoming_cards() -> dict[str, int]:
    """
    Re-scrapes upcoming cards and clears cached CSV reads.
    """
    events, fights = scrape_upcoming_cards()
    save_csvs(events, fights)

    load_upcoming_events.cache_clear()
    load_upcoming_fights.cache_clear()

    return {
        "events": len(events),
        "fights": len(fights),
    }


@lru_cache(maxsize=1)
def load_upcoming_events() -> pd.DataFrame:
    if not UPCOMING_EVENTS_CSV.exists():
        refresh_upcoming_cards()

    return pd.read_csv(UPCOMING_EVENTS_CSV)


@lru_cache(maxsize=1)
def load_upcoming_fights() -> pd.DataFrame:
    if not UPCOMING_FIGHTS_CSV.exists():
        refresh_upcoming_cards()

    return pd.read_csv(UPCOMING_FIGHTS_CSV)


def get_future_cards() -> list[dict[str, Any]]:
    events_df = load_upcoming_events()
    fights_df = load_upcoming_fights()

    cards = []

    for _, event in events_df.iterrows():
        event_id = clean_text(event["event_id"])
        event_fights_df = fights_df[fights_df["event_id"].astype(str) == event_id]

        cards.append(
            {
                "event_id": event_id,
                "event_name": clean_text(event["event_name"]),
                "event_date": clean_text(event["event_date"]),
                "event_location": clean_text(event["event_location"]),
                "event_url": clean_text(event["event_url"]),
                "fight_count": int(len(event_fights_df)),
            }
        )

    return cards


def get_future_card(event_id: str) -> dict[str, Any]:
    events_df = load_upcoming_events()
    fights_df = load_upcoming_fights()

    event_matches = events_df[events_df["event_id"].astype(str) == str(event_id)]

    if event_matches.empty:
        raise ValueError(f"Future card not found: {event_id}")

    event = event_matches.iloc[0]

    event_fights_df = fights_df[fights_df["event_id"].astype(str) == str(event_id)]

    fights = []

    for _, fight in event_fights_df.iterrows():
        fight_id = clean_text(fight["fight_url"]).rstrip("/").split("/")[-1]

        fights.append(
            {
                "fight_id": fight_id,
                "fight_url": clean_text(fight["fight_url"]),
                "fighter_1": clean_text(fight["fighter_1"]),
                "fighter_2": clean_text(fight["fighter_2"]),
                "weight_class": clean_text(fight["weight_class"]),
            }
        )

    return {
        "event_id": clean_text(event["event_id"]),
        "event_name": clean_text(event["event_name"]),
        "event_date": clean_text(event["event_date"]),
        "event_location": clean_text(event["event_location"]),
        "event_url": clean_text(event["event_url"]),
        "fights": fights,
    }


def get_future_card_predictions(event_id: str) -> dict[str, Any]:
    card = get_future_card(event_id)

    predicted_fights = []

    for fight in card["fights"]:
        fighter_1 = fight["fighter_1"]
        fighter_2 = fight["fighter_2"]
        weight_class = fight["weight_class"]

        try:
            prediction = predict_fight_data(
                fighter_a=fighter_1,
                fighter_b=fighter_2,
                weight_class=weight_class,
            )

            predicted_fights.append(
                {
                    **fight,
                    "prediction_available": True,
                    "prediction": prediction,
                    "error": None,
                }
            )

        except FighterNotFoundError as error:
            predicted_fights.append(
                {
                    **fight,
                    "prediction_available": False,
                    "prediction": None,
                    "error": {
                        "message": f"Could not find fighter: {error.fighter_name}",
                        "suggestions": error.suggestions,
                    },
                }
            )

        except Exception as error:
            predicted_fights.append(
                {
                    **fight,
                    "prediction_available": False,
                    "prediction": None,
                    "error": {
                        "message": "Prediction failed.",
                        "details": str(error),
                    },
                }
            )

    return {
        **card,
        "fights": predicted_fights,
    }