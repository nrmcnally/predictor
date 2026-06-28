from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from app.data.scrape_upcoming_cards import scrape_upcoming_cards, save_csvs
from app.features.fight_context_features import build_future_fight_context
from app.services.fight_context_override_service import (
    find_scheduled_rounds_override,
    upsert_scheduled_rounds_override,
)
from app.services.prediction_service import FighterNotFoundError, predict_fight_data
from app.repositories import future_cards_repository


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
    if future_cards_repository.count_upcoming_events() == 0:
        refresh_upcoming_cards()

    return future_cards_repository.read_upcoming_events_df()


@lru_cache(maxsize=1)
def load_upcoming_fights() -> pd.DataFrame:
    if future_cards_repository.count_upcoming_fights() == 0:
        refresh_upcoming_cards()

    return future_cards_repository.read_upcoming_fights_df()


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
    event_name = clean_text(event["event_name"])
    is_fight_night = event_name.casefold().startswith("ufc fight night")

    event_fights_df = fights_df[fights_df["event_id"].astype(str) == str(event_id)]

    fights = []

    card_size = int(len(event_fights_df))

    for fight_index, (_, fight) in enumerate(event_fights_df.iterrows()):
        fight_id = clean_text(fight["fight_url"]).rstrip("/").split("/")[-1]
        fighter_1 = clean_text(fight["fighter_1"])
        fighter_2 = clean_text(fight["fighter_2"])
        fight_url = clean_text(fight["fight_url"])
        round_override = find_scheduled_rounds_override(
            event_id=event_id,
            fight_url=fight_url,
            fighter_1=fighter_1,
            fighter_2=fighter_2,
        )
        explicit_scheduled_rounds = (
            round_override["scheduled_rounds"]
            if round_override
            else fight.get("scheduled_rounds")
        )
        fight_context = build_future_fight_context(
            fight_index=fight_index,
            card_size=card_size,
            explicit_scheduled_rounds=explicit_scheduled_rounds,
        )

        if round_override:
            fight_context["fight_context_source"] = "manual_override"

        fights.append(
            {
                "fight_id": fight_id,
                "fight_url": fight_url,
                "fighter_1": fighter_1,
                "fighter_2": fighter_2,
                "weight_class": clean_text(fight["weight_class"]),
                "fight_context": fight_context,
                "scheduled_rounds": fight_context["fight_context_scheduled_rounds"],
                "is_main_event": bool(fight_context["fight_context_is_main_event"]),
                "card_position_from_top": fight_index + 1,
                "round_override_eligible": fight_index in {1, 2} and not is_fight_night,
                "round_override_saved": bool(round_override),
                "round_override_source": fight_context.get("fight_context_source", ""),
                "round_override_updated_at": (
                    round_override.get("updated_at", "") if round_override else ""
                ),
            }
        )

    return {
        "event_id": clean_text(event["event_id"]),
        "event_name": event_name,
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
                fight_context=fight.get("fight_context"),
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


def set_future_fight_scheduled_rounds(
    *,
    event_id: str,
    fight_id: str,
    scheduled_rounds: Any,
) -> dict[str, Any]:
    events_df = load_upcoming_events()
    fights_df = load_upcoming_fights()

    event_matches = events_df[events_df["event_id"].astype(str) == str(event_id)]

    if event_matches.empty:
        raise ValueError(f"Future card not found: {event_id}")

    event = event_matches.iloc[0]
    event_fights_df = fights_df[fights_df["event_id"].astype(str) == str(event_id)]

    for fight_index, (_, fight) in enumerate(event_fights_df.iterrows()):
        current_fight_id = clean_text(fight["fight_url"]).rstrip("/").split("/")[-1]

        if current_fight_id != str(fight_id):
            continue

        override = upsert_scheduled_rounds_override(
            event_id=event_id,
            event_name=event.get("event_name", ""),
            event_date=event.get("event_date", ""),
            event_url=event.get("event_url", ""),
            fight_id=current_fight_id,
            fight_url=fight.get("fight_url", ""),
            fighter_1=fight.get("fighter_1", ""),
            fighter_2=fight.get("fighter_2", ""),
            weight_class=fight.get("weight_class", ""),
            scheduled_rounds=scheduled_rounds,
        )

        return {
            "event_id": event_id,
            "fight_id": current_fight_id,
            "card_position_from_top": fight_index + 1,
            "override": override,
            "card": get_future_card_predictions(event_id),
        }

    raise ValueError(f"Future fight not found: {fight_id}")
