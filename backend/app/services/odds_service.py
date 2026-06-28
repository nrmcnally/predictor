from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from app.repositories import future_cards_repository, odds_track_repository


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

UPCOMING_FIGHTS_CSV = RAW_DATA_DIR / "upcoming_fights.csv"
CURRENT_MMA_ODDS_JSON = RAW_DATA_DIR / "current_mma_odds.json"
FUTURE_FIGHT_ODDS_CSV = PROCESSED_DATA_DIR / "future_fight_odds.csv"
# Per-fight opening (frozen on first sight) + closing (latest seen) market line,
# accumulated across odds refreshes. This is what closing-line value (CLV) needs.
FIGHT_ODDS_TRACK_CSV = PROCESSED_DATA_DIR / "fight_odds_track.csv"

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/mma_mixed_martial_arts/odds/"

PREFERRED_BOOKMAKERS = [
    "draftkings",
    "fanduel",
    "betmgm",
    "caesars",
    "betrivers",
    "espnbet",
]

logger = logging.getLogger("ufc_predictor.odds")

# Fighter-name match thresholds for pairing an odds event to one of our fights.
# Require BOTH fighters to individually clear PER_FIGHTER_MATCH_THRESHOLD, so a
# perfect match on one fighter can't drag a weak match on the other over the line
# (the old average-only test let, e.g., 1.00 + 0.76 = 0.88 through). Accepted
# matches whose weaker fighter falls below LOW_CONFIDENCE_MATCH_THRESHOLD are
# kept but flagged on the row and logged for review.
PER_FIGHTER_MATCH_THRESHOLD = 0.85
LOW_CONFIDENCE_MATCH_THRESHOLD = 0.92


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def normalize_name(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9 ]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def name_similarity(left: str, right: str) -> float:
    left = normalize_name(left)
    right = normalize_name(right)

    if not left or not right:
        return 0.0

    if left == right:
        return 1.0

    return SequenceMatcher(None, left, right).ratio()


def names_match(left: str, right: str, threshold: float = 0.88) -> bool:
    return name_similarity(left, right) >= threshold


def american_to_implied_probability(odds: Any) -> float | None:
    try:
        odds_value = float(odds)
    except (TypeError, ValueError):
        return None

    if odds_value > 0:
        return 100.0 / (odds_value + 100.0)

    if odds_value < 0:
        return abs(odds_value) / (abs(odds_value) + 100.0)

    return None


def format_percent(value: float | None) -> str:
    if value is None:
        return ""

    return f"{value * 100.0:.1f}%"


def get_api_key(api_key: str | None = None) -> str:
    key = clean_text(api_key or os.environ.get("ODDS_API_KEY", ""))

    if not key:
        raise ValueError(
            "Missing ODDS_API_KEY. Set it with: set ODDS_API_KEY=your_key_here"
        )

    return key


