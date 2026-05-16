from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

FIGHTER_PROFILES_CSV = RAW_DATA_DIR / "fighter_profiles.csv"
FIGHTER_SNAPSHOTS_CSV = PROCESSED_DATA_DIR / "fighter_snapshots.csv"
BACKUP_SNAPSHOTS_CSV = PROCESSED_DATA_DIR / "fighter_snapshots_before_physical_backup.csv"


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


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def normalize_name(value: Any) -> str:
    """
    Normalizes names for joining.

    This simple version works for most UFCStats names.
    Later, we can add a manual alias file if some fighters do not match.
    """
    return clean_text(value).lower()


def normalize_stance(value: Any) -> str:
    stance = clean_text(value).lower()

    if stance in {"orthodox", "southpaw", "switch", "open stance", "sideways"}:
        return stance

    return "unknown"


def build_profile_features(profiles_df: pd.DataFrame) -> pd.DataFrame:
    profiles_df = profiles_df.copy()

    profiles_df["fighter_key"] = profiles_df["fighter"].apply(normalize_name)

    profiles_df["stance_normalized"] = profiles_df["stance"].apply(normalize_stance)

    profiles_df["height_inches"] = pd.to_numeric(
        profiles_df["height_inches"],
        errors="coerce",
    )
    profiles_df["reach_inches"] = pd.to_numeric(
        profiles_df["reach_inches"],
        errors="coerce",
    )

    profiles_df["reach_minus_height_inches"] = (
        profiles_df["reach_inches"] - profiles_df["height_inches"]
    )

    profiles_df["is_orthodox"] = (
        profiles_df["stance_normalized"] == "orthodox"
    ).astype(int)

    profiles_df["is_southpaw"] = (
        profiles_df["stance_normalized"] == "southpaw"
    ).astype(int)

    profiles_df["is_switch_stance"] = (
        profiles_df["stance_normalized"] == "switch"
    ).astype(int)

    profiles_df["is_open_stance"] = (
        profiles_df["stance_normalized"] == "open stance"
    ).astype(int)

    profiles_df["is_sideways_stance"] = (
        profiles_df["stance_normalized"] == "sideways"
    ).astype(int)

    profiles_df["is_stance_unknown"] = (
        profiles_df["stance_normalized"] == "unknown"
    ).astype(int)

    keep_columns = [
        "fighter_key",
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

    return profiles_df[keep_columns].drop_duplicates(subset=["fighter_key"])


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not FIGHTER_PROFILES_CSV.exists():
        raise FileNotFoundError(
            f"Missing {FIGHTER_PROFILES_CSV}. "
            "Run scrape_fighter_profiles.py first."
        )

    if not FIGHTER_SNAPSHOTS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {FIGHTER_SNAPSHOTS_CSV}. "
            "Run build_fighter_snapshots.py first."
        )

    profiles_df = pd.read_csv(FIGHTER_PROFILES_CSV)
    snapshots_df = pd.read_csv(FIGHTER_SNAPSHOTS_CSV)

    return profiles_df, snapshots_df


def add_physical_features_to_snapshots(
    profiles_df: pd.DataFrame,
    snapshots_df: pd.DataFrame,
) -> pd.DataFrame:
    snapshots_df = snapshots_df.copy()

    existing_physical_columns = [
        column for column in PHYSICAL_COLUMNS if column in snapshots_df.columns
    ]

    if existing_physical_columns:
        print(
            "Removing existing physical feature columns before recalculating: "
            f"{existing_physical_columns}"
        )
        snapshots_df = snapshots_df.drop(columns=existing_physical_columns)

    profiles_features_df = build_profile_features(profiles_df)

    snapshots_df["fighter_key"] = snapshots_df["fighter"].apply(normalize_name)

    merged_df = snapshots_df.merge(
        profiles_features_df,
        on="fighter_key",
        how="left",
    )

    merged_df = merged_df.drop(columns=["fighter_key"])

    return merged_df


def save_snapshots(df: pd.DataFrame) -> None:
    if not BACKUP_SNAPSHOTS_CSV.exists():
        shutil.copy(FIGHTER_SNAPSHOTS_CSV, BACKUP_SNAPSHOTS_CSV)
        print(f"Created backup: {BACKUP_SNAPSHOTS_CSV}")

    df.to_csv(FIGHTER_SNAPSHOTS_CSV, index=False)


def main() -> None:
    print("Loading fighter profiles and fighter snapshots...")
    profiles_df, snapshots_df = load_inputs()

    print(f"Loaded {len(profiles_df)} fighter profiles.")
    print(f"Loaded {len(snapshots_df)} fighter snapshots.")

    print("Adding physical features to fighter snapshots...")
    updated_snapshots_df = add_physical_features_to_snapshots(
        profiles_df=profiles_df,
        snapshots_df=snapshots_df,
    )

    save_snapshots(updated_snapshots_df)

    print()
    print(f"Saved physical-enhanced snapshots to: {FIGHTER_SNAPSHOTS_CSV}")

    print()
    print("Missing value rates for physical features:")
    print(updated_snapshots_df[PHYSICAL_COLUMNS].isna().mean().sort_values(ascending=False))

    print()
    print("Preview:")
    preview_columns = [
        "fighter",
        "opponent",
        "event_date",
        "height_inches",
        "reach_inches",
        "reach_minus_height_inches",
        "is_orthodox",
        "is_southpaw",
        "is_switch_stance",
    ]

    print(updated_snapshots_df[preview_columns].tail(20))


if __name__ == "__main__":
    main()