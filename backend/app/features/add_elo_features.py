from __future__ import annotations

import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from app.features.strength_of_schedule import (
    SOS_FEATURE_COLUMNS,
    compute_sos_features,
    empty_sos_features,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

FIGHTER_SNAPSHOTS_CSV = PROCESSED_DATA_DIR / "fighter_snapshots.csv"
BACKUP_SNAPSHOTS_CSV = PROCESSED_DATA_DIR / "fighter_snapshots_before_elo_backup.csv"


BASE_ELO = 1500.0
K_BASE = 32.0


def clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""

    return " ".join(str(value).split())


def expected_score(rating_a: float, rating_b: float) -> float:
    """
    Standard Elo expected score.

    If both fighters are 1500, expected score is 0.5.
    If fighter A is much higher rated, expected score is above 0.5.
    """
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def method_multiplier(method: Any) -> float:
    """
    Adjusts Elo movement based on how decisive the result was.

    Conservative version:
        Finish: slightly more movement
        Split decision: slightly less movement
        Majority decision: slightly less movement
        Normal decision: normal movement
    """
    method_text = clean_text(method).lower()

    if "ko/tko" in method_text or "submission" in method_text:
        return 1.25

    if "split" in method_text or "s-dec" in method_text:
        return 0.85

    if "majority" in method_text or "m-dec" in method_text:
        return 0.90

    return 1.00


def load_snapshots() -> pd.DataFrame:
    if not FIGHTER_SNAPSHOTS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {FIGHTER_SNAPSHOTS_CSV}. "
            "Run build_fighter_snapshots.py first."
        )

    return pd.read_csv(FIGHTER_SNAPSHOTS_CSV)


def calculate_prior_elo_change_last_3(
    current_rating: float,
    history: list[float],
) -> float | None:
    """
    Measures recent Elo momentum.

    If the fighter has at least 3 prior Elo history points:
        current pre-fight Elo - Elo from 3 fights ago

    If not enough history:
        None
    """
    if len(history) < 3:
        return None

    return current_rating - history[-3]


