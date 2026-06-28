from __future__ import annotations

"""
Strength-of-schedule (competition quality) features.

Raw win rate and even Elo are competition-blind in subtle ways: a 1600-Elo fighter
who padded a record against cans looks the same on some axes as one who beat killers.
These features describe *who a fighter has faced and beaten so far*, using each past
opponent's pre-fight Elo (the opponent's rating at the time of that fight).

Leakage-safety: the caller must pass only the fighter's history of fights that
happened strictly before the fight being described, and must pass the opponent's
*pre-fight* Elo (rating before that past fight resolved). Built this way, every value
is knowable before the current fight starts.
"""

from typing import Any


SOS_FEATURE_COLUMNS = [
    "prior_avg_opponent_elo",
    "prior_recent3_avg_opponent_elo",
    "prior_max_opponent_elo",
    "prior_avg_beaten_opponent_elo",
]


def empty_sos_features() -> dict[str, Any]:
    return {column: None for column in SOS_FEATURE_COLUMNS}


def compute_sos_features(
    opp_elo_history: list[float],
    result_history: list[int],
) -> dict[str, Any]:
    """
    opp_elo_history: pre-fight Elo of each prior opponent, oldest first.
    result_history:  1 if the fighter won that prior fight, else 0 (same order).
    """
    if not opp_elo_history:
        return empty_sos_features()

    average_opponent_elo = sum(opp_elo_history) / len(opp_elo_history)

    recent_opponents = opp_elo_history[-3:]
    recent_average_opponent_elo = sum(recent_opponents) / len(recent_opponents)

    beaten_opponent_elos = [
        opponent_elo
        for opponent_elo, won in zip(opp_elo_history, result_history)
        if won == 1
    ]

    average_beaten_opponent_elo = (
        sum(beaten_opponent_elos) / len(beaten_opponent_elos)
        if beaten_opponent_elos
        else None
    )

    return {
        "prior_avg_opponent_elo": float(average_opponent_elo),
        "prior_recent3_avg_opponent_elo": float(recent_average_opponent_elo),
        "prior_max_opponent_elo": float(max(opp_elo_history)),
        "prior_avg_beaten_opponent_elo": (
            float(average_beaten_opponent_elo)
            if average_beaten_opponent_elo is not None
            else None
        ),
    }
