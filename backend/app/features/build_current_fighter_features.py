from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from app.features.build_fighter_snapshots import (
    add_opponent_adjusted_history_columns,
    add_engineered_fight_columns,
    add_opponent_stats,
    build_snapshot_from_history,
    clean_text,
)
from app.features.add_elo_features import (
    BASE_ELO,
    K_BASE,
    expected_score,
    method_multiplier,
)
from app.features.strength_of_schedule import (
    SOS_FEATURE_COLUMNS,
    compute_sos_features,
)
from app.features.cardio_features import (
    CARDIO_SNAPSHOT_COLUMNS,
    build_current_cardio_lookup,
)
from app.features.add_cardio_features import load_round_stats
from app.features.add_weight_size_features import (
    add_weight_size_features_to_current_features,
    load_fighter_profiles,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

FIGHT_STATS_CSV = RAW_DATA_DIR / "fight_stats.csv"
FIGHTER_SNAPSHOTS_CSV = PROCESSED_DATA_DIR / "fighter_snapshots.csv"
CURRENT_FIGHTER_FEATURES_CSV = PROCESSED_DATA_DIR / "current_fighter_features.csv"


PHYSICAL_COLUMNS = [
    "height_inches",
    "reach_inches",
    "reach_minus_height_inches",
    "is_orthodox",
    "is_southpaw",
    "is_switch_stance",
    "is_open_stance",
    "is_sideways_stance",
    "is_stance_unknown",
]


def load_fight_stats() -> pd.DataFrame:
    if not FIGHT_STATS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {FIGHT_STATS_CSV}. Run scrape_fight_details.py first."
        )

    return pd.read_csv(FIGHT_STATS_CSV)


def load_fighter_snapshots() -> pd.DataFrame:
    if not FIGHTER_SNAPSHOTS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {FIGHTER_SNAPSHOTS_CSV}. Run build_fighter_snapshots.py first."
        )

    return pd.read_csv(FIGHTER_SNAPSHOTS_CSV)


def prepare_fight_history(fight_stats_df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes raw fight_stats.csv and adds the same engineered columns
    used when we built historical fighter snapshots.
    """
    df = fight_stats_df.copy()

    df = add_opponent_stats(df)
    df = add_engineered_fight_columns(df)

    df = df.sort_values(
        by=["event_date_parsed", "event_name", "fight_url", "fighter"],
        ascending=[True, True, True, True],
    ).reset_index(drop=True)
    df = add_opponent_adjusted_history_columns(df)

    return df


def build_final_elo_state(df: pd.DataFrame) -> tuple[
    dict[str, float],
    dict[str, list[float]],
    dict[str, list[float]],
    dict[str, list[int]],
]:
    """
    Replays the full fight history and returns each fighter's current Elo state,
    plus the strength-of-schedule history (pre-fight Elo of every opponent faced
    and whether the fighter won).

    This is similar to add_elo_features.py, but instead of saving pre-fight Elo
    for every fight, we only care about the final/current state.
    """
    ratings: dict[str, float] = defaultdict(lambda: BASE_ELO)
    rating_history: dict[str, list[float]] = defaultdict(list)
    opponent_elo_history: dict[str, list[float]] = defaultdict(list)
    opponent_result_history: dict[str, list[int]] = defaultdict(list)

    grouped = df.groupby("fight_url", sort=False)

    total_fights = grouped.ngroups

    for fight_number, (_, fight_rows) in enumerate(grouped, start=1):
        if fight_number % 500 == 0:
            print(f"Processed current Elo for {fight_number}/{total_fights} fights...")

        if len(fight_rows) != 2:
            continue

        row_a = fight_rows.iloc[0]
        row_b = fight_rows.iloc[1]

        fighter_a = clean_text(row_a["fighter"])
        fighter_b = clean_text(row_b["fighter"])

        rating_a_before = ratings[fighter_a]
        rating_b_before = ratings[fighter_b]

        actual_a = float(row_a["is_winner"])
        actual_b = float(row_b["is_winner"])

        opponent_elo_history[fighter_a].append(rating_b_before)
        opponent_result_history[fighter_a].append(int(actual_a == 1))
        opponent_elo_history[fighter_b].append(rating_a_before)
        opponent_result_history[fighter_b].append(int(actual_b == 1))

        if actual_a == actual_b:
            rating_history[fighter_a].append(rating_a_before)
            rating_history[fighter_b].append(rating_b_before)
            continue

        expected_a = expected_score(rating_a_before, rating_b_before)
        expected_b = expected_score(rating_b_before, rating_a_before)

        multiplier = method_multiplier(row_a.get("method", ""))

        k_value = K_BASE * multiplier

        rating_a_after = rating_a_before + k_value * (actual_a - expected_a)
        rating_b_after = rating_b_before + k_value * (actual_b - expected_b)

        ratings[fighter_a] = rating_a_after
        ratings[fighter_b] = rating_b_after

        rating_history[fighter_a].append(rating_a_after)
        rating_history[fighter_b].append(rating_b_after)

    return ratings, rating_history, opponent_elo_history, opponent_result_history


def build_physical_lookup(snapshots_df: pd.DataFrame) -> pd.DataFrame:
    """
    Pulls the latest physical-profile columns for each fighter.

    These columns were already added to fighter_snapshots.csv in the previous step.
    """
    available_physical_columns = [
        column for column in PHYSICAL_COLUMNS if column in snapshots_df.columns
    ]

    if not available_physical_columns:
        print("No physical columns found in fighter_snapshots.csv.")
        return pd.DataFrame(columns=["fighter"])

    snapshots_df = snapshots_df.copy()
    snapshots_df["event_date_parsed"] = pd.to_datetime(
        snapshots_df["event_date"],
        errors="coerce",
    )

    latest_rows = (
        snapshots_df
        .sort_values(["fighter", "event_date_parsed"])
        .groupby("fighter", as_index=False)
        .tail(1)
    )

    return latest_rows[["fighter"] + available_physical_columns].copy()


def build_current_features(
    engineered_df: pd.DataFrame,
    snapshots_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Builds one current feature row per fighter.

    The current row includes:
        - full historical averages
        - recent form
        - current Elo
        - physical features
    """
    current_as_of_date = engineered_df["event_date_parsed"].max()

    print(f"Building current fighter features as of: {current_as_of_date.date()}")

    fighter_histories: dict[str, list[pd.Series]] = defaultdict(list)

    grouped = engineered_df.groupby("fight_url", sort=False)

    for _, fight_rows in grouped:
        for _, row in fight_rows.iterrows():
            fighter = clean_text(row["fighter"])
            fighter_histories[fighter].append(row)

    ratings, rating_history, opponent_elo_history, opponent_result_history = (
        build_final_elo_state(engineered_df)
    )

    current_rows: list[dict[str, Any]] = []

    for fighter, history in fighter_histories.items():
        if not history:
            continue

        latest_row = history[-1].copy()

        # This dummy/current row is only used so build_snapshot_from_history()
        # can compute "days since last fight" as of the latest completed event.
        latest_row["fight_url"] = "__current__"
        latest_row["event_name"] = "Current Fighter Features"
        latest_row["event_date"] = current_as_of_date.strftime("%B %d, %Y")
        latest_row["event_date_parsed"] = current_as_of_date
        latest_row["opponent"] = ""
        latest_row["method"] = ""
        latest_row["is_winner"] = 0
        latest_row["is_win"] = 0
        latest_row["is_loss"] = 0
        latest_row["is_decisive_result"] = 0
        latest_row["is_unscored_result"] = 0

        snapshot = build_snapshot_from_history(latest_row, history)
        row_dict = asdict(snapshot)

        current_elo = ratings[fighter]
        elo_history = rating_history[fighter]

        row_dict["prior_elo"] = current_elo
        row_dict["prior_peak_elo"] = max(elo_history) if elo_history else BASE_ELO
        row_dict["prior_lowest_elo"] = min(elo_history) if elo_history else BASE_ELO

        if len(elo_history) >= 3:
            row_dict["prior_elo_change_last_3"] = current_elo - elo_history[-3]
        else:
            row_dict["prior_elo_change_last_3"] = None

        row_dict["prior_elo_fights"] = len(elo_history)

        sos_features = compute_sos_features(
            opponent_elo_history[fighter],
            opponent_result_history[fighter],
        )
        for column in SOS_FEATURE_COLUMNS:
            row_dict[column] = sos_features.get(column)

        current_rows.append(row_dict)

    current_df = pd.DataFrame(current_rows)

    physical_lookup_df = build_physical_lookup(snapshots_df)

    if not physical_lookup_df.empty:
        current_df = current_df.merge(
            physical_lookup_df,
            on="fighter",
            how="left",
        )

    profiles_df = load_fighter_profiles()

    current_df = add_weight_size_features_to_current_features(
        profiles_df=profiles_df,
        current_features_df=current_df,
        fight_stats_df=engineered_df,
    )

    cardio_lookup = build_current_cardio_lookup(load_round_stats())

    if not cardio_lookup.empty:
        current_df = current_df.merge(cardio_lookup, on="fighter", how="left")

    # Keep a stable schema even before per-round data has been backfilled.
    for column in CARDIO_SNAPSHOT_COLUMNS:
        if column not in current_df.columns:
            current_df[column] = pd.NA

    return current_df


def save_current_features(df: pd.DataFrame) -> None:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CURRENT_FIGHTER_FEATURES_CSV, index=False)


def main() -> None:
    print("Loading fight stats...")
    fight_stats_df = load_fight_stats()
    print(f"Loaded {len(fight_stats_df)} fighter-fight rows.")

    print("Loading fighter snapshots...")
    snapshots_df = load_fighter_snapshots()
    print(f"Loaded {len(snapshots_df)} fighter snapshots.")

    print("Preparing fight history...")
    engineered_df = prepare_fight_history(fight_stats_df)

    print("Building current fighter features...")
    current_features_df = build_current_features(
        engineered_df=engineered_df,
        snapshots_df=snapshots_df,
    )

    save_current_features(current_features_df)

    print()
    print(f"Saved {len(current_features_df)} current fighter feature rows.")
    print(f"Output file: {CURRENT_FIGHTER_FEATURES_CSV}")

    print()
    print("Preview:")
    preview_columns = [
        "fighter",
        "prior_fights",
        "prior_wins",
        "prior_losses",
        "prior_decisive_results",
        "prior_unscored_results",
        "prior_win_rate",
        "days_since_last_fight",
        "prior_elo",
        "height_inches",
        "reach_inches",
        "listed_weight_lbs",
        "listed_weight_minus_class_lbs",
        "prior_common_weight_class_lbs",
        "current_vs_common_weight_class_lbs_delta",
        "is_southpaw",
        "is_switch_stance",
    ]

    existing_preview_columns = [
        column for column in preview_columns if column in current_features_df.columns
    ]

    print(current_features_df[existing_preview_columns].tail(30))


if __name__ == "__main__":
    main()
