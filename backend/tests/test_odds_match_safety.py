"""
Tests for odds->fighter match safety (ROADMAP §8b Phase 0, item #3).

The matcher must require BOTH fighters to clear the name-similarity bar
individually, so a perfect match on one fighter can't drag a weak match on the
other over the line. Borderline-but-accepted matches must be flagged.

Runs under pytest, or standalone:  python tests/test_odds_match_safety.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.services.odds_service as odds  # noqa: E402


def _fake_similarity(mapping):
    """Return a name_similarity stand-in driven by an (left, right) -> score map."""

    def similarity(left, right):
        return mapping.get((left, right), 0.0)

    return similarity


def test_both_fighters_must_match_not_just_average():
    event = {"home_team": "A", "away_team": "B"}
    original = odds.name_similarity
    try:
        # F1 matches home perfectly; F2 matches away only 0.78.
        odds.name_similarity = _fake_similarity(
            {("A", "F1"): 1.0, ("B", "F2"): 0.78}
        )
        is_match, avg_score, weaker_score = odds.odds_event_matches_fight(
            event, "F1", "F2"
        )
        # Average is 0.89 -> the OLD average-only rule would have accepted this.
        assert avg_score >= 0.88
        # But the weaker fighter (0.78) is below the per-fighter bar, so reject.
        assert weaker_score == 0.78
        assert is_match is False
    finally:
        odds.name_similarity = original


def test_clean_match_accepted():
    event = {"home_team": "A", "away_team": "B"}
    original = odds.name_similarity
    try:
        odds.name_similarity = _fake_similarity(
            {("A", "F1"): 0.97, ("B", "F2"): 0.95}
        )
        is_match, _avg, weaker_score = odds.odds_event_matches_fight(event, "F1", "F2")
        assert is_match is True
        assert weaker_score == 0.95
    finally:
        odds.name_similarity = original


def test_swapped_orientation_matches():
    # The odds feed's home/away order may be reversed vs our fighter_1/fighter_2.
    event = {"home_team": "A", "away_team": "B"}
    original = odds.name_similarity
    try:
        odds.name_similarity = _fake_similarity(
            {("A", "F2"): 0.96, ("B", "F1"): 0.95}
        )
        is_match, _avg, weaker_score = odds.odds_event_matches_fight(event, "F1", "F2")
        assert is_match is True
        assert weaker_score == 0.95
    finally:
        odds.name_similarity = original


def test_low_confidence_match_is_flagged():
    event = {"home_team": "A", "away_team": "B", "id": "e1", "commence_time": "t", "bookmakers": []}
    fight_row = pd.Series({"fighter_1": "F1", "fighter_2": "F2"})
    original = odds.name_similarity
    try:
        # Both clear the per-fighter bar (0.85) but the weaker is below the
        # low-confidence comfort threshold (0.92) -> accepted but flagged.
        odds.name_similarity = _fake_similarity(
            {("A", "F1"): 0.88, ("B", "F2"): 0.88}
        )
        row = odds.build_odds_row_for_fight(fight_row, [event])
        assert row["odds_match_low_confidence"] is True
        assert row["odds_match_min_score"] == 0.88
    finally:
        odds.name_similarity = original


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
