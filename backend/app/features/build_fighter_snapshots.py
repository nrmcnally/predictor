from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

FIGHT_STATS_CSV = RAW_DATA_DIR / "fight_stats.csv"
FIGHTER_SNAPSHOTS_CSV = PROCESSED_DATA_DIR / "fighter_snapshots.csv"


@dataclass
class FighterSnapshot:
    fight_url: str
    event_name: str
    event_date: str
    fighter: str
    opponent: str
    weight_class: str
    method: str

    target_is_winner: int

    prior_fights: int
    prior_wins: int
    prior_losses: int
    prior_decisive_results: int
    prior_unscored_results: int
    prior_win_rate: float | None

    days_since_last_fight: float | None

    prior_finish_wins: int
    prior_finish_losses: int
    prior_finish_win_rate: float | None
    prior_finish_loss_rate: float | None

    avg_fight_duration_seconds: float | None

    avg_kd_for: float | None
    avg_kd_against: float | None

    avg_sig_str_landed_per_15: float | None
    avg_sig_str_attempted_per_15: float | None
    avg_sig_str_absorbed_per_15: float | None
    avg_sig_str_defense: float | None
    avg_sig_str_accuracy: float | None
    avg_sig_str_differential_per_15: float | None

    avg_total_str_landed_per_15: float | None
    avg_total_str_absorbed_per_15: float | None

    avg_td_landed_per_15: float | None
    avg_td_attempted_per_15: float | None
    avg_td_absorbed_per_15: float | None
    avg_td_accuracy: float | None
    avg_td_defense: float | None

    avg_sub_att_per_15: float | None
    avg_ctrl_seconds_per_15: float | None
    avg_ctrl_absorbed_seconds_per_15: float | None

    avg_head_landed_per_15: float | None
    avg_body_landed_per_15: float | None
    avg_leg_landed_per_15: float | None

    avg_distance_landed_per_15: float | None
    avg_clinch_landed_per_15: float | None
    avg_ground_landed_per_15: float | None

    recent_3_win_rate: float | None
    recent_5_win_rate: float | None

    recent_3_sig_str_differential_per_15: float | None
    recent_5_sig_str_differential_per_15: float | None

    recent_3_td_differential_per_15: float | None
    recent_5_td_differential_per_15: float | None

    sample_reliability: float | None

    bayes_win_rate: float | None
    bayes_finish_win_rate: float | None
    bayes_finish_loss_rate: float | None
    bayes_ko_tko_win_rate: float | None
    bayes_ko_tko_loss_rate: float | None
    bayes_submission_win_rate: float | None
    bayes_submission_loss_rate: float | None
    bayes_decision_win_rate: float | None
    bayes_sig_str_accuracy: float | None
    bayes_sig_str_defense: float | None
    bayes_td_accuracy: float | None
    bayes_td_defense: float | None

    decayed_win_rate: float | None
    decayed_finish_win_rate: float | None
    decayed_finish_loss_rate: float | None
    decayed_sig_str_differential_per_15: float | None
    decayed_td_differential_per_15: float | None
    decayed_ctrl_differential_per_15: float | None

    avg_opponent_adjusted_striking_per_15: float | None
    avg_opponent_adjusted_striking_defense_per_15: float | None
    avg_opponent_adjusted_td_per_15: float | None
    avg_opponent_adjusted_td_defense_per_15: float | None
    avg_opponent_adjusted_control_per_15: float | None
    avg_opponent_adjusted_control_defense_per_15: float | None

    recent_3_opponent_adjusted_striking_per_15: float | None
    recent_3_opponent_adjusted_td_per_15: float | None

    style_pressure_score: float | None
    style_wrestling_score: float | None
    style_control_score: float | None
    path_ko_tko_score: float | None
    path_submission_score: float | None
    path_decision_score: float | None
    vulnerability_ko_tko_score: float | None
    vulnerability_submission_score: float | None
    durability_risk_score: float | None
    volatility_finish_or_finished_rate: float | None
    volatility_performance_variance: float | None


def clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""

    return " ".join(str(value).split())


def safe_divide(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator is None:
        return None

    if denominator == 0:
        return None

    if pd.isna(numerator) or pd.isna(denominator):
        return None

    return float(numerator) / float(denominator)


def parse_time_to_seconds(value: Any) -> int | None:
    value = clean_text(value)

    if not value or ":" not in value:
        return None

    minutes_text, seconds_text = value.split(":", 1)

    try:
        minutes = int(minutes_text)
        seconds = int(seconds_text)
    except ValueError:
        return None

    return minutes * 60 + seconds


def calculate_fight_duration_seconds(row: pd.Series) -> int | None:
    """
    Calculates elapsed fight time.

    Example:
        Round 2, time 3:15 means:
        one completed round + 3:15
        300 + 195 = 495 seconds
    """
    try:
        round_number = int(row["round"])
    except ValueError:
        return None

    round_time_seconds = parse_time_to_seconds(row["time"])

    if round_time_seconds is None:
        return None

    completed_rounds = max(round_number - 1, 0)

    return completed_rounds * 300 + round_time_seconds


def is_finish_method(method: Any) -> bool:
    method_text = clean_text(method).lower()

    finish_keywords = [
        "ko/tko",
        "submission",
        "sub",
        "tko",
        "ko",
    ]

    return any(keyword in method_text for keyword in finish_keywords)


def is_ko_tko_method(method: Any) -> bool:
    method_text = clean_text(method).lower()

    return "ko/tko" in method_text or method_text in {"ko", "tko"}


def is_submission_method(method: Any) -> bool:
    method_text = clean_text(method).lower()

    return "submission" in method_text or "sub" in method_text


def is_decision_method(method: Any) -> bool:
    method_text = clean_text(method).lower()

    return "dec" in method_text


def per_15(value: Any, duration_seconds: Any) -> float | None:
    if pd.isna(value) or pd.isna(duration_seconds):
        return None

    if duration_seconds == 0:
        return None

    return float(value) / float(duration_seconds) * 900.0


def add_opponent_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds columns showing what the opponent did in the same fight.

    This lets us calculate:
        strikes absorbed
        takedowns absorbed
        control time absorbed
        knockdowns absorbed
    """
    opponent_columns = [
        "fight_url",
        "fighter",
        "opponent",
        "kd",
        "sig_str_landed",
        "sig_str_attempted",
        "total_str_landed",
        "total_str_attempted",
        "td_landed",
        "td_attempted",
        "sub_att",
        "ctrl_seconds",
    ]

    opponent_df = df[opponent_columns].copy()

    opponent_df = opponent_df.rename(
        columns={
            "fighter": "opponent",
            "opponent": "fighter",
            "kd": "opp_kd",
            "sig_str_landed": "opp_sig_str_landed",
            "sig_str_attempted": "opp_sig_str_attempted",
            "total_str_landed": "opp_total_str_landed",
            "total_str_attempted": "opp_total_str_attempted",
            "td_landed": "opp_td_landed",
            "td_attempted": "opp_td_attempted",
            "sub_att": "opp_sub_att",
            "ctrl_seconds": "opp_ctrl_seconds",
        }
    )

    return df.merge(
        opponent_df,
        on=["fight_url", "fighter", "opponent"],
        how="left",
    )


def add_engineered_fight_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["event_date_parsed"] = pd.to_datetime(df["event_date"], errors="coerce")

    df["fight_duration_seconds"] = df.apply(calculate_fight_duration_seconds, axis=1)

    if "result" in df.columns:
        result_text = df["result"].apply(lambda value: clean_text(value).lower())
        df["is_win"] = result_text.eq("win").astype(int)
        df["is_loss"] = result_text.eq("loss").astype(int)
    else:
        is_winner = pd.to_numeric(df.get("is_winner", 0), errors="coerce").fillna(0)
        df["is_win"] = is_winner.eq(1).astype(int)
        df["is_loss"] = is_winner.eq(0).astype(int)

    df["is_decisive_result"] = ((df["is_win"] == 1) | (df["is_loss"] == 1)).astype(int)
    df["is_unscored_result"] = (df["is_decisive_result"] == 0).astype(int)

    df["is_finish"] = df["method"].apply(is_finish_method)
    df["finish_win"] = ((df["is_win"] == 1) & df["is_finish"]).astype(int)
    df["finish_loss"] = ((df["is_loss"] == 1) & df["is_finish"]).astype(int)

    df["is_ko_tko"] = df["method"].apply(is_ko_tko_method)
    df["is_submission"] = df["method"].apply(is_submission_method)
    df["is_decision"] = df["method"].apply(is_decision_method)

    df["ko_tko_win"] = ((df["is_win"] == 1) & df["is_ko_tko"]).astype(int)
    df["ko_tko_loss"] = ((df["is_loss"] == 1) & df["is_ko_tko"]).astype(int)
    df["submission_win"] = ((df["is_win"] == 1) & df["is_submission"]).astype(int)
    df["submission_loss"] = ((df["is_loss"] == 1) & df["is_submission"]).astype(int)
    df["decision_win"] = ((df["is_win"] == 1) & df["is_decision"]).astype(int)
    df["decision_loss"] = ((df["is_loss"] == 1) & df["is_decision"]).astype(int)
    df["finish_or_finished"] = ((df["finish_win"] == 1) | (df["finish_loss"] == 1)).astype(int)

    df["kd_against"] = df["opp_kd"]

    df["sig_str_absorbed"] = df["opp_sig_str_landed"]
    df["total_str_absorbed"] = df["opp_total_str_landed"]

    df["td_absorbed"] = df["opp_td_landed"]
    df["ctrl_absorbed_seconds"] = df["opp_ctrl_seconds"]

    df["sig_str_landed_per_15"] = df.apply(
        lambda row: per_15(row["sig_str_landed"], row["fight_duration_seconds"]),
        axis=1,
    )
    df["sig_str_attempted_per_15"] = df.apply(
        lambda row: per_15(row["sig_str_attempted"], row["fight_duration_seconds"]),
        axis=1,
    )
    df["sig_str_absorbed_per_15"] = df.apply(
        lambda row: per_15(row["sig_str_absorbed"], row["fight_duration_seconds"]),
        axis=1,
    )

    df["sig_str_differential_per_15"] = (
        df["sig_str_landed_per_15"] - df["sig_str_absorbed_per_15"]
    )

    df["total_str_landed_per_15"] = df.apply(
        lambda row: per_15(row["total_str_landed"], row["fight_duration_seconds"]),
        axis=1,
    )
    df["total_str_absorbed_per_15"] = df.apply(
        lambda row: per_15(row["total_str_absorbed"], row["fight_duration_seconds"]),
        axis=1,
    )

    df["td_landed_per_15"] = df.apply(
        lambda row: per_15(row["td_landed"], row["fight_duration_seconds"]),
        axis=1,
    )
    df["td_attempted_per_15"] = df.apply(
        lambda row: per_15(row["td_attempted"], row["fight_duration_seconds"]),
        axis=1,
    )
    df["td_absorbed_per_15"] = df.apply(
        lambda row: per_15(row["td_absorbed"], row["fight_duration_seconds"]),
        axis=1,
    )

    df["td_differential_per_15"] = df["td_landed_per_15"] - df["td_absorbed_per_15"]

    df["sub_att_per_15"] = df.apply(
        lambda row: per_15(row["sub_att"], row["fight_duration_seconds"]),
        axis=1,
    )
    df["ctrl_seconds_per_15"] = df.apply(
        lambda row: per_15(row["ctrl_seconds"], row["fight_duration_seconds"]),
        axis=1,
    )
    df["ctrl_absorbed_seconds_per_15"] = df.apply(
        lambda row: per_15(row["ctrl_absorbed_seconds"], row["fight_duration_seconds"]),
        axis=1,
    )
    df["ctrl_differential_per_15"] = (
        df["ctrl_seconds_per_15"] - df["ctrl_absorbed_seconds_per_15"]
    )

    for column in [
        "head_landed",
        "body_landed",
        "leg_landed",
        "distance_landed",
        "clinch_landed",
        "ground_landed",
    ]:
        df[f"{column}_per_15"] = df.apply(
            lambda row: per_15(row[column], row["fight_duration_seconds"]),
            axis=1,
        )

    df["sig_str_accuracy_decimal"] = df.apply(
        lambda row: safe_divide(row["sig_str_landed"], row["sig_str_attempted"]),
        axis=1,
    )

    df["sig_str_defense_decimal"] = df.apply(
        lambda row: 1.0 - safe_divide(row["opp_sig_str_landed"], row["opp_sig_str_attempted"])
        if safe_divide(row["opp_sig_str_landed"], row["opp_sig_str_attempted"]) is not None
        else None,
        axis=1,
    )

    df["td_accuracy_decimal"] = df.apply(
        lambda row: safe_divide(row["td_landed"], row["td_attempted"]),
        axis=1,
    )

    df["td_defense_decimal"] = df.apply(
        lambda row: 1.0 - safe_divide(row["opp_td_landed"], row["opp_td_attempted"])
        if safe_divide(row["opp_td_landed"], row["opp_td_attempted"]) is not None
        else None,
        axis=1,
    )

    return df


def mean_or_none(values: list[float]) -> float | None:
    clean_values = [value for value in values if value is not None and not pd.isna(value)]

    if not clean_values:
        return None

    return float(np.mean(clean_values))


def sum_column(history: list[pd.Series], column: str) -> int:
    if not history:
        return 0

    return int(sum(row.get(column, 0) for row in history if not pd.isna(row.get(column, 0))))


def mean_column(history: list[pd.Series], column: str) -> float | None:
    if not history:
        return None

    return mean_or_none([row.get(column) for row in history])


def recent_mean_column(history: list[pd.Series], column: str, number_of_fights: int) -> float | None:
    if not history:
        return None

    recent_history = history[-number_of_fights:]

    return mean_column(recent_history, column)


def decisive_history(history: list[pd.Series]) -> list[pd.Series]:
    return [
        row for row in history
        if row.get("is_decisive_result", 0) == 1
    ]


def recent_win_rate(history: list[pd.Series], number_of_fights: int) -> float | None:
    recent_decisive_history = decisive_history(history)[-number_of_fights:]

    if not recent_decisive_history:
        return None

    return safe_divide(
        sum_column(recent_decisive_history, "is_win"),
        len(recent_decisive_history),
    )


def sum_float_column(history: list[pd.Series], column: str) -> float:
    if not history:
        return 0.0

    values = pd.to_numeric(
        pd.Series([row.get(column) for row in history]),
        errors="coerce",
    )

    return float(values.fillna(0.0).sum())


def bayesian_rate(
    successes: float,
    attempts: float,
    prior_rate: float,
    prior_weight: float,
) -> float | None:
    if attempts < 0:
        return None

    return float((successes + prior_rate * prior_weight) / (attempts + prior_weight))


def decayed_mean_column(
    history: list[pd.Series],
    column: str,
    decay: float = 0.72,
) -> float | None:
    if not history:
        return None

    values = []
    weights = []

    for age_index, row in enumerate(reversed(history)):
        value = row.get(column)

        if value is None or pd.isna(value):
            continue

        values.append(float(value))
        weights.append(decay ** age_index)

    if not values:
        return None

    return float(np.average(values, weights=weights))


def decayed_rate(
    history: list[pd.Series],
    success_column: str,
    denominator_column: str = "is_decisive_result",
    decay: float = 0.72,
) -> float | None:
    if not history:
        return None

    successes = 0.0
    denominators = 0.0

    for age_index, row in enumerate(reversed(history)):
        weight = decay ** age_index
        denominator = row.get(denominator_column, 0)

        if denominator is None or pd.isna(denominator) or float(denominator) <= 0:
            continue

        successes += float(row.get(success_column, 0) or 0) * weight
        denominators += float(denominator) * weight

    return safe_divide(successes, denominators)


def std_column(history: list[pd.Series], column: str) -> float | None:
    values = [
        float(row.get(column))
        for row in history
        if row.get(column) is not None and not pd.isna(row.get(column))
    ]

    if len(values) < 2:
        return None

    return float(np.std(values))


def mean_history_value(
    history: list[pd.Series],
    column: str,
) -> float | None:
    return mean_column(history, column)


def add_opponent_adjusted_history_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Scores past fight performance relative to what the opponent usually allows.

    These columns are still leakage-safe: for each completed fight, the baseline
    is built from the opponent's history before that fight.
    """
    df = df.copy()

    adjusted_columns = [
        "opponent_adjusted_striking_per_15",
        "opponent_adjusted_striking_defense_per_15",
        "opponent_adjusted_td_per_15",
        "opponent_adjusted_td_defense_per_15",
        "opponent_adjusted_control_per_15",
        "opponent_adjusted_control_defense_per_15",
    ]

    for column in adjusted_columns:
        df[column] = np.nan

    fighter_histories: dict[str, list[pd.Series]] = defaultdict(list)

    grouped_fights = df.groupby("fight_url", sort=False)

    for _, fight_rows in grouped_fights:
        updates: dict[int, dict[str, float | None]] = {}

        for row_index, row in fight_rows.iterrows():
            opponent = clean_text(row.get("opponent", ""))
            opponent_history = fighter_histories[opponent]

            opponent_sig_absorbed = mean_history_value(
                opponent_history,
                "sig_str_absorbed_per_15",
            )
            opponent_sig_landed = mean_history_value(
                opponent_history,
                "sig_str_landed_per_15",
            )
            opponent_td_absorbed = mean_history_value(
                opponent_history,
                "td_absorbed_per_15",
            )
            opponent_td_landed = mean_history_value(
                opponent_history,
                "td_landed_per_15",
            )
            opponent_ctrl_absorbed = mean_history_value(
                opponent_history,
                "ctrl_absorbed_seconds_per_15",
            )
            opponent_ctrl_for = mean_history_value(
                opponent_history,
                "ctrl_seconds_per_15",
            )

            sig_landed = row.get("sig_str_landed_per_15")
            sig_absorbed = row.get("sig_str_absorbed_per_15")
            td_landed = row.get("td_landed_per_15")
            td_absorbed = row.get("td_absorbed_per_15")
            ctrl_for = row.get("ctrl_seconds_per_15")
            ctrl_absorbed = row.get("ctrl_absorbed_seconds_per_15")

            updates[row_index] = {
                "opponent_adjusted_striking_per_15": None
                if opponent_sig_absorbed is None or pd.isna(sig_landed)
                else float(sig_landed) - opponent_sig_absorbed,
                "opponent_adjusted_striking_defense_per_15": None
                if opponent_sig_landed is None or pd.isna(sig_absorbed)
                else opponent_sig_landed - float(sig_absorbed),
                "opponent_adjusted_td_per_15": None
                if opponent_td_absorbed is None or pd.isna(td_landed)
                else float(td_landed) - opponent_td_absorbed,
                "opponent_adjusted_td_defense_per_15": None
                if opponent_td_landed is None or pd.isna(td_absorbed)
                else opponent_td_landed - float(td_absorbed),
                "opponent_adjusted_control_per_15": None
                if opponent_ctrl_absorbed is None or pd.isna(ctrl_for)
                else float(ctrl_for) - opponent_ctrl_absorbed,
                "opponent_adjusted_control_defense_per_15": None
                if opponent_ctrl_for is None or pd.isna(ctrl_absorbed)
                else opponent_ctrl_for - float(ctrl_absorbed),
            }

        for row_index, values in updates.items():
            for column, value in values.items():
                df.at[row_index, column] = np.nan if value is None else value

        for _, row in fight_rows.iterrows():
            fighter = clean_text(row["fighter"])
            fighter_histories[fighter].append(df.loc[row.name])

    return df


def build_snapshot_from_history(row: pd.Series, history: list[pd.Series]) -> FighterSnapshot:
    prior_fights = len(history)

    prior_wins = sum_column(history, "is_win")
    prior_losses = sum_column(history, "is_loss")
    prior_unscored_results = sum_column(history, "is_unscored_result")
    prior_decisive_results = prior_wins + prior_losses

    prior_win_rate = safe_divide(prior_wins, prior_decisive_results)

    prior_finish_wins = sum_column(history, "finish_win")
    prior_finish_losses = sum_column(history, "finish_loss")

    prior_finish_win_rate = safe_divide(prior_finish_wins, prior_decisive_results)
    prior_finish_loss_rate = safe_divide(prior_finish_losses, prior_decisive_results)

    days_since_last_fight = None

    if history:
        last_fight_date = history[-1].get("event_date_parsed")
        current_fight_date = row.get("event_date_parsed")

        if pd.notna(last_fight_date) and pd.notna(current_fight_date):
            days_since_last_fight = float((current_fight_date - last_fight_date).days)

    sample_reliability = safe_divide(prior_fights, prior_fights + 5)

    ko_tko_wins = sum_column(history, "ko_tko_win")
    ko_tko_losses = sum_column(history, "ko_tko_loss")
    submission_wins = sum_column(history, "submission_win")
    submission_losses = sum_column(history, "submission_loss")
    decision_wins = sum_column(history, "decision_win")

    bayes_win_rate = bayesian_rate(prior_wins, prior_decisive_results, 0.50, 4.0)
    bayes_finish_win_rate = bayesian_rate(
        prior_finish_wins,
        prior_decisive_results,
        0.32,
        4.0,
    )
    bayes_finish_loss_rate = bayesian_rate(
        prior_finish_losses,
        prior_decisive_results,
        0.32,
        4.0,
    )
    bayes_ko_tko_win_rate = bayesian_rate(
        ko_tko_wins,
        prior_decisive_results,
        0.18,
        4.0,
    )
    bayes_ko_tko_loss_rate = bayesian_rate(
        ko_tko_losses,
        prior_decisive_results,
        0.18,
        4.0,
    )
    bayes_submission_win_rate = bayesian_rate(
        submission_wins,
        prior_decisive_results,
        0.12,
        4.0,
    )
    bayes_submission_loss_rate = bayesian_rate(
        submission_losses,
        prior_decisive_results,
        0.12,
        4.0,
    )
    bayes_decision_win_rate = bayesian_rate(
        decision_wins,
        prior_decisive_results,
        0.28,
        4.0,
    )

    sig_str_landed = sum_float_column(history, "sig_str_landed")
    sig_str_attempted = sum_float_column(history, "sig_str_attempted")
    opp_sig_str_landed = sum_float_column(history, "opp_sig_str_landed")
    opp_sig_str_attempted = sum_float_column(history, "opp_sig_str_attempted")
    td_landed = sum_float_column(history, "td_landed")
    td_attempted = sum_float_column(history, "td_attempted")
    opp_td_landed = sum_float_column(history, "opp_td_landed")
    opp_td_attempted = sum_float_column(history, "opp_td_attempted")

    bayes_sig_str_accuracy = bayesian_rate(
        sig_str_landed,
        sig_str_attempted,
        0.46,
        300.0,
    )
    bayes_sig_str_defense = 1.0 - bayesian_rate(
        opp_sig_str_landed,
        opp_sig_str_attempted,
        0.46,
        300.0,
    )
    bayes_td_accuracy = bayesian_rate(td_landed, td_attempted, 0.36, 20.0)
    bayes_td_defense = 1.0 - bayesian_rate(opp_td_landed, opp_td_attempted, 0.36, 20.0)

    avg_td_attempted_per_15 = mean_column(history, "td_attempted_per_15")
    avg_td_landed_per_15 = mean_column(history, "td_landed_per_15")
    avg_ctrl_seconds_per_15 = mean_column(history, "ctrl_seconds_per_15")
    avg_ctrl_absorbed_seconds_per_15 = mean_column(
        history,
        "ctrl_absorbed_seconds_per_15",
    )
    avg_sig_str_attempted_per_15 = mean_column(history, "sig_str_attempted_per_15")
    avg_sig_str_landed_per_15 = mean_column(history, "sig_str_landed_per_15")
    avg_sig_str_absorbed_per_15 = mean_column(history, "sig_str_absorbed_per_15")
    avg_kd_for = mean_column(history, "kd")
    avg_kd_against = mean_column(history, "kd_against")
    avg_sub_att_per_15 = mean_column(history, "sub_att_per_15")
    avg_fight_duration_seconds = mean_column(history, "fight_duration_seconds")

    path_ko_tko_score = (
        (bayes_ko_tko_win_rate or 0)
        + (avg_kd_for or 0) * 0.12
        + (avg_sig_str_landed_per_15 or 0) / 120.0
    )
    path_submission_score = (
        (bayes_submission_win_rate or 0)
        + (avg_sub_att_per_15 or 0) / 5.0
        + (avg_ctrl_seconds_per_15 or 0) / 900.0
    )
    path_decision_score = (
        (bayes_decision_win_rate or 0)
        + ((avg_fight_duration_seconds or 0) / 900.0) * 0.25
        + (bayes_win_rate or 0) * 0.25
    )
    vulnerability_ko_tko_score = (
        (bayes_ko_tko_loss_rate or 0)
        + (avg_kd_against or 0) * 0.12
        + (avg_sig_str_absorbed_per_15 or 0) / 130.0
    )
    vulnerability_submission_score = (
        (bayes_submission_loss_rate or 0)
        + (avg_ctrl_absorbed_seconds_per_15 or 0) / 900.0
        + (mean_column(history, "td_absorbed_per_15") or 0) / 8.0
    )
    durability_risk_score = (
        vulnerability_ko_tko_score
        + vulnerability_submission_score * 0.4
        + (bayes_finish_loss_rate or 0)
    )
    style_pressure_score = (
        (avg_sig_str_attempted_per_15 or 0) / 100.0
        + (avg_sig_str_landed_per_15 or 0) / 75.0
    )
    style_wrestling_score = (
        (avg_td_attempted_per_15 or 0) / 8.0
        + (avg_td_landed_per_15 or 0) / 5.0
        + (avg_ctrl_seconds_per_15 or 0) / 900.0
    )
    style_control_score = (
        (avg_ctrl_seconds_per_15 or 0) / 900.0
        + (bayes_td_defense or 0) * 0.2
    )

    return FighterSnapshot(
        fight_url=clean_text(row["fight_url"]),
        event_name=clean_text(row["event_name"]),
        event_date=clean_text(row["event_date"]),
        fighter=clean_text(row["fighter"]),
        opponent=clean_text(row["opponent"]),
        weight_class=clean_text(row["weight_class"]),
        method=clean_text(row["method"]),

        target_is_winner=int(row.get("is_win", row.get("is_winner", 0))),

        prior_fights=prior_fights,
        prior_wins=prior_wins,
        prior_losses=prior_losses,
        prior_decisive_results=prior_decisive_results,
        prior_unscored_results=prior_unscored_results,
        prior_win_rate=prior_win_rate,

        days_since_last_fight=days_since_last_fight,

        prior_finish_wins=prior_finish_wins,
        prior_finish_losses=prior_finish_losses,
        prior_finish_win_rate=prior_finish_win_rate,
        prior_finish_loss_rate=prior_finish_loss_rate,

        avg_fight_duration_seconds=avg_fight_duration_seconds,

        avg_kd_for=avg_kd_for,
        avg_kd_against=avg_kd_against,

        avg_sig_str_landed_per_15=avg_sig_str_landed_per_15,
        avg_sig_str_attempted_per_15=avg_sig_str_attempted_per_15,
        avg_sig_str_absorbed_per_15=avg_sig_str_absorbed_per_15,
        avg_sig_str_defense=mean_column(history, "sig_str_defense_decimal"),
        avg_sig_str_accuracy=mean_column(history, "sig_str_accuracy_decimal"),
        avg_sig_str_differential_per_15=mean_column(history, "sig_str_differential_per_15"),

        avg_total_str_landed_per_15=mean_column(history, "total_str_landed_per_15"),
        avg_total_str_absorbed_per_15=mean_column(history, "total_str_absorbed_per_15"),

        avg_td_landed_per_15=avg_td_landed_per_15,
        avg_td_attempted_per_15=avg_td_attempted_per_15,
        avg_td_absorbed_per_15=mean_column(history, "td_absorbed_per_15"),
        avg_td_accuracy=mean_column(history, "td_accuracy_decimal"),
        avg_td_defense=mean_column(history, "td_defense_decimal"),

        avg_sub_att_per_15=mean_column(history, "sub_att_per_15"),
        avg_ctrl_seconds_per_15=avg_ctrl_seconds_per_15,
        avg_ctrl_absorbed_seconds_per_15=avg_ctrl_absorbed_seconds_per_15,

        avg_head_landed_per_15=mean_column(history, "head_landed_per_15"),
        avg_body_landed_per_15=mean_column(history, "body_landed_per_15"),
        avg_leg_landed_per_15=mean_column(history, "leg_landed_per_15"),

        avg_distance_landed_per_15=mean_column(history, "distance_landed_per_15"),
        avg_clinch_landed_per_15=mean_column(history, "clinch_landed_per_15"),
        avg_ground_landed_per_15=mean_column(history, "ground_landed_per_15"),

        recent_3_win_rate=recent_win_rate(history, 3),
        recent_5_win_rate=recent_win_rate(history, 5),

        recent_3_sig_str_differential_per_15=recent_mean_column(
            history,
            "sig_str_differential_per_15",
            3,
        ),
        recent_5_sig_str_differential_per_15=recent_mean_column(
            history,
            "sig_str_differential_per_15",
            5,
        ),

        recent_3_td_differential_per_15=recent_mean_column(
            history,
            "td_differential_per_15",
            3,
        ),
        recent_5_td_differential_per_15=recent_mean_column(
            history,
            "td_differential_per_15",
            5,
        ),

        sample_reliability=sample_reliability,

        bayes_win_rate=bayes_win_rate,
        bayes_finish_win_rate=bayes_finish_win_rate,
        bayes_finish_loss_rate=bayes_finish_loss_rate,
        bayes_ko_tko_win_rate=bayes_ko_tko_win_rate,
        bayes_ko_tko_loss_rate=bayes_ko_tko_loss_rate,
        bayes_submission_win_rate=bayes_submission_win_rate,
        bayes_submission_loss_rate=bayes_submission_loss_rate,
        bayes_decision_win_rate=bayes_decision_win_rate,
        bayes_sig_str_accuracy=bayes_sig_str_accuracy,
        bayes_sig_str_defense=bayes_sig_str_defense,
        bayes_td_accuracy=bayes_td_accuracy,
        bayes_td_defense=bayes_td_defense,

        decayed_win_rate=decayed_rate(history, "is_win"),
        decayed_finish_win_rate=decayed_rate(history, "finish_win"),
        decayed_finish_loss_rate=decayed_rate(history, "finish_loss"),
        decayed_sig_str_differential_per_15=decayed_mean_column(
            history,
            "sig_str_differential_per_15",
        ),
        decayed_td_differential_per_15=decayed_mean_column(
            history,
            "td_differential_per_15",
        ),
        decayed_ctrl_differential_per_15=decayed_mean_column(
            history,
            "ctrl_differential_per_15",
        ),

        avg_opponent_adjusted_striking_per_15=mean_column(
            history,
            "opponent_adjusted_striking_per_15",
        ),
        avg_opponent_adjusted_striking_defense_per_15=mean_column(
            history,
            "opponent_adjusted_striking_defense_per_15",
        ),
        avg_opponent_adjusted_td_per_15=mean_column(
            history,
            "opponent_adjusted_td_per_15",
        ),
        avg_opponent_adjusted_td_defense_per_15=mean_column(
            history,
            "opponent_adjusted_td_defense_per_15",
        ),
        avg_opponent_adjusted_control_per_15=mean_column(
            history,
            "opponent_adjusted_control_per_15",
        ),
        avg_opponent_adjusted_control_defense_per_15=mean_column(
            history,
            "opponent_adjusted_control_defense_per_15",
        ),

        recent_3_opponent_adjusted_striking_per_15=recent_mean_column(
            history,
            "opponent_adjusted_striking_per_15",
            3,
        ),
        recent_3_opponent_adjusted_td_per_15=recent_mean_column(
            history,
            "opponent_adjusted_td_per_15",
            3,
        ),

        style_pressure_score=style_pressure_score,
        style_wrestling_score=style_wrestling_score,
        style_control_score=style_control_score,
        path_ko_tko_score=path_ko_tko_score,
        path_submission_score=path_submission_score,
        path_decision_score=path_decision_score,
        vulnerability_ko_tko_score=vulnerability_ko_tko_score,
        vulnerability_submission_score=vulnerability_submission_score,
        durability_risk_score=durability_risk_score,
        volatility_finish_or_finished_rate=bayesian_rate(
            sum_column(history, "finish_or_finished"),
            prior_decisive_results,
            0.62,
            4.0,
        ),
        volatility_performance_variance=std_column(
            history,
            "sig_str_differential_per_15",
        ),
    )


def build_fighter_snapshots(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df = add_opponent_stats(df)
    df = add_engineered_fight_columns(df)

    df = df.sort_values(
        by=["event_date_parsed", "event_name", "fight_url", "fighter"],
        ascending=[True, True, True, True],
    ).reset_index(drop=True)
    df = add_opponent_adjusted_history_columns(df)

    fighter_histories: dict[str, list[pd.Series]] = defaultdict(list)
    snapshots: list[FighterSnapshot] = []

    grouped_fights = df.groupby("fight_url", sort=False)

    total_fights = grouped_fights.ngroups

    for fight_number, (_, fight_rows) in enumerate(grouped_fights, start=1):
        if fight_number % 500 == 0:
            print(f"Processed {fight_number}/{total_fights} fights...")

        # Build both fighter snapshots BEFORE adding this fight to history.
        for _, row in fight_rows.iterrows():
            fighter = clean_text(row["fighter"])
            history = fighter_histories[fighter]

            snapshot = build_snapshot_from_history(row, history)
            snapshots.append(snapshot)

        # Now that snapshots are saved, this fight can become history.
        for _, row in fight_rows.iterrows():
            fighter = clean_text(row["fighter"])
            fighter_histories[fighter].append(row)

    return pd.DataFrame([asdict(snapshot) for snapshot in snapshots])


def load_fight_stats() -> pd.DataFrame:
    if not FIGHT_STATS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {FIGHT_STATS_CSV}. Run the fight detail scraper first."
        )

    return pd.read_csv(FIGHT_STATS_CSV)


def save_fighter_snapshots(df: pd.DataFrame) -> None:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(FIGHTER_SNAPSHOTS_CSV, index=False)


def main() -> None:
    print("Loading fight stats...")
    fight_stats_df = load_fight_stats()

    print(f"Loaded {len(fight_stats_df)} fighter-fight rows.")

    print("Building fighter history snapshots...")
    snapshots_df = build_fighter_snapshots(fight_stats_df)

    save_fighter_snapshots(snapshots_df)

    print()
    print(f"Saved {len(snapshots_df)} fighter snapshots.")
    print(f"Output file: {FIGHTER_SNAPSHOTS_CSV}")

    print()
    print("Preview:")
    preview_columns = [
        "event_date",
        "fighter",
        "opponent",
        "target_is_winner",
        "prior_fights",
        "prior_wins",
        "prior_losses",
        "prior_decisive_results",
        "prior_unscored_results",
        "prior_win_rate",
        "days_since_last_fight",
        "avg_sig_str_differential_per_15",
        "avg_td_landed_per_15",
    ]
    print(snapshots_df[preview_columns].head(20))


if __name__ == "__main__":
    main()
