from __future__ import annotations

"""
Style-matchup interaction features.

The winner model otherwise sees only per-fighter *differences* (A's trait minus
B's trait), which is linear and cannot express "A's takedowns will land because B
specifically has poor takedown defense." These features are explicit cross terms:
one fighter's offensive trait multiplied by the opponent's complementary weakness.

They are matchup-level (computed from both fighters' pre-fight snapshot rows), so
they are leakage-safe as long as the input rows are pre-fight snapshots — exactly
what both the training builder and the live predictor pass in.

CRITICAL: this is the single source of truth used by BOTH training
(build_matchups) and inference (prediction_service). Keeping one implementation is
what prevents train/serve skew.

All features are written from fighter A's perspective. The mirrored training rows
and the two-orientation prediction both call this with the fighters swapped, so the
asymmetric features are covered in both directions.
"""

from typing import Any

import pandas as pd


INTERACTION_FEATURE_COLUMNS = [
    "xint_a_takedown_vs_def",
    "xint_a_ko_threat_vs_chin",
    "xint_a_sub_threat_vs_vuln",
    "xint_a_striking_vs_def",
    "xint_stance_southpaw_edge",
    "xint_reach_x_distance",
]


def _num(row: Any, column: str) -> float | None:
    value = row.get(column) if hasattr(row, "get") else None

    if value is None or pd.isna(value):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number


def _product(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None

    return float(left * right)


def empty_interaction_features() -> dict[str, Any]:
    return {column: None for column in INTERACTION_FEATURE_COLUMNS}


def compute_interaction_features(
    fighter_a_row: Any,
    fighter_b_row: Any,
) -> dict[str, Any]:
    a_td_landed = _num(fighter_a_row, "avg_td_landed_per_15")
    b_td_defense = _num(fighter_b_row, "bayes_td_defense")
    b_td_allowed_rate = None if b_td_defense is None else (1.0 - b_td_defense)

    a_ko_threat = _num(fighter_a_row, "path_ko_tko_score")
    b_ko_vulnerability = _num(fighter_b_row, "vulnerability_ko_tko_score")

    a_sub_threat = _num(fighter_a_row, "path_submission_score")
    b_sub_vulnerability = _num(fighter_b_row, "vulnerability_submission_score")

    a_striking = _num(fighter_a_row, "avg_sig_str_landed_per_15")
    b_sig_defense = _num(fighter_b_row, "bayes_sig_str_defense")
    b_sig_allowed_rate = None if b_sig_defense is None else (1.0 - b_sig_defense)

    a_southpaw = _num(fighter_a_row, "is_southpaw") or 0.0
    a_orthodox = _num(fighter_a_row, "is_orthodox") or 0.0
    b_southpaw = _num(fighter_b_row, "is_southpaw") or 0.0
    b_orthodox = _num(fighter_b_row, "is_orthodox") or 0.0
    # +1 when A (southpaw) holds the open-stance edge over an orthodox B,
    # -1 in the reverse, 0 when stances match or are unknown.
    stance_edge = (a_southpaw * b_orthodox) - (a_orthodox * b_southpaw)

    a_reach = _num(fighter_a_row, "reach_inches")
    b_reach = _num(fighter_b_row, "reach_inches")
    a_distance_striking = _num(fighter_a_row, "avg_distance_landed_per_15")
    reach_advantage = (
        None if a_reach is None or b_reach is None else (a_reach - b_reach)
    )

    return {
        # A's takedown volume amplified by how often B gets taken down.
        "xint_a_takedown_vs_def": _product(a_td_landed, b_td_allowed_rate),
        # A's knockout path against B's chin/durability risk.
        "xint_a_ko_threat_vs_chin": _product(a_ko_threat, b_ko_vulnerability),
        # A's submission path against B's submission vulnerability.
        "xint_a_sub_threat_vs_vuln": _product(a_sub_threat, b_sub_vulnerability),
        # A's striking volume amplified by how often B gets hit.
        "xint_a_striking_vs_def": _product(a_striking, b_sig_allowed_rate),
        # Directional southpaw/orthodox open-stance edge.
        "xint_stance_southpaw_edge": float(stance_edge),
        # Reach advantage only matters to the extent A fights at distance.
        "xint_reach_x_distance": _product(reach_advantage, a_distance_striking),
    }
