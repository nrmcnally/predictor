from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

FIGHTER_SNAPSHOTS_CSV = PROCESSED_DATA_DIR / "fighter_snapshots.csv"
TRAINING_MATCHUPS_CSV = PROCESSED_DATA_DIR / "training_matchups.csv"


ID_COLUMNS = {
    "fight_url",
    "event_name",
    "event_date",
    "fighter",
    "opponent",
    "weight_class",
    "method",
    "target_is_winner",
}


def clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""

    return " ".join(str(value).split())


def load_fighter_snapshots() -> pd.DataFrame:
    if not FIGHTER_SNAPSHOTS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {FIGHTER_SNAPSHOTS_CSV}. "
            "Run build_fighter_snapshots.py first."
        )

    return pd.read_csv(FIGHTER_SNAPSHOTS_CSV)


def get_numeric_feature_columns(df: pd.DataFrame) -> list[str]:
    """
    Finds numeric snapshot columns that can be used as model features.

    We intentionally exclude:
        - IDs and names
        - current fight result
        - method, because method is only known after the fight
    """
    numeric_columns = []

    for column in df.columns:
        if column in ID_COLUMNS:
            continue

        if pd.api.types.is_numeric_dtype(df[column]):
            numeric_columns.append(column)

    return numeric_columns


def build_single_matchup_row(
    fighter_a_row: pd.Series,
    fighter_b_row: pd.Series,
    numeric_feature_columns: list[str],
) -> dict[str, Any]:
    """
    Builds one model row from Fighter A's perspective.

    The model will receive:
        fighter_a_feature - fighter_b_feature

    Example:
        diff_prior_win_rate = A prior win rate - B prior win rate
    """
    row = {
        "fight_url": clean_text(fighter_a_row["fight_url"]),
        "event_name": clean_text(fighter_a_row["event_name"]),
        "event_date": clean_text(fighter_a_row["event_date"]),
        "weight_class": clean_text(fighter_a_row["weight_class"]),

        "fighter_a": clean_text(fighter_a_row["fighter"]),
        "fighter_b": clean_text(fighter_b_row["fighter"]),

        "target": int(fighter_a_row["target_is_winner"]),
    }

    for column in numeric_feature_columns:
        fighter_a_value = fighter_a_row[column]
        fighter_b_value = fighter_b_row[column]

        row[f"a_{column}"] = fighter_a_value
        row[f"b_{column}"] = fighter_b_value
        row[f"diff_{column}"] = fighter_a_value - fighter_b_value

    return row


def build_matchup_training_rows(snapshots_df: pd.DataFrame) -> pd.DataFrame:
    snapshots_df = snapshots_df.copy()

    numeric_feature_columns = get_numeric_feature_columns(snapshots_df)

    print(f"Using {len(numeric_feature_columns)} numeric snapshot features.")
    print("Feature columns:")
    for column in numeric_feature_columns:
        print(f"- {column}")

    matchup_rows = []

    grouped = snapshots_df.groupby("fight_url", sort=False)

    skipped_fights = 0

    for fight_url, fight_rows in grouped:
        if len(fight_rows) != 2:
            skipped_fights += 1
            continue

        fighter_rows = list(fight_rows.itertuples(index=False, name=None))
        fight_columns = list(fight_rows.columns)

        row_1 = pd.Series(fighter_rows[0], index=fight_columns)
        row_2 = pd.Series(fighter_rows[1], index=fight_columns)

        # Skip rows without a clear winner/loser.
        # For this dataset, this should rarely happen because we filtered earlier.
        if row_1["target_is_winner"] == row_2["target_is_winner"]:
            skipped_fights += 1
            continue

        # Normal row
        matchup_rows.append(
            build_single_matchup_row(
                fighter_a_row=row_1,
                fighter_b_row=row_2,
                numeric_feature_columns=numeric_feature_columns,
            )
        )

        # Mirrored row
        matchup_rows.append(
            build_single_matchup_row(
                fighter_a_row=row_2,
                fighter_b_row=row_1,
                numeric_feature_columns=numeric_feature_columns,
            )
        )

    if skipped_fights:
        print(f"Skipped {skipped_fights} fights because they were not usable.")

    return pd.DataFrame(matchup_rows)


def save_training_matchups(df: pd.DataFrame) -> None:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TRAINING_MATCHUPS_CSV, index=False)


def main() -> None:
    print("Loading fighter snapshots...")
    snapshots_df = load_fighter_snapshots()

    print(f"Loaded {len(snapshots_df)} fighter snapshots.")

    print("Building matchup training rows...")
    matchups_df = build_matchup_training_rows(snapshots_df)

    save_training_matchups(matchups_df)

    print()
    print(f"Saved {len(matchups_df)} matchup rows.")
    print(f"Output file: {TRAINING_MATCHUPS_CSV}")

    print()
    print("Target distribution:")
    print(matchups_df["target"].value_counts(dropna=False))

    print()
    print("Preview:")
    preview_columns = [
        "event_date",
        "fighter_a",
        "fighter_b",
        "target",
        "diff_prior_fights",
        "diff_prior_win_rate",
        "diff_days_since_last_fight",
        "diff_avg_sig_str_differential_per_15",
        "diff_avg_td_landed_per_15",
    ]

    existing_preview_columns = [
        column for column in preview_columns if column in matchups_df.columns
    ]

    print(matchups_df[existing_preview_columns].head(20))


if __name__ == "__main__":
    main()