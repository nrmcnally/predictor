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

    df["is_finish"] = df["method"].apply(is_finish_method)
    df["finish_win"] = ((df["is_winner"] == 1) & df["is_finish"]).astype(int)
    df["finish_loss"] = ((df["is_winner"] == 0) & df["is_finish"]).astype(int)

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


def build_snapshot_from_history(row: pd.Series, history: list[pd.Series]) -> FighterSnapshot:
    prior_fights = len(history)

    prior_wins = sum_column(history, "is_winner")
    prior_losses = prior_fights - prior_wins

    prior_win_rate = safe_divide(prior_wins, prior_fights)

    prior_finish_wins = sum_column(history, "finish_win")
    prior_finish_losses = sum_column(history, "finish_loss")

    prior_finish_win_rate = safe_divide(prior_finish_wins, prior_fights)
    prior_finish_loss_rate = safe_divide(prior_finish_losses, prior_fights)

    days_since_last_fight = None

    if history:
        last_fight_date = history[-1].get("event_date_parsed")
        current_fight_date = row.get("event_date_parsed")

        if pd.notna(last_fight_date) and pd.notna(current_fight_date):
            days_since_last_fight = float((current_fight_date - last_fight_date).days)

    return FighterSnapshot(
        fight_url=clean_text(row["fight_url"]),
        event_name=clean_text(row["event_name"]),
        event_date=clean_text(row["event_date"]),
        fighter=clean_text(row["fighter"]),
        opponent=clean_text(row["opponent"]),
        weight_class=clean_text(row["weight_class"]),
        method=clean_text(row["method"]),

        target_is_winner=int(row["is_winner"]),

        prior_fights=prior_fights,
        prior_wins=prior_wins,
        prior_losses=prior_losses,
        prior_win_rate=prior_win_rate,

        days_since_last_fight=days_since_last_fight,

        prior_finish_wins=prior_finish_wins,
        prior_finish_losses=prior_finish_losses,
        prior_finish_win_rate=prior_finish_win_rate,
        prior_finish_loss_rate=prior_finish_loss_rate,

        avg_fight_duration_seconds=mean_column(history, "fight_duration_seconds"),

        avg_kd_for=mean_column(history, "kd"),
        avg_kd_against=mean_column(history, "kd_against"),

        avg_sig_str_landed_per_15=mean_column(history, "sig_str_landed_per_15"),
        avg_sig_str_attempted_per_15=mean_column(history, "sig_str_attempted_per_15"),
        avg_sig_str_absorbed_per_15=mean_column(history, "sig_str_absorbed_per_15"),
        avg_sig_str_defense=mean_column(history, "sig_str_defense_decimal"),
        avg_sig_str_accuracy=mean_column(history, "sig_str_accuracy_decimal"),
        avg_sig_str_differential_per_15=mean_column(history, "sig_str_differential_per_15"),

        avg_total_str_landed_per_15=mean_column(history, "total_str_landed_per_15"),
        avg_total_str_absorbed_per_15=mean_column(history, "total_str_absorbed_per_15"),

        avg_td_landed_per_15=mean_column(history, "td_landed_per_15"),
        avg_td_attempted_per_15=mean_column(history, "td_attempted_per_15"),
        avg_td_absorbed_per_15=mean_column(history, "td_absorbed_per_15"),
        avg_td_accuracy=mean_column(history, "td_accuracy_decimal"),
        avg_td_defense=mean_column(history, "td_defense_decimal"),

        avg_sub_att_per_15=mean_column(history, "sub_att_per_15"),
        avg_ctrl_seconds_per_15=mean_column(history, "ctrl_seconds_per_15"),
        avg_ctrl_absorbed_seconds_per_15=mean_column(history, "ctrl_absorbed_seconds_per_15"),

        avg_head_landed_per_15=mean_column(history, "head_landed_per_15"),
        avg_body_landed_per_15=mean_column(history, "body_landed_per_15"),
        avg_leg_landed_per_15=mean_column(history, "leg_landed_per_15"),

        avg_distance_landed_per_15=mean_column(history, "distance_landed_per_15"),
        avg_clinch_landed_per_15=mean_column(history, "clinch_landed_per_15"),
        avg_ground_landed_per_15=mean_column(history, "ground_landed_per_15"),

        recent_3_win_rate=recent_mean_column(history, "is_winner", 3),
        recent_5_win_rate=recent_mean_column(history, "is_winner", 5),

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
    )


def build_fighter_snapshots(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df = add_opponent_stats(df)
    df = add_engineered_fight_columns(df)

    df = df.sort_values(
        by=["event_date_parsed", "event_name", "fight_url", "fighter"],
        ascending=[True, True, True, True],
    ).reset_index(drop=True)

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
        "prior_win_rate",
        "days_since_last_fight",
        "avg_sig_str_differential_per_15",
        "avg_td_landed_per_15",
    ]
    print(snapshots_df[preview_columns].head(20))


if __name__ == "__main__":
    main()