from __future__ import annotations

import json
import os
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

UPCOMING_FIGHTS_CSV = RAW_DATA_DIR / "upcoming_fights.csv"
CURRENT_MMA_ODDS_JSON = RAW_DATA_DIR / "current_mma_odds.json"
FUTURE_FIGHT_ODDS_CSV = PROCESSED_DATA_DIR / "future_fight_odds.csv"

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/mma_mixed_martial_arts/odds/"

PREFERRED_BOOKMAKERS = [
    "draftkings",
    "fanduel",
    "betmgm",
    "caesars",
    "betrivers",
    "espnbet",
]


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
    if not UPCOMING_FIGHTS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {UPCOMING_FIGHTS_CSV}. Refresh future cards first."
        )

    return pd.read_csv(UPCOMING_FIGHTS_CSV)


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
) -> tuple[bool, float]:
    home_team = clean_text(odds_event.get("home_team", ""))
    away_team = clean_text(odds_event.get("away_team", ""))

    direct_score = (
        name_similarity(home_team, fighter_1)
        + name_similarity(away_team, fighter_2)
    ) / 2.0

    swapped_score = (
        name_similarity(home_team, fighter_2)
        + name_similarity(away_team, fighter_1)
    ) / 2.0

    best_score = max(direct_score, swapped_score)

    return best_score >= 0.88, best_score


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

    for odds_event in odds_events:
        is_match, score = odds_event_matches_fight(
            odds_event=odds_event,
            fighter_1=fighter_1,
            fighter_2=fighter_2,
        )

        if is_match and score > best_score:
            best_event = odds_event
            best_score = score

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

    odds_available_count = int(odds_df["odds_available"].sum()) if not odds_df.empty else 0

    return {
        "output_file": str(FUTURE_FIGHT_ODDS_CSV),
        "raw_odds_file": str(CURRENT_MMA_ODDS_JSON),
        "upcoming_fights": int(len(upcoming_fights_df)),
        "odds_events": int(len(odds_events)),
        "matched_fights": odds_available_count,
        "unmatched_fights": int(len(upcoming_fights_df) - odds_available_count),
    }


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