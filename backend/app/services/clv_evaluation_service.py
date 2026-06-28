from __future__ import annotations

"""
Closing-Line Value (CLV).

For each fight where the model made a pick and we captured both an opening and a
closing market line, did the line move TOWARD the model's pick by close? If the
model picked a fighter at an opening implied probability of P_open and the line
closed at P_close > P_open for that fighter, the market came toward the model — it
"beat the close", the gold-standard sign that a pick had real value the market
hadn't yet priced.

CLV needs two odds captures per fight (opening frozen, closing latest), so it only
becomes meaningful as `fight_odds_track.csv` accumulates refreshes near fight time.
"""

from pathlib import Path
from typing import Any

import pandas as pd

from app.repositories import (
    event_fights_repository,
    odds_track_repository,
    saved_predictions_repository,
)
from app.services.odds_service import (
    optional_float,
    optional_int,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

EVENT_FIGHTS_CSV = RAW_DATA_DIR / "event_fights.csv"
SAVED_CARD_PREDICTIONS_CSV = PROCESSED_DATA_DIR / "saved_card_predictions.csv"


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).split())


def norm_name(value: Any) -> str:
    return clean_text(value).lower()


def norm_url(value: Any) -> str:
    text = clean_text(value).replace("https://www.", "https://").replace("http://www.", "http://")
    return text.rstrip("/")


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return clean_text(value).lower() in {"true", "1", "yes", "y"}


def read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _pct(value: float | None) -> str:
    return "" if value is None else f"{value * 100.0:.1f}%"


def _signed_pts(value: float | None) -> str:
    return "" if value is None else f"{value * 100.0:+.1f} pts"


def _empty(message: str) -> dict[str, Any]:
    return {
        "available": False,
        "message": message,
        "scored_clv_fights": 0,
        "beat_close_count": 0,
        "beat_close_rate": None,
        "beat_close_percentage": "",
        "avg_clv_points": None,
        "avg_clv_points_display": "",
        "fights": [],
    }


def build_clv_evaluation() -> dict[str, Any]:
    track = odds_track_repository.read_all_df()

    if track.empty:
        return _empty(
            "No closing-line track yet. CLV accrues once odds are refreshed more than once "
            "per fight (ideally near fight time)."
        )

    saved = saved_predictions_repository.read_all_df()
    results = event_fights_repository.read_all_df()

    pick_by_url: dict[str, str] = {}
    for _, row in saved.iterrows():
        if not parse_bool(row.get("prediction_available", False)):
            continue
        pick_by_url[norm_url(row.get("fight_url", ""))] = clean_text(row.get("predicted_winner", ""))

    winner_by_url: dict[str, str] = {}
    for _, row in results.iterrows():
        winner = clean_text(row.get("winner", ""))
        if winner:
            winner_by_url[norm_url(row.get("fight_url", ""))] = winner

    fights: list[dict[str, Any]] = []

    for _, row in track.iterrows():
        url = norm_url(row.get("fight_url", ""))
        pick = pick_by_url.get(url)
        if not pick:
            continue

        fighter_1 = clean_text(row.get("fighter_1", ""))
        fighter_2 = clean_text(row.get("fighter_2", ""))

        if norm_name(pick) == norm_name(fighter_1):
            open_p = optional_float(row.get("opening_fighter_1_probability"))
            close_p = optional_float(row.get("closing_fighter_1_probability"))
        elif norm_name(pick) == norm_name(fighter_2):
            open_p = optional_float(row.get("opening_fighter_2_probability"))
            close_p = optional_float(row.get("closing_fighter_2_probability"))
        else:
            continue

        if open_p is None or close_p is None:
            continue

        captures = optional_int(row.get("capture_count")) or 1
        clv = close_p - open_p
        winner = winner_by_url.get(url, "")

        fights.append(
            {
                "fight_url": url,
                "fighter_1": fighter_1,
                "fighter_2": fighter_2,
                "predicted_winner": pick,
                "opening_probability": open_p,
                "opening_percentage": _pct(open_p),
                "closing_probability": close_p,
                "closing_percentage": _pct(close_p),
                "clv": clv,
                "clv_points": _signed_pts(clv),
                "beat_close": clv > 0,
                "captures": captures,
                "completed": bool(winner),
                "pick_won": bool(winner) and norm_name(winner) == norm_name(pick),
            }
        )

    # Only fights with a real second capture carry CLV signal; a single capture has
    # opening == closing by construction.
    moved = [f for f in fights if f["captures"] > 1 and abs(f["clv"]) > 1e-6]

    if not moved:
        result = _empty(
            "Picks are being tracked, but no fight has a second (closing) odds capture yet — "
            "refresh odds again closer to an event to record line movement."
        )
        result["tracked_pick_fights"] = len(fights)
        return result

    beat = sum(1 for f in moved if f["beat_close"])
    avg_clv = sum(f["clv"] for f in moved) / len(moved)
    beat_rate = beat / len(moved)

    return {
        "available": True,
        "message": "",
        "tracked_pick_fights": len(fights),
        "scored_clv_fights": len(moved),
        "beat_close_count": beat,
        "beat_close_rate": beat_rate,
        "beat_close_percentage": _pct(beat_rate),
        "avg_clv_points": avg_clv,
        "avg_clv_points_display": _signed_pts(avg_clv),
        "fights": sorted(moved, key=lambda f: f["clv"], reverse=True)[:25],
    }
