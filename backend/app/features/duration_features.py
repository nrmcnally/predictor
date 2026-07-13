from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd


# Symmetric pre-fight information only. Market totals and prices are deliberately
# absent: the duration distribution must be estimated independently of the book.
DURATION_PAIR_FEATURES = [
    "prior_fights",
    "prior_finish_win_rate",
    "prior_finish_loss_rate",
    "bayes_finish_win_rate",
    "bayes_finish_loss_rate",
    "decayed_finish_win_rate",
    "decayed_finish_loss_rate",
    "avg_fight_duration_seconds",
    "avg_kd_for",
    "avg_kd_against",
    "avg_sig_str_landed_per_15",
    "avg_sig_str_absorbed_per_15",
    "avg_td_landed_per_15",
    "avg_td_absorbed_per_15",
    "avg_sub_att_per_15",
    "avg_ctrl_seconds_per_15",
    "avg_ctrl_absorbed_seconds_per_15",
    "sample_reliability",
    "avg_opponent_adjusted_striking_per_15",
    "avg_opponent_adjusted_striking_defense_per_15",
    "avg_opponent_adjusted_td_per_15",
    "avg_opponent_adjusted_td_defense_per_15",
    "style_pressure_score",
    "style_wrestling_score",
    "style_control_score",
    "path_ko_tko_score",
    "path_submission_score",
    "path_decision_score",
    "vulnerability_ko_tko_score",
    "vulnerability_submission_score",
    "durability_risk_score",
    "volatility_finish_or_finished_rate",
    "age_years",
    "prior_avg_cardio_sig_output_slope",
    "prior_avg_cardio_late_round_share",
    "prior_avg_cardio_rounds_logged",
    "current_vs_recent_weight_class_lbs_delta",
]

DURATION_CONTEXT_FEATURES = [
    "fight_context_scheduled_rounds",
    "fight_context_is_five_round",
    "fight_context_is_main_event",
    "fight_context_card_position_from_top",
    "fight_context_card_position_from_bottom",
    "fight_context_card_size",
]

INTERVAL_NUMERIC_FEATURE = "duration_interval_end_rounds"
INTERVAL_CATEGORICAL_FEATURE = "duration_interval_label"
WEIGHT_CLASS_FEATURE = "weight_class"


def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return np.nan
    return number if np.isfinite(number) else np.nan


def _pair_values(left: Any, right: Any) -> tuple[float, float]:
    values = np.asarray([_number(left), _number(right)], dtype=float)
    finite = values[np.isfinite(values)]
    mean = float(finite.mean()) if len(finite) else np.nan
    gap = float(abs(values[0] - values[1])) if np.isfinite(values).all() else np.nan
    return mean, gap


def duration_numeric_feature_names() -> list[str]:
    names: list[str] = []
    for base in DURATION_PAIR_FEATURES:
        names.extend([f"pair_mean_{base}", f"pair_gap_{base}"])
    names.extend(DURATION_CONTEXT_FEATURES)
    names.append(INTERVAL_NUMERIC_FEATURE)
    return names


def duration_categorical_feature_names() -> list[str]:
    return [WEIGHT_CLASS_FEATURE, INTERVAL_CATEGORICAL_FEATURE]


def build_matchup_duration_features(matchups: pd.DataFrame) -> pd.DataFrame:
    """Build orientation-invariant fight features from a/b training rows."""
    features = pd.DataFrame(index=matchups.index)

    for base in DURATION_PAIR_FEATURES:
        left_source = matchups.get(f"a_{base}")
        right_source = matchups.get(f"b_{base}")
        if left_source is None:
            left = pd.Series(np.nan, index=matchups.index)
        else:
            left = pd.to_numeric(left_source, errors="coerce")
        if right_source is None:
            right = pd.Series(np.nan, index=matchups.index)
        else:
            right = pd.to_numeric(right_source, errors="coerce")
        features[f"pair_mean_{base}"] = pd.concat([left, right], axis=1).mean(
            axis=1, skipna=True
        )
        features[f"pair_gap_{base}"] = (left - right).abs()

    for name in DURATION_CONTEXT_FEATURES:
        source = matchups.get(name)
        features[name] = (
            pd.to_numeric(source, errors="coerce")
            if source is not None
            else np.nan
        )

    weight_class = matchups.get(WEIGHT_CLASS_FEATURE)
    features[WEIGHT_CLASS_FEATURE] = (
        weight_class.fillna("Unknown").astype(str)
        if weight_class is not None
        else "Unknown"
    )
    return features


def build_prediction_duration_features(
    fighter_a: Mapping[str, Any],
    fighter_b: Mapping[str, Any],
    *,
    weight_class: str,
    fight_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the same symmetric feature contract for one future matchup."""
    features: dict[str, Any] = {}

    for base in DURATION_PAIR_FEATURES:
        mean, gap = _pair_values(fighter_a.get(base), fighter_b.get(base))
        features[f"pair_mean_{base}"] = mean
        features[f"pair_gap_{base}"] = gap

    for name in DURATION_CONTEXT_FEATURES:
        features[name] = _number(fight_context.get(name))

    features[WEIGHT_CLASS_FEATURE] = str(weight_class or "Unknown")
    return features


def add_interval_features(
    base_features: Mapping[str, Any], interval_end_rounds: float
) -> dict[str, Any]:
    row = dict(base_features)
    row[INTERVAL_NUMERIC_FEATURE] = float(interval_end_rounds)
    row[INTERVAL_CATEGORICAL_FEATURE] = f"through_{float(interval_end_rounds):.1f}"
    return row
