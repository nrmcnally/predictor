from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

FIGHTER_PROFILES_CSV = RAW_DATA_DIR / "fighter_profiles.csv"
FIGHTER_SNAPSHOTS_CSV = PROCESSED_DATA_DIR / "fighter_snapshots.csv"
CURRENT_FIGHTER_FEATURES_CSV = PROCESSED_DATA_DIR / "current_fighter_features.csv"


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def load_profiles_with_dob() -> pd.DataFrame:
    if not FIGHTER_PROFILES_CSV.exists():
        raise FileNotFoundError(
            f"Missing {FIGHTER_PROFILES_CSV}. Run fighter profile scraping first."
        )

    profiles_df = pd.read_csv(FIGHTER_PROFILES_CSV)

    if "fighter" not in profiles_df.columns:
        raise ValueError("fighter_profiles.csv must contain fighter.")

    if "dob" not in profiles_df.columns:
        raise ValueError(
            "fighter_profiles.csv does not contain dob. "
            "Run app.data.enrich_fighter_profiles_dob first."
        )

    keep_columns = ["fighter", "dob"]

    if "dob_raw" in profiles_df.columns:
        keep_columns.append("dob_raw")

    profiles_df = profiles_df[keep_columns].copy()
    profiles_df["fighter"] = profiles_df["fighter"].apply(clean_text)
    profiles_df["dob"] = pd.to_datetime(profiles_df["dob"], errors="coerce")

    profiles_df = profiles_df.drop_duplicates(subset=["fighter"], keep="last")

    return profiles_df


def calculate_age_years(
    dob_series: pd.Series,
    reference_date_series: pd.Series,
) -> pd.Series:
    age_days = (reference_date_series - dob_series).dt.days
    age_years = age_days / 365.25

    age_years = age_years.where(age_years >= 0)
    age_years = age_years.where(age_years <= 80)

    return age_years.round(2)


def add_age_to_fighter_snapshots(profiles_df: pd.DataFrame) -> dict[str, Any]:
    if not FIGHTER_SNAPSHOTS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {FIGHTER_SNAPSHOTS_CSV}. Build fighter snapshots first."
        )

    snapshots_df = pd.read_csv(FIGHTER_SNAPSHOTS_CSV)

    if "fighter" not in snapshots_df.columns:
        raise ValueError("fighter_snapshots.csv must contain fighter.")

    if "event_date" not in snapshots_df.columns:
        raise ValueError("fighter_snapshots.csv must contain event_date.")

    columns_to_remove = [
        column
        for column in ["dob", "dob_raw", "age_years", "age_known"]
        if column in snapshots_df.columns
    ]

    if columns_to_remove:
        snapshots_df = snapshots_df.drop(columns=columns_to_remove)

    snapshots_df["fighter"] = snapshots_df["fighter"].apply(clean_text)

    snapshots_df = snapshots_df.merge(
        profiles_df,
        on="fighter",
        how="left",
    )

    snapshots_df["event_date_parsed_for_age"] = pd.to_datetime(
        snapshots_df["event_date"],
        errors="coerce",
    )

    snapshots_df["age_years"] = calculate_age_years(
        dob_series=snapshots_df["dob"],
        reference_date_series=snapshots_df["event_date_parsed_for_age"],
    )

    snapshots_df["age_known"] = snapshots_df["age_years"].notna().astype(int)

    snapshots_df = snapshots_df.drop(columns=["event_date_parsed_for_age"])

    snapshots_df.to_csv(FIGHTER_SNAPSHOTS_CSV, index=False)

    return {
        "file": str(FIGHTER_SNAPSHOTS_CSV),
        "rows": int(len(snapshots_df)),
        "age_known_rows": int(snapshots_df["age_known"].sum()),
        "age_coverage": float(snapshots_df["age_known"].mean()),
    }


def add_age_to_current_fighter_features(profiles_df: pd.DataFrame) -> dict[str, Any]:
    if not CURRENT_FIGHTER_FEATURES_CSV.exists():
        return {
            "file": str(CURRENT_FIGHTER_FEATURES_CSV),
            "skipped": True,
            "reason": "current_fighter_features.csv does not exist yet.",
        }

    current_df = pd.read_csv(CURRENT_FIGHTER_FEATURES_CSV)

    if "fighter" not in current_df.columns:
        raise ValueError("current_fighter_features.csv must contain fighter.")

    columns_to_remove = [
        column
        for column in ["dob", "dob_raw", "age_years", "age_known"]
        if column in current_df.columns
    ]

    if columns_to_remove:
        current_df = current_df.drop(columns=columns_to_remove)

    current_df["fighter"] = current_df["fighter"].apply(clean_text)

    current_df = current_df.merge(
        profiles_df,
        on="fighter",
        how="left",
    )

    today = pd.Timestamp(date.today())

    current_df["current_date_for_age"] = today

    current_df["age_years"] = calculate_age_years(
        dob_series=current_df["dob"],
        reference_date_series=current_df["current_date_for_age"],
    )

    current_df["age_known"] = current_df["age_years"].notna().astype(int)

    current_df = current_df.drop(columns=["current_date_for_age"])

    current_df.to_csv(CURRENT_FIGHTER_FEATURES_CSV, index=False)

    return {
        "file": str(CURRENT_FIGHTER_FEATURES_CSV),
        "skipped": False,
        "rows": int(len(current_df)),
        "age_known_rows": int(current_df["age_known"].sum()),
        "age_coverage": float(current_df["age_known"].mean()),
    }


def add_age_features() -> dict[str, Any]:
    profiles_df = load_profiles_with_dob()

    snapshot_result = add_age_to_fighter_snapshots(profiles_df)
    current_result = add_age_to_current_fighter_features(profiles_df)

    return {
        "profiles_file": str(FIGHTER_PROFILES_CSV),
        "profile_rows": int(len(profiles_df)),
        "profiles_with_dob": int(profiles_df["dob"].notna().sum()),
        "snapshot_result": snapshot_result,
        "current_result": current_result,
    }


def main() -> None:
    result = add_age_features()

    print()
    print("Age feature enrichment complete")
    print("=" * 70)

    print(f"Profiles: {result['profile_rows']}")
    print(f"Profiles with DOB: {result['profiles_with_dob']}")
    print()

    print("fighter_snapshots.csv")
    print("-" * 70)

    for key, value in result["snapshot_result"].items():
        print(f"{key}: {value}")

    print()
    print("current_fighter_features.csv")
    print("-" * 70)

    for key, value in result["current_result"].items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()