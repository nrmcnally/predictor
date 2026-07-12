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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.odds_service import (  # noqa: E402
    aggregate_totals,
    get_bookmaker_totals,
)


def _book(key, line, over_price, under_price):
    return {
        "key": key,
        "title": key.title(),
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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all totals tests passed")