def fetch_current_mma_odds(api_key: str | None = None) -> list[dict[str, Any]]:
    key = get_api_key(api_key)

    response = requests.get(
        ODDS_API_URL,
        params={
            "apiKey": key,
            "regions": "us",
            "markets": "h2h",
            "oddsFormat": "american",
            "dateFormat": "iso",
        },
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Odds API request failed: {response.status_code} {response.text[:500]}"
        )

    data = response.json()

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "source": "the-odds-api",
        "sport_key": "mma_mixed_martial_arts",
        "markets": "h2h",
        "odds_format": "american",
        "data": data,
    }

    with open(CURRENT_MMA_ODDS_JSON, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    return data


def load_upcoming_fights() -> pd.DataFrame:
    return future_cards_repository.read_upcoming_fights_df()


def find_outcome_for_fighter(
    outcomes: list[dict[str, Any]],
    fighter_name: str,
) -> dict[str, Any] | None:
    best_outcome = None
    best_score = 0.0

    for outcome in outcomes:
        outcome_name = clean_text(outcome.get("name", ""))
        score = name_similarity(outcome_name, fighter_name)

        if score > best_score:
            best_score = score
            best_outcome = outcome

    if best_score >= 0.88:
        return best_outcome

    return None


def extract_h2h_market(bookmaker: dict[str, Any]) -> dict[str, Any] | None:
    for market in bookmaker.get("markets", []):
        if market.get("key") == "h2h":
            return market

    return None


def choose_representative_bookmaker(matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not matches:
        return None

    for preferred_key in PREFERRED_BOOKMAKERS:
        for match in matches:
            if clean_text(match.get("bookmaker_key", "")).lower() == preferred_key:
                return match

    return matches[0]


def odds_event_matches_fight(
    odds_event: dict[str, Any],
    fighter_1: str,
    fighter_2: str,
) -> tuple[bool, float, float]:
    """Return (is_match, avg_score, weaker_score).

    The odds feed's home/away order isn't guaranteed to match our
    fighter_1/fighter_2 order, so both orientations are scored. A match requires
    BOTH fighters in the better orientation to individually clear
    PER_FIGHTER_MATCH_THRESHOLD. ``weaker_score`` is the lower of the two
    per-fighter similarities in that orientation, used to flag low-confidence
    matches downstream.
    """
    home_team = clean_text(odds_event.get("home_team", ""))
    away_team = clean_text(odds_event.get("away_team", ""))

    direct_1 = name_similarity(home_team, fighter_1)
    direct_2 = name_similarity(away_team, fighter_2)
    swapped_1 = name_similarity(home_team, fighter_2)
    swapped_2 = name_similarity(away_team, fighter_1)

    direct_avg = (direct_1 + direct_2) / 2.0
    swapped_avg = (swapped_1 + swapped_2) / 2.0

    if direct_avg >= swapped_avg:
        best_score = direct_avg
        weaker_score = min(direct_1, direct_2)
    else:
        best_score = swapped_avg
        weaker_score = min(swapped_1, swapped_2)

    is_match = weaker_score >= PER_FIGHTER_MATCH_THRESHOLD

    return is_match, best_score, weaker_score


def get_bookmaker_probability_match(
    bookmaker: dict[str, Any],
    fighter_1: str,
    fighter_2: str,
) -> dict[str, Any] | None:
    market = extract_h2h_market(bookmaker)

    if not market:
        return None

    outcomes = market.get("outcomes", [])

    fighter_1_outcome = find_outcome_for_fighter(outcomes, fighter_1)
    fighter_2_outcome = find_outcome_for_fighter(outcomes, fighter_2)

    if not fighter_1_outcome or not fighter_2_outcome:
        return None

    fighter_1_odds = fighter_1_outcome.get("price")
    fighter_2_odds = fighter_2_outcome.get("price")

    fighter_1_implied = american_to_implied_probability(fighter_1_odds)
    fighter_2_implied = american_to_implied_probability(fighter_2_odds)

    if fighter_1_implied is None or fighter_2_implied is None:
        return None

    total_implied = fighter_1_implied + fighter_2_implied

    if total_implied <= 0:
        return None

    fighter_1_no_vig = fighter_1_implied / total_implied
    fighter_2_no_vig = fighter_2_implied / total_implied

    return {
        "bookmaker_key": clean_text(bookmaker.get("key", "")),
        "bookmaker_title": clean_text(bookmaker.get("title", "")),
        "last_update": clean_text(bookmaker.get("last_update", "")),
        "fighter_1_odds_american": fighter_1_odds,
        "fighter_2_odds_american": fighter_2_odds,
        "fighter_1_market_probability": fighter_1_no_vig,
        "fighter_2_market_probability": fighter_2_no_vig,
    }


def build_odds_row_for_fight(
    fight_row: pd.Series,
    odds_events: list[dict[str, Any]],
) -> dict[str, Any]:
    fighter_1 = clean_text(fight_row.get("fighter_1", ""))
    fighter_2 = clean_text(fight_row.get("fighter_2", ""))

    best_event = None
    best_score = 0.0
    best_weaker_score = 0.0

    for odds_event in odds_events:
        is_match, score, weaker_score = odds_event_matches_fight(
            odds_event=odds_event,
            fighter_1=fighter_1,
            fighter_2=fighter_2,
        )

        if is_match and score > best_score:
            best_event = odds_event
            best_score = score
            best_weaker_score = weaker_score

    low_confidence_match = bool(best_event) and best_weaker_score < LOW_CONFIDENCE_MATCH_THRESHOLD

    if low_confidence_match:
        logger.warning(
            "Low-confidence odds match for %s vs %s "
            "(weaker name similarity %.2f) -> %s vs %s",
            fighter_1,
            fighter_2,
            best_weaker_score,
            clean_text(best_event.get("home_team", "")),
            clean_text(best_event.get("away_team", "")),
        )

    base_row = {
        "event_name": clean_text(fight_row.get("event_name", "")),
        "event_date": clean_text(fight_row.get("event_date", "")),
        "event_url": clean_text(fight_row.get("event_url", "")),
        "fight_url": clean_text(fight_row.get("fight_url", "")),
        "fighter_1": fighter_1,
        "fighter_2": fighter_2,
        "weight_class": clean_text(fight_row.get("weight_class", "")),
        "odds_available": False,
        "odds_event_id": "",
        "odds_commence_time": "",
        "odds_match_score": best_score,
        "odds_match_min_score": best_weaker_score,
        "odds_match_low_confidence": low_confidence_match,
        "odds_bookmaker": "",
        "odds_last_update": "",
        "bookmakers_matched": 0,
        "fighter_1_odds_american": None,
        "fighter_2_odds_american": None,
        "fighter_1_market_probability": None,
        "fighter_2_market_probability": None,
        "fighter_1_market_percentage": "",
        "fighter_2_market_percentage": "",
        "market_favorite": "",
        "market_favorite_probability": None,
        "market_favorite_percentage": "",
    }

    if not best_event:
        return base_row

    bookmaker_matches = []

    for bookmaker in best_event.get("bookmakers", []):
        bookmaker_match = get_bookmaker_probability_match(
            bookmaker=bookmaker,
            fighter_1=fighter_1,
            fighter_2=fighter_2,
        )

        if bookmaker_match:
            bookmaker_matches.append(bookmaker_match)

    if not bookmaker_matches:
        return {
            **base_row,
            "odds_event_id": clean_text(best_event.get("id", "")),
            "odds_commence_time": clean_text(best_event.get("commence_time", "")),
        }

    fighter_1_market_probability = sum(
        match["fighter_1_market_probability"] for match in bookmaker_matches
    ) / len(bookmaker_matches)

    fighter_2_market_probability = sum(
        match["fighter_2_market_probability"] for match in bookmaker_matches
    ) / len(bookmaker_matches)

    representative = choose_representative_bookmaker(bookmaker_matches)

    if fighter_1_market_probability >= fighter_2_market_probability:
        market_favorite = fighter_1
        market_favorite_probability = fighter_1_market_probability
    else:
        market_favorite = fighter_2
        market_favorite_probability = fighter_2_market_probability

    return {
        **base_row,
        "odds_available": True,
        "odds_event_id": clean_text(best_event.get("id", "")),
        "odds_commence_time": clean_text(best_event.get("commence_time", "")),
        "odds_bookmaker": clean_text(representative.get("bookmaker_title", "")),
        "odds_last_update": clean_text(representative.get("last_update", "")),
        "bookmakers_matched": len(bookmaker_matches),
        "fighter_1_odds_american": representative.get("fighter_1_odds_american"),
        "fighter_2_odds_american": representative.get("fighter_2_odds_american"),
        "fighter_1_market_probability": fighter_1_market_probability,
        "fighter_2_market_probability": fighter_2_market_probability,
        "fighter_1_market_percentage": format_percent(fighter_1_market_probability),
        "fighter_2_market_percentage": format_percent(fighter_2_market_probability),
        "market_favorite": market_favorite,
        "market_favorite_probability": market_favorite_probability,
        "market_favorite_percentage": format_percent(market_favorite_probability),
    }


def refresh_future_fight_odds(api_key: str | None = None) -> dict[str, Any]:
    odds_events = fetch_current_mma_odds(api_key=api_key)
    upcoming_fights_df = load_upcoming_fights()

    rows = []

    for _, fight_row in upcoming_fights_df.iterrows():
        rows.append(
            build_odds_row_for_fight(
                fight_row=fight_row,
                odds_events=odds_events,
            )
        )

    odds_df = pd.DataFrame(rows)

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    odds_df.to_csv(FUTURE_FIGHT_ODDS_CSV, index=False)

    # Capture the opening/closing line track for CLV.
    track_result = update_fight_odds_track()

    odds_available_count = int(odds_df["odds_available"].sum()) if not odds_df.empty else 0

    return {
        "output_file": str(FUTURE_FIGHT_ODDS_CSV),
        "odds_track_fights": track_result.get("tracked_fights", 0),
        "raw_odds_file": str(CURRENT_MMA_ODDS_JSON),
        "upcoming_fights": int(len(upcoming_fights_df)),
        "odds_events": int(len(odds_events)),
        "matched_fights": odds_available_count,
        "unmatched_fights": int(len(upcoming_fights_df) - odds_available_count),
    }


def optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_int(value: Any) -> int | None:
    number = optional_float(value)
    return None if number is None else int(number)


def _normalize_fight_url(value: Any) -> str:
    normalized = clean_text(value).replace("https://www.", "https://").replace("http://www.", "http://")
    return normalized.rstrip("/")


def update_fight_odds_track() -> dict[str, Any]:
    """
    Maintains the fight_odds_track table: per fight, freeze the OPENING line the first
    time we see odds and overwrite the CLOSING line every refresh. Fights that drop out
    of the current odds (event passed) keep their last-seen row automatically — no
    rewrite needed. Run on every odds refresh so the closing line is captured as near
    to fight time as the pipeline runs. Each fight is upserted atomically (SQLite).
    """
    if not FUTURE_FIGHT_ODDS_CSV.exists():
        return {"tracked_fights": 0, "updated_this_run": 0, "storage": "sqlite"}

    current = pd.read_csv(FUTURE_FIGHT_ODDS_CSV)
    if "fighter_1_market_probability" in current.columns:
        current = current[current["fighter_1_market_probability"].notna()].copy()

    now = datetime.now().isoformat(timespec="seconds")
    updated = 0

    for _, row in current.iterrows():
        url = _normalize_fight_url(row.get("fight_url", ""))
        if not url:
            continue

        odds_track_repository.record_capture(
            fight_url=url,
            fighter_1=clean_text(row.get("fighter_1", "")),
            fighter_2=clean_text(row.get("fighter_2", "")),
            fighter_1_probability=optional_float(row.get("fighter_1_market_probability")),
            fighter_2_probability=optional_float(row.get("fighter_2_market_probability")),
            captured_at=now,
        )
        updated += 1

    total = int(len(odds_track_repository.read_all_df()))
    return {"tracked_fights": total, "updated_this_run": updated, "storage": "sqlite"}


def load_future_fight_odds() -> dict[str, Any]:
    if not FUTURE_FIGHT_ODDS_CSV.exists():
        return {
            "available": False,
            "message": "Future fight odds have not been refreshed yet.",
            "odds": [],
        }

    odds_df = pd.read_csv(FUTURE_FIGHT_ODDS_CSV)

    return {
        "available": True,
        "message": "Future fight odds loaded.",
        "odds": odds_df.fillna("").to_dict(orient="records"),
    }


def main() -> None:
    result = refresh_future_fight_odds()

    print()
    print("Future fight odds refreshed")
    print("=" * 80)

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()