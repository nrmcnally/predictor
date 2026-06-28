from __future__ import annotations

"""
Probability-aware grading for saved pre-fight predictions.

Plain accuracy (right/wrong) throws away the probabilities we saved and punishes
honest uncertainty: a correctly-called 95% favorite and a coin-flip that happened
to land both score as one "correct". This module grades the saved probabilities
with proper scoring rules (Brier score, log loss), turns them into digestible
letter grades on a UFC-calibrated scale, and compares the engine against the market
on the same scale.

Brier score = mean of (1 - p_assigned_to_actual_winner)^2. Lower is better.
  - always 50% (no skill)         -> 0.250
  - decent independent model       -> ~0.215-0.225
  - sharp market                   -> ~0.200-0.210
  - near the irreducible UFC floor -> ~0.180

The letter-grade thresholds below are hand-set anchors to that reality, not a
learned scale — they are meant to be read as "how good were these probabilities
for MMA", where MMA is genuinely chaotic and even perfect play caps out well above
zero error.
"""

import math
from typing import Any


# Ordered best -> worst. Each tuple is (max_brier_inclusive, letter).
_GRADE_THRESHOLDS: list[tuple[float, str]] = [
    (0.180, "A+"),
    (0.195, "A"),
    (0.205, "A-"),
    (0.215, "B+"),
    (0.225, "B"),
    (0.235, "B-"),
    (0.245, "C+"),
    (0.250, "C"),
    (0.260, "D"),
]


def clamp_probability(probability: float, epsilon: float = 1e-6) -> float:
    return max(epsilon, min(1.0 - epsilon, float(probability)))


def brier_for_outcome(probability_assigned_to_winner: float) -> float:
    """Squared error of the probability placed on the fighter who actually won."""
    p = clamp_probability(probability_assigned_to_winner)
    return float((1.0 - p) ** 2)


def log_loss_for_outcome(probability_assigned_to_winner: float) -> float:
    p = clamp_probability(probability_assigned_to_winner)
    return float(-math.log(p))


def letter_grade_for_brier(brier: float | None) -> str:
    if brier is None:
        return "N/A"

    for max_brier, letter in _GRADE_THRESHOLDS:
        if brier <= max_brier:
            return letter

    return "F"


def grade_tone(letter: str) -> str:
    """Maps a letter grade to a frontend Tag tone."""
    if letter.startswith("A"):
        return "win"
    if letter.startswith("B"):
        return "gold"
    if letter.startswith("C"):
        return "warn"
    return "loss"


def fight_quality(probability_assigned_to_winner: float | None) -> dict[str, str]:
    """A digestible per-fight verdict that respects the probability, not just W/L."""
    if probability_assigned_to_winner is None:
        return {"label": "", "tone": "neutral"}

    p = float(probability_assigned_to_winner)

    if p >= 0.62:
        return {"label": "Confident hit", "tone": "win"}
    if p >= 0.50:
        return {"label": "Lean hit", "tone": "gold"}
    if p >= 0.38:
        return {"label": "Close miss", "tone": "warn"}

    return {"label": "Bad miss", "tone": "loss"}


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _brier_skill_score(model_brier: float | None, reference_brier: float | None) -> float | None:
    """Positive means the model's probabilities beat the reference (e.g. market)."""
    if model_brier is None or reference_brier is None or reference_brier <= 0:
        return None
    return float((reference_brier - model_brier) / reference_brier)


def _verdict(model_brier: float | None, market_brier: float | None) -> dict[str, Any]:
    if model_brier is None or market_brier is None:
        return {"label": "No market to compare", "tone": "neutral", "code": "no_market"}

    delta = model_brier - market_brier  # negative = model better (lower error)

    if delta < -0.005:
        return {"label": "Beat the market", "tone": "win", "code": "beat"}
    if delta > 0.005:
        return {"label": "Behind the market", "tone": "loss", "code": "behind"}

    return {"label": "Matched the market", "tone": "gold", "code": "matched"}


def _edge_subset(entries: list[dict[str, Any]]) -> dict[str, Any]:
    model_probs = [e["model_p_winner"] for e in entries if e.get("model_p_winner") is not None]
    market_probs = [e["market_p_winner"] for e in entries if e.get("market_p_winner") is not None]

    model_brier = _mean([brier_for_outcome(p) for p in model_probs])
    market_brier = _mean([brier_for_outcome(p) for p in market_probs])

    model_correct = [bool(e["model_correct"]) for e in entries if e.get("model_correct") is not None]
    market_correct = [bool(e["market_correct"]) for e in entries if e.get("market_correct") is not None]

    return {
        "count": len(entries),
        "model_won_count": sum(1 for c in model_correct if c),
        "model_accuracy": _mean([1.0 if c else 0.0 for c in model_correct]),
        "market_accuracy": _mean([1.0 if c else 0.0 for c in market_correct]),
        "model_brier": model_brier,
        "market_brier": market_brier,
        "verdict": _verdict(model_brier, market_brier),
    }


def build_edge_analysis(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Splits scored fights by whether the model agreed with the market favorite.

    Edge can only exist where the model DISAGREES with the market — that is the
    only subset where the model is making a different bet. On agreements the two
    pick the same fighter, so the only difference is confidence.
    """
    comparable = [
        e
        for e in entries
        if e.get("agree_with_market") is not None and e.get("market_p_winner") is not None
    ]

    agree = [e for e in comparable if e["agree_with_market"]]
    disagree = [e for e in comparable if not e["agree_with_market"]]

    disagreement_rate = (len(disagree) / len(comparable)) if comparable else None

    return {
        "comparable_fights": len(comparable),
        "agreement_count": len(agree),
        "disagreement_count": len(disagree),
        "disagreement_rate": disagreement_rate,
        "disagreement_rate_percentage": f"{disagreement_rate * 100:.0f}%"
        if disagreement_rate is not None
        else "",
        "agree": _edge_subset(agree),
        "disagree": _edge_subset(disagree),
        # Below ~20 disagreement fights, any conclusion is mostly variance.
        "small_sample": len(disagree) < 20,
    }


def grade_predictions(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """
    entries: one dict per scored fight (a fight with an actual winner and a saved
    prediction). Recognised keys:
        model_p_winner   probability the model gave the actual winner (required)
        model_confidence probability the model gave its own pick (for expected wins)
        model_correct    bool
        market_p_winner  probability the market gave the actual winner (optional)
        market_correct   bool | None
    """
    model_probs = [e["model_p_winner"] for e in entries if e.get("model_p_winner") is not None]
    market_probs = [e["market_p_winner"] for e in entries if e.get("market_p_winner") is not None]

    model_brier = _mean([brier_for_outcome(p) for p in model_probs])
    model_log_loss = _mean([log_loss_for_outcome(p) for p in model_probs])
    market_brier = _mean([brier_for_outcome(p) for p in market_probs])
    market_log_loss = _mean([log_loss_for_outcome(p) for p in market_probs])

    correct_flags = [bool(e["model_correct"]) for e in entries if e.get("model_correct") is not None]
    accuracy = _mean([1.0 if c else 0.0 for c in correct_flags])

    market_flags = [bool(e["market_correct"]) for e in entries if e.get("market_correct") is not None]
    market_accuracy = _mean([1.0 if c else 0.0 for c in market_flags])

    # Expected wins = sum of the probability the model gave to its OWN pick.
    confidences = [e["model_confidence"] for e in entries if e.get("model_confidence") is not None]
    expected_correct = sum(confidences) if confidences else None
    actual_correct = sum(1 for c in correct_flags if c)

    engine_letter = letter_grade_for_brier(model_brier)
    market_letter = letter_grade_for_brier(market_brier)

    return {
        "scored_fights": len(model_probs),
        "market_scored_fights": len(market_probs),
        "accuracy": accuracy,
        "accuracy_percentage": f"{accuracy * 100:.1f}%" if accuracy is not None else "",
        "market_accuracy": market_accuracy,
        "market_accuracy_percentage": f"{market_accuracy * 100:.1f}%" if market_accuracy is not None else "",
        "model_brier": model_brier,
        "model_log_loss": model_log_loss,
        "market_brier": market_brier,
        "market_log_loss": market_log_loss,
        "engine_grade": engine_letter,
        "engine_grade_tone": grade_tone(engine_letter),
        "market_grade": market_letter,
        "market_grade_tone": grade_tone(market_letter),
        "brier_skill_vs_market": _brier_skill_score(model_brier, market_brier),
        "verdict": _verdict(model_brier, market_brier),
        "expected_correct": expected_correct,
        "expected_correct_display": f"{expected_correct:.1f}" if expected_correct is not None else "",
        "actual_correct": actual_correct,
    }
