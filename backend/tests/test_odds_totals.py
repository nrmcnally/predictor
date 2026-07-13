"""
Tests for the rounds over/under (totals) market extraction and aggregation:
per-book de-vig, missing/partial quotes, and the consensus-line rule when
books quote different lines.

Runs under pytest, or standalone:  python tests/test_odds_totals.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.odds_service import (  # noqa: E402
    aggregate_totals,
    build_odds_row_for_fight,
    build_totals_snapshot_rows,
    get_bookmaker_totals,
)


def _book(key, line, over_price, under_price):
    return {
        "key": key,
        "title": key.title(),
        "last_update": f"{key}-updated",
        "markets": [
            {
                "key": "totals",
                "outcomes": [
                    {"name": "Over", "price": over_price, "point": line},
                    {"name": "Under", "price": under_price, "point": line},
                ],
            }
        ],
    }


def test_bookmaker_totals_devig():
    quote = get_bookmaker_totals(_book("draftkings", 2.5, -140, +110))
    assert quote is not None
    assert quote["rounds_line"] == 2.5
    # -140 implies .5833, +110 implies .4762; de-vigged they must sum to 1
    assert math.isclose(
        quote["over_market_probability"] + quote["under_market_probability"], 1.0
    )
    assert quote["over_market_probability"] > quote["under_market_probability"]


def test_bookmaker_without_totals_market_is_skipped():
    h2h_only = {
        "key": "fanduel",
        "title": "FanDuel",
        "markets": [{"key": "h2h", "outcomes": []}],
    }
    assert get_bookmaker_totals(h2h_only) is None
    assert aggregate_totals([h2h_only]) is None


def test_partial_outcomes_are_skipped():
    over_only = _book("betmgm", 1.5, -120, +100)
    over_only["markets"][0]["outcomes"] = over_only["markets"][0]["outcomes"][:1]
    assert get_bookmaker_totals(over_only) is None


def test_consensus_line_wins_and_averages_only_matching_books():
    books = [
        _book("draftkings", 2.5, -140, +110),
        _book("fanduel", 2.5, -150, +120),
        _book("betmgm", 1.5, -200, +160),
    ]
    result = aggregate_totals(books)
    assert result["rounds_line"] == 2.5
    assert result["totals_bookmakers_matched"] == 2
    # representative comes from the preferred-book order (draftkings first)
    assert result["over_odds_american"] == -140
    assert result["over_market_percentage"].endswith("%")


def test_aggregate_empty_is_none():
    assert aggregate_totals([]) is None


def _event(books):
    return {
        "id": "odds-event-1",
        "commence_time": "2026-07-20T00:00:00Z",
        "home_team": "A Fighter",
        "away_team": "B Fighter",
        "bookmakers": books,
    }


def _fight():
    return {
        "event_name": "UFC Test",
        "event_date": "July 19, 2026",
        "event_url": "event-1",
        "fight_url": "fight-1",
        "fighter_1": "A Fighter",
        "fighter_2": "B Fighter",
        "weight_class": "Lightweight",
    }


def test_history_rows_keep_non_consensus_book_lines():
    books = [
        _book("draftkings", 2.5, -140, +110),
        _book("fanduel", 1.5, -180, +145),
    ]
    rows = build_totals_snapshot_rows(
        pd.DataFrame([_fight()]), [_event(books)], captured_at="capture-1"
    )
    assert len(rows) == 2
    assert {row["rounds_line"] for row in rows} == {1.5, 2.5}
    assert {row["bookmaker_last_update"] for row in rows} == {
        "draftkings-updated",
        "fanduel-updated",
    }


def test_totals_survive_when_event_has_no_h2h_quote():
    row = build_odds_row_for_fight(
        pd.Series(_fight()), [_event([_book("draftkings", 4.5, -110, -110)])]
    )
    assert row["odds_available"] is False
    assert row["rounds_line"] == 4.5
    assert row["totals_bookmakers_matched"] == 1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all totals tests passed")
