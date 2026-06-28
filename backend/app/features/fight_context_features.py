from __future__ import annotations

from typing import Any

import pandas as pd


FIGHT_CONTEXT_NUMERIC_FEATURES = [
    "fight_context_scheduled_rounds",
    "fight_context_is_five_round",
    "fight_context_is_main_event",
    "fight_context_card_position_from_top",
    "fight_context_card_position_from_bottom",
    "fight_context_card_size",
]


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def normalize_fight_url(value: Any) -> str:
    normalized = clean_text(value)
    normalized = normalized.replace("https://www.", "https://")
    normalized = normalized.replace("http://www.", "http://")
    return normalized.rstrip("/")


def optional_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def infer_scheduled_rounds(
    *,
    card_position_from_top: int | None,
    actual_round: Any = None,
    explicit_scheduled_rounds: Any = None,
) -> int:
    """
    UFCStats does not provide scheduled rounds in the current saved CSV shape.

    We keep the inference intentionally conservative:
      - explicit value wins when a future scraper/feed eventually provides it
      - actual round 4/5 proves a fight was scheduled for 5
      - the first listed fight on a card is treated as the main event
      - everything else defaults to 3
    """
    explicit_rounds = optional_int(explicit_scheduled_rounds)

    if explicit_rounds in {3, 5}:
        return explicit_rounds

    actual_round_number = optional_int(actual_round)

    if actual_round_number is not None and actual_round_number > 3:
        return 5

    if card_position_from_top == 1:
        return 5

    return 3


def build_context_payload(
    *,
    card_position_from_top: int | None,
    card_size: int | None,
    actual_round: Any = None,
    explicit_scheduled_rounds: Any = None,
) -> dict[str, Any]:
    scheduled_rounds = infer_scheduled_rounds(
        card_position_from_top=card_position_from_top,
        actual_round=actual_round,
        explicit_scheduled_rounds=explicit_scheduled_rounds,
    )

    if card_position_from_top is not None and card_size is not None:
        card_position_from_bottom = max(card_size - card_position_from_top + 1, 1)
    else:
        card_position_from_bottom = None

    return {
        "fight_context_scheduled_rounds": scheduled_rounds,
        "fight_context_is_five_round": 1 if scheduled_rounds == 5 else 0,
        "fight_context_is_main_event": 1 if card_position_from_top == 1 else 0,
        "fight_context_card_position_from_top": card_position_from_top,
        "fight_context_card_position_from_bottom": card_position_from_bottom,
        "fight_context_card_size": card_size,
        "fight_context_source": (
            "explicit"
            if optional_int(explicit_scheduled_rounds) in {3, 5}
            else "actual_round"
            if optional_int(actual_round) is not None and optional_int(actual_round) > 3
            else "main_event_inference"
            if card_position_from_top == 1
            else "default_three_round"
        ),
    }


def build_event_fight_context_lookup(event_fights_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if event_fights_df.empty or "fight_url" not in event_fights_df.columns:
        return {}

    df = event_fights_df.copy()

    if "event_url" not in df.columns:
        df["event_url"] = df.get("event_name", "")

    df["_event_key"] = df["event_url"].apply(clean_text)
    df["_card_position_from_top"] = df.groupby("_event_key", sort=False).cumcount() + 1
    df["_card_size"] = df.groupby("_event_key")["fight_url"].transform("count")

    lookup: dict[str, dict[str, Any]] = {}

    for _, row in df.iterrows():
        fight_url = normalize_fight_url(row.get("fight_url", ""))

        if not fight_url:
            continue

        lookup[fight_url] = build_context_payload(
            card_position_from_top=optional_int(row.get("_card_position_from_top")),
            card_size=optional_int(row.get("_card_size")),
            actual_round=row.get("round"),
            explicit_scheduled_rounds=row.get("scheduled_rounds"),
        )

    return lookup


def build_future_fight_context(
    *,
    fight_index: int,
    card_size: int,
    explicit_scheduled_rounds: Any = None,
) -> dict[str, Any]:
    return build_context_payload(
        card_position_from_top=fight_index + 1,
        card_size=card_size,
        explicit_scheduled_rounds=explicit_scheduled_rounds,
    )


def default_fight_context() -> dict[str, Any]:
    return build_context_payload(
        card_position_from_top=None,
        card_size=None,
        explicit_scheduled_rounds=3,
    )
