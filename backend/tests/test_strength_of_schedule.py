"""
Tests for strength-of-schedule features (opponent-Elo quality / quality of wins).

Runs under pytest, or standalone:  python tests/test_strength_of_schedule.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.strength_of_schedule import (  # noqa: E402
    compute_sos_features,
    empty_sos_features,
)


def test_empty_history_is_all_none():
    result = compute_sos_features([], [])
    assert result == empty_sos_features()
    assert all(value is None for value in result.values())


def test_sos_aggregates():
    # Faced opponents at Elo 1500, 1600, 1400; won the 1st and 3rd, lost the 2nd.
    result = compute_sos_features([1500.0, 1600.0, 1400.0], [1, 0, 1])

    assert result["prior_avg_opponent_elo"] == 1500.0           # mean of all three
    assert result["prior_max_opponent_elo"] == 1600.0           # toughest faced
    assert result["prior_recent3_avg_opponent_elo"] == 1500.0   # last 3 = all
    assert result["prior_avg_beaten_opponent_elo"] == 1450.0    # mean of beaten (1500, 1400)


def test_recent3_uses_only_last_three():
    # Five opponents; recent3 must average only the last three (1300, 1200, 1100).
    result = compute_sos_features([1700.0, 1600.0, 1300.0, 1200.0, 1100.0], [1, 1, 1, 1, 1])
    assert result["prior_recent3_avg_opponent_elo"] == 1200.0
    assert result["prior_max_opponent_elo"] == 1700.0


def test_no_wins_yet_leaves_beaten_none():
    result = compute_sos_features([1500.0, 1600.0], [0, 0])
    assert result["prior_avg_beaten_opponent_elo"] is None
    assert result["prior_avg_opponent_elo"] == 1550.0


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
