"""
Tests for scraped-result ingestion validation (data-contract layer 2):
the structural-failure vs completeness-warning split.

Runs under pytest, or standalone:  python tests/test_data_validation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.data_validation_service import (  # noqa: E402
    validate_scraped_event_fights,
)


def _row(i, **overrides):
    row = {
        "fight_url": f"http://f/{i}",
        "fighter_1": "Ada Striker",
        "fighter_2": "Boz Grappler",
        "winner": "Ada Striker",
        "method": "KO/TKO",
    }
    row.update(overrides)
    return row


def test_complete_event_passes_clean():
    report = validate_scraped_event_fights([_row(1), _row(2)], "UFC Test")
    assert report.ok
    assert report.warnings == []
    assert report.incomplete_rows == 0


def test_zero_fights_is_structural_failure():
    report = validate_scraped_event_fights([], "UFC Test")
    assert not report.ok


def test_missing_names_and_urls_are_structural_failures():
    rows = [_row(1, fighter_1=""), _row(2, fight_url=None)]
    report = validate_scraped_event_fights(rows, "UFC Test")
    assert not report.ok
    assert len(report.failures) == 2


def test_duplicate_fight_url_is_structural_failure():
    report = validate_scraped_event_fights(
        [_row(1), _row(2, fight_url="http://f/1")], "UFC Test"
    )
    assert not report.ok


def test_winner_not_in_bout_is_structural_failure():
    report = validate_scraped_event_fights(
        [_row(1, winner="Cid Wrestler")], "UFC Test"
    )
    assert not report.ok


def test_accented_winner_spelling_still_matches():
    report = validate_scraped_event_fights(
        [_row(1, fighter_1="José Aldo", winner="Jose Aldo")], "UFC Test"
    )
    assert report.ok


def test_results_still_posting_warns_but_passes():
    """The Friday-morning state: some bouts have no winner/method yet. Rows
    are accepted (re-scrape completes them) and the warning carries counts."""
    rows = [
        _row(1),
        _row(2, winner=None, method=None),
        _row(3, winner="Ada Striker", method=float("nan")),
    ]
    report = validate_scraped_event_fights(rows, "UFC Test")
    assert report.ok
    assert report.incomplete_rows == 2
    assert "2 of 3" in report.warnings[0]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all validation tests passed")
