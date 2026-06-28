"""
Tests for probability-aware prediction grading.

Runs under pytest, or standalone:  python tests/test_prediction_grading.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.prediction_grading import (  # noqa: E402
    brier_for_outcome,
    build_edge_analysis,
    fight_quality,
    grade_predictions,
    letter_grade_for_brier,
)


def test_brier_extremes():
    assert brier_for_outcome(1.0) < 1e-6          # perfect call on the winner
    assert math.isclose(brier_for_outcome(0.5), 0.25, rel_tol=1e-9)  # coin flip
    assert brier_for_outcome(0.0) > 0.99          # called winner ~0%, max error


def test_letter_grades():
    assert letter_grade_for_brier(0.18) == "A+"
    assert letter_grade_for_brier(0.19) == "A"
    assert letter_grade_for_brier(0.205) == "A-"
    assert letter_grade_for_brier(0.225) == "B"
    assert letter_grade_for_brier(0.25) == "C"
    assert letter_grade_for_brier(0.30) == "F"
    assert letter_grade_for_brier(None) == "N/A"


def test_fight_quality_tiers():
    assert fight_quality(0.80)["label"] == "Confident hit"
    assert fight_quality(0.55)["label"] == "Lean hit"
    assert fight_quality(0.42)["label"] == "Close miss"
    assert fight_quality(0.20)["label"] == "Bad miss"


def test_grade_predictions_beat_market():
    # Model put more probability on the actual winners than the market did.
    entries = [
        {"model_p_winner": 0.70, "model_confidence": 0.70, "model_correct": True,
         "market_p_winner": 0.55, "market_correct": True},
        {"model_p_winner": 0.60, "model_confidence": 0.60, "model_correct": True,
         "market_p_winner": 0.45, "market_correct": False},
    ]
    result = grade_predictions(entries)

    assert result["scored_fights"] == 2
    assert math.isclose(result["accuracy"], 1.0, rel_tol=1e-9)
    assert result["model_brier"] < result["market_brier"]
    assert result["verdict"]["code"] == "beat"
    assert result["brier_skill_vs_market"] > 0
    # expected wins = sum of confidences = 1.30
    assert math.isclose(result["expected_correct"], 1.30, rel_tol=1e-9)
    assert result["actual_correct"] == 2


def test_grade_predictions_behind_market():
    entries = [
        {"model_p_winner": 0.40, "model_confidence": 0.60, "model_correct": False,
         "market_p_winner": 0.75, "market_correct": True},
    ]
    result = grade_predictions(entries)
    assert result["verdict"]["code"] == "behind"
    assert result["model_brier"] > result["market_brier"]


def test_grade_predictions_no_market():
    entries = [
        {"model_p_winner": 0.65, "model_confidence": 0.65, "model_correct": True},
    ]
    result = grade_predictions(entries)
    assert result["market_brier"] is None
    assert result["verdict"]["code"] == "no_market"
    assert result["market_grade"] == "N/A"


def test_edge_analysis_splits_and_grades():
    entries = [
        # Agreed with market (both favored the winner), model sharper.
        {"model_p_winner": 0.70, "model_correct": True, "market_p_winner": 0.60,
         "market_correct": True, "agree_with_market": True},
        # Disagreed: model took the underdog and lost -> behind the market here.
        {"model_p_winner": 0.40, "model_correct": False, "market_p_winner": 0.65,
         "market_correct": True, "agree_with_market": False},
        # No odds -> excluded from edge analysis entirely.
        {"model_p_winner": 0.55, "model_correct": True},
    ]
    edge = build_edge_analysis(entries)

    assert edge["comparable_fights"] == 2
    assert edge["agreement_count"] == 1
    assert edge["disagreement_count"] == 1
    assert edge["disagree"]["count"] == 1
    assert edge["disagree"]["model_won_count"] == 0
    assert edge["disagree"]["verdict"]["code"] == "behind"
    assert edge["small_sample"] is True


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