def add_elo_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # If these columns already exist from a previous run, remove them first.
    # This makes the script safe to rerun.
    elo_columns = [
        "prior_elo",
        "prior_peak_elo",
        "prior_lowest_elo",
        "prior_elo_change_last_3",
        "prior_elo_fights",
        *SOS_FEATURE_COLUMNS,
    ]

    existing_elo_columns = [column for column in elo_columns if column in df.columns]

    if existing_elo_columns:
        print(f"Removing existing Elo columns before recalculating: {existing_elo_columns}")
        df = df.drop(columns=existing_elo_columns)

    df["event_date_parsed"] = pd.to_datetime(df["event_date"], errors="coerce")

    df = df.sort_values(
        by=["event_date_parsed", "event_name", "fight_url", "fighter"],
        ascending=[True, True, True, True],
    ).reset_index(drop=True)

    ratings: dict[str, float] = defaultdict(lambda: BASE_ELO)
    rating_history: dict[str, list[float]] = defaultdict(list)

    # Strength-of-schedule tracking: the pre-fight Elo of each opponent a fighter
    # has faced so far, plus whether the fighter won, in chronological order.
    opponent_elo_history: dict[str, list[float]] = defaultdict(list)
    opponent_result_history: dict[str, list[int]] = defaultdict(list)

    prior_elo_by_index: dict[int, float] = {}
    prior_peak_elo_by_index: dict[int, float] = {}
    prior_lowest_elo_by_index: dict[int, float] = {}
    prior_elo_change_last_3_by_index: dict[int, float | None] = {}
    prior_elo_fights_by_index: dict[int, int] = {}
    sos_by_index: dict[int, dict[str, Any]] = {}

    grouped = df.groupby("fight_url", sort=False)

    total_fights = grouped.ngroups

    for fight_number, (_, fight_rows) in enumerate(grouped, start=1):
        if fight_number % 500 == 0:
            print(f"Processed Elo for {fight_number}/{total_fights} fights...")

        if len(fight_rows) != 2:
            # Defensive fallback. This should not happen in our cleaned data.
            for row_index, row in fight_rows.iterrows():
                fighter = clean_text(row["fighter"])
                current_rating = ratings[fighter]
                history = rating_history[fighter]

                prior_elo_by_index[row_index] = current_rating
                prior_peak_elo_by_index[row_index] = max(history) if history else BASE_ELO
                prior_lowest_elo_by_index[row_index] = min(history) if history else BASE_ELO
                prior_elo_change_last_3_by_index[row_index] = calculate_prior_elo_change_last_3(
                    current_rating=current_rating,
                    history=history,
                )
                prior_elo_fights_by_index[row_index] = len(history)
                sos_by_index[row_index] = empty_sos_features()

            continue

        row_a = fight_rows.iloc[0]
        row_b = fight_rows.iloc[1]

        index_a = fight_rows.index[0]
        index_b = fight_rows.index[1]

        fighter_a = clean_text(row_a["fighter"])
        fighter_b = clean_text(row_b["fighter"])

        rating_a_before = ratings[fighter_a]
        rating_b_before = ratings[fighter_b]

        history_a = rating_history[fighter_a]
        history_b = rating_history[fighter_b]

        # Save pre-fight Elo features for Fighter A.
        prior_elo_by_index[index_a] = rating_a_before
        prior_peak_elo_by_index[index_a] = max(history_a) if history_a else BASE_ELO
        prior_lowest_elo_by_index[index_a] = min(history_a) if history_a else BASE_ELO
        prior_elo_change_last_3_by_index[index_a] = calculate_prior_elo_change_last_3(
            current_rating=rating_a_before,
            history=history_a,
        )
        prior_elo_fights_by_index[index_a] = len(history_a)
        sos_by_index[index_a] = compute_sos_features(
            opponent_elo_history[fighter_a],
            opponent_result_history[fighter_a],
        )

        # Save pre-fight Elo features for Fighter B.
        prior_elo_by_index[index_b] = rating_b_before
        prior_peak_elo_by_index[index_b] = max(history_b) if history_b else BASE_ELO
        prior_lowest_elo_by_index[index_b] = min(history_b) if history_b else BASE_ELO
        prior_elo_change_last_3_by_index[index_b] = calculate_prior_elo_change_last_3(
            current_rating=rating_b_before,
            history=history_b,
        )
        prior_elo_fights_by_index[index_b] = len(history_b)
        sos_by_index[index_b] = compute_sos_features(
            opponent_elo_history[fighter_b],
            opponent_result_history[fighter_b],
        )

        actual_a = float(row_a["target_is_winner"])
        actual_b = float(row_b["target_is_winner"])

        # Record who each fighter faced (opponent's pre-fight Elo). This happens
        # after their SoS features are saved, so the current opponent is excluded
        # from the current-fight values.
        opponent_elo_history[fighter_a].append(rating_b_before)
        opponent_result_history[fighter_a].append(int(actual_a == 1))
        opponent_elo_history[fighter_b].append(rating_a_before)
        opponent_result_history[fighter_b].append(int(actual_b == 1))

        # If this is not a clear winner/loser fight, do not update ratings.
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

    df["prior_elo"] = df.index.map(prior_elo_by_index)
    df["prior_peak_elo"] = df.index.map(prior_peak_elo_by_index)
    df["prior_lowest_elo"] = df.index.map(prior_lowest_elo_by_index)
    df["prior_elo_change_last_3"] = df.index.map(prior_elo_change_last_3_by_index)
    df["prior_elo_fights"] = df.index.map(prior_elo_fights_by_index)

    for column in SOS_FEATURE_COLUMNS:
        df[column] = df.index.map(
            {index: features.get(column) for index, features in sos_by_index.items()}
        )

    df = df.drop(columns=["event_date_parsed"])

    return df


def save_snapshots_with_elo(df: pd.DataFrame) -> None:
    if not BACKUP_SNAPSHOTS_CSV.exists():
        shutil.copy(FIGHTER_SNAPSHOTS_CSV, BACKUP_SNAPSHOTS_CSV)
        print(f"Created backup: {BACKUP_SNAPSHOTS_CSV}")

    df.to_csv(FIGHTER_SNAPSHOTS_CSV, index=False)


def main() -> None:
    print("Loading fighter snapshots...")
    snapshots_df = load_snapshots()

    print(f"Loaded {len(snapshots_df)} fighter snapshots.")

    print("Adding Elo features...")
    snapshots_with_elo_df = add_elo_features(snapshots_df)

    save_snapshots_with_elo(snapshots_with_elo_df)

    print()
    print(f"Saved Elo-enhanced snapshots to: {FIGHTER_SNAPSHOTS_CSV}")

    print()
    print("Preview:")
    preview_columns = [
        "event_date",
        "fighter",
        "opponent",
        "target_is_winner",
        "prior_fights",
        "prior_elo",
        "prior_peak_elo",
        "prior_lowest_elo",
        "prior_elo_change_last_3",
        "prior_elo_fights",
    ]

    print(snapshots_with_elo_df[preview_columns].head(30))


if __name__ == "__main__":
    main()