from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

FIGHTER_PROFILES_CSV = RAW_DATA_DIR / "fighter_profiles.csv"
FIGHTER_DOBS_BACKUP_CSV = RAW_DATA_DIR / "fighter_dobs_backup.csv"


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def read_csv_as_text(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def ensure_dob_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "dob_raw" not in df.columns:
        df["dob_raw"] = ""

    if "dob" not in df.columns:
        df["dob"] = ""

    if "profile_url" not in df.columns:
        df["profile_url"] = ""

    if "fighter" not in df.columns:
        df["fighter"] = ""

    df["fighter"] = df["fighter"].apply(clean_text)
    df["profile_url"] = df["profile_url"].apply(clean_text)
    df["dob_raw"] = df["dob_raw"].apply(clean_text)
    df["dob"] = df["dob"].apply(clean_text)

    return df


def build_dob_lookup(backup_df: pd.DataFrame) -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, str]]]:
    by_url: dict[str, tuple[str, str]] = {}
    by_fighter: dict[str, tuple[str, str]] = {}

    for _, row in backup_df.iterrows():
        fighter = clean_text(row.get("fighter", ""))
        profile_url = clean_text(row.get("profile_url", ""))
        dob_raw = clean_text(row.get("dob_raw", ""))
        dob = clean_text(row.get("dob", ""))

        if not dob:
            continue

        if profile_url:
            by_url[profile_url] = (dob_raw, dob)

        if fighter:
            by_fighter[fighter] = (dob_raw, dob)

    return by_url, by_fighter


def write_backup_from_profiles(profiles_df: pd.DataFrame) -> int:
    backup_columns = ["fighter", "profile_url", "dob_raw", "dob"]

    backup_df = profiles_df.copy()

    for column in backup_columns:
        if column not in backup_df.columns:
            backup_df[column] = ""

    backup_df = backup_df[backup_columns].copy()
    backup_df = ensure_dob_columns(backup_df)

    backup_df.to_csv(FIGHTER_DOBS_BACKUP_CSV, index=False)

    return int((backup_df["dob"] != "").sum())


def restore_fighter_dobs_from_backup() -> dict[str, Any]:
    if not FIGHTER_PROFILES_CSV.exists():
        raise FileNotFoundError(
            f"Missing {FIGHTER_PROFILES_CSV}. Run fighter profile scraping first."
        )

    profiles_df = read_csv_as_text(FIGHTER_PROFILES_CSV)
    profiles_df = ensure_dob_columns(profiles_df)

    dob_count_before = int((profiles_df["dob"] != "").sum())

    if not FIGHTER_DOBS_BACKUP_CSV.exists():
        backup_dob_count = write_backup_from_profiles(profiles_df)

        return {
            "profiles_file": str(FIGHTER_PROFILES_CSV),
            "backup_file": str(FIGHTER_DOBS_BACKUP_CSV),
            "backup_existed": False,
            "rows": int(len(profiles_df)),
            "dob_count_before": dob_count_before,
            "restored_count": 0,
            "dob_count_after": dob_count_before,
            "backup_dob_count": backup_dob_count,
            "message": "No DOB backup existed, so one was created from current profiles.",
        }

    backup_df = read_csv_as_text(FIGHTER_DOBS_BACKUP_CSV)
    backup_df = ensure_dob_columns(backup_df)

    by_url, by_fighter = build_dob_lookup(backup_df)

    restored_count = 0

    for index, row in profiles_df.iterrows():
        current_dob = clean_text(row.get("dob", ""))

        if current_dob:
            continue

        profile_url = clean_text(row.get("profile_url", ""))
        fighter = clean_text(row.get("fighter", ""))

        restored_value = None

        if profile_url and profile_url in by_url:
            restored_value = by_url[profile_url]
        elif fighter and fighter in by_fighter:
            restored_value = by_fighter[fighter]

        if restored_value is None:
            continue

        dob_raw, dob = restored_value

        profiles_df.at[index, "dob_raw"] = dob_raw
        profiles_df.at[index, "dob"] = dob
        restored_count += 1

    profiles_df.to_csv(FIGHTER_PROFILES_CSV, index=False)

    dob_count_after = int((profiles_df["dob"] != "").sum())
    backup_dob_count = write_backup_from_profiles(profiles_df)

    return {
        "profiles_file": str(FIGHTER_PROFILES_CSV),
        "backup_file": str(FIGHTER_DOBS_BACKUP_CSV),
        "backup_existed": True,
        "rows": int(len(profiles_df)),
        "dob_count_before": dob_count_before,
        "restored_count": restored_count,
        "dob_count_after": dob_count_after,
        "backup_dob_count": backup_dob_count,
        "message": "DOB restore completed.",
    }


def main() -> None:
    result = restore_fighter_dobs_from_backup()

    print()
    print("DOB restore complete")
    print("=" * 70)

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()