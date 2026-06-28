from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
FIGHT_CONTEXT_OVERRIDES_CSV = RAW_DATA_DIR / "fight_context_overrides.csv"

OVERRIDE_COLUMNS = [
    "updated_at",
    "event_id",
    "event_name",
    "event_date",
    "event_url",
    "fight_id",
    "fight_url",
    "fighter_1",
    "fighter_2",
    "weight_class",
    "scheduled_rounds",
    "source",
]


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def optional_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def normalize_fight_url(value: Any) -> str:
    normalized = clean_text(value)
    normalized = normalized.replace("https://www.", "https://")
    normalized = normalized.replace("http://www.", "http://")
    return normalized.rstrip("/")


def normalize_name(value: Any) -> str:
    return clean_text(value).casefold()


def make_fight_id(fight_url: Any) -> str:
    return normalize_fight_url(fight_url).rstrip("/").split("/")[-1]


def make_matchup_key(event_id: Any, fighter_1: Any, fighter_2: Any) -> str:
    fighters = sorted([normalize_name(fighter_1), normalize_name(fighter_2)])
    return "::".join([clean_text(event_id), *fighters])


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_fight_context_overrides() -> pd.DataFrame:
    if not FIGHT_CONTEXT_OVERRIDES_CSV.exists():
        return pd.DataFrame(columns=OVERRIDE_COLUMNS)

    try:
        df = pd.read_csv(FIGHT_CONTEXT_OVERRIDES_CSV)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=OVERRIDE_COLUMNS)

    for column in OVERRIDE_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    return df[OVERRIDE_COLUMNS].copy()


def write_fight_context_overrides(df: pd.DataFrame) -> None:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    for column in OVERRIDE_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    df[OVERRIDE_COLUMNS].to_csv(FIGHT_CONTEXT_OVERRIDES_CSV, index=False)


def find_scheduled_rounds_override(
    *,
    event_id: Any,
    fight_url: Any,
    fighter_1: Any,
    fighter_2: Any,
) -> dict[str, Any] | None:
    df = read_fight_context_overrides()

    if df.empty:
        return None

    normalized_url = normalize_fight_url(fight_url)
    matchup_key = make_matchup_key(event_id, fighter_1, fighter_2)

    matches = df.iloc[0:0].copy()

    if normalized_url:
        url_matches = df[
            df["fight_url"].apply(normalize_fight_url) == normalized_url
        ].copy()
        matches = pd.concat([matches, url_matches], ignore_index=True)

    key_matches = df[
        df.apply(
            lambda row: make_matchup_key(
                row.get("event_id", ""),
                row.get("fighter_1", ""),
                row.get("fighter_2", ""),
            )
            == matchup_key,
            axis=1,
        )
    ].copy()
    matches = pd.concat([matches, key_matches], ignore_index=True)

    if matches.empty:
        return None

    matches["_updated_at_sort"] = pd.to_datetime(
        matches["updated_at"],
        errors="coerce",
    )
    matches = matches.sort_values("_updated_at_sort", ascending=False)
    row = matches.iloc[0]

    scheduled_rounds = optional_int(row.get("scheduled_rounds"))

    if scheduled_rounds not in {3, 5}:
        return None

    return {
        "scheduled_rounds": scheduled_rounds,
        "source": clean_text(row.get("source", "manual")),
        "updated_at": clean_text(row.get("updated_at", "")),
    }


def upsert_scheduled_rounds_override(
    *,
    event_id: Any,
    event_name: Any,
    event_date: Any,
    event_url: Any,
    fight_id: Any,
    fight_url: Any,
    fighter_1: Any,
    fighter_2: Any,
    weight_class: Any,
    scheduled_rounds: Any,
) -> dict[str, Any]:
    rounds = optional_int(scheduled_rounds)

    if rounds not in {3, 5}:
        raise ValueError("Scheduled rounds must be 3 or 5.")

    df = read_fight_context_overrides()

    normalized_url = normalize_fight_url(fight_url)
    matchup_key = make_matchup_key(event_id, fighter_1, fighter_2)

    if not df.empty:
        by_url = (
            df["fight_url"].apply(normalize_fight_url) == normalized_url
            if normalized_url
            else pd.Series(False, index=df.index)
        )
        by_matchup = df.apply(
            lambda row: make_matchup_key(
                row.get("event_id", ""),
                row.get("fighter_1", ""),
                row.get("fighter_2", ""),
            )
            == matchup_key,
            axis=1,
        )

        df = df[~(by_url | by_matchup)].copy()

    row = {
        "updated_at": now_iso(),
        "event_id": clean_text(event_id),
        "event_name": clean_text(event_name),
        "event_date": clean_text(event_date),
        "event_url": clean_text(event_url),
        "fight_id": clean_text(fight_id) or make_fight_id(fight_url),
        "fight_url": normalize_fight_url(fight_url),
        "fighter_1": clean_text(fighter_1),
        "fighter_2": clean_text(fighter_2),
        "weight_class": clean_text(weight_class),
        "scheduled_rounds": rounds,
        "source": "manual",
    }

    combined = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    write_fight_context_overrides(combined)

    return row
