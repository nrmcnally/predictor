from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIGHTER_PROFILES_CSV = PROJECT_ROOT / "data" / "raw" / "fighter_profiles.csv"


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def parse_profile_detail_items(soup: BeautifulSoup) -> dict[str, str]:
    details: dict[str, str] = {}

    for item in soup.select("li.b-list__box-list-item"):
        title_element = item.select_one("i.b-list__box-item-title")

        if title_element is None:
            continue

        label = clean_text(title_element.get_text()).replace(":", "").lower()

        # Remove the label text from the full list item text.
        full_text = clean_text(item.get_text(" "))
        label_text = clean_text(title_element.get_text(" "))
        value = clean_text(full_text.replace(label_text, "", 1))

        details[label] = value

    return details


def scrape_dob(profile_url: str) -> tuple[str, str]:
    profile_url = clean_text(profile_url)

    if not profile_url:
        return "", ""

    response = requests.get(profile_url, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    details = parse_profile_detail_items(soup)

    dob_raw = clean_text(details.get("dob", ""))

    if dob_raw in {"", "--"}:
        return dob_raw, ""

    parsed_dob = pd.to_datetime(dob_raw, errors="coerce")

    if pd.isna(parsed_dob):
        return dob_raw, ""

    return dob_raw, parsed_dob.date().isoformat()


def enrich_fighter_profiles_with_dob(
    limit: int | None = None,
    delay_seconds: float = 0.25,
    force: bool = False,
) -> dict[str, Any]:
    if not FIGHTER_PROFILES_CSV.exists():
        raise FileNotFoundError(
            f"Missing {FIGHTER_PROFILES_CSV}. Run fighter profile scraping first."
        )

    df = pd.read_csv(FIGHTER_PROFILES_CSV)

    if "profile_url" not in df.columns:
        raise ValueError("fighter_profiles.csv must contain profile_url.")

    if "dob_raw" not in df.columns:
        df["dob_raw"] = ""

    if "dob" not in df.columns:
        df["dob"] = ""

    # Important:
    # If these columns are blank, pandas may read them as float64.
    # Force them to object/string-compatible columns before assigning DOB text.
    df["dob_raw"] = df["dob_raw"].fillna("").astype("object")
    df["dob"] = df["dob"].fillna("").astype("object")
    df["profile_url"] = df["profile_url"].fillna("").astype("object")

    if "fighter" in df.columns:
        df["fighter"] = df["fighter"].fillna("").astype("object")

    total_rows = len(df)
    updated_count = 0
    skipped_count = 0
    failed_count = 0

    rows_to_process = []

    for index, row in df.iterrows():
        existing_dob = clean_text(row.get("dob", ""))

        if existing_dob and not force:
            skipped_count += 1
            continue

        rows_to_process.append(index)

    if limit is not None:
        rows_to_process = rows_to_process[:limit]

    print(f"fighter_profiles rows: {total_rows}")
    print(f"rows needing DOB scrape: {len(rows_to_process)}")
    print(f"force refresh: {force}")
    print()

    for process_number, index in enumerate(rows_to_process, start=1):
        fighter = clean_text(df.at[index, "fighter"])
        profile_url = clean_text(df.at[index, "profile_url"])

        print(f"[{process_number}/{len(rows_to_process)}] {fighter}")

        try:
            dob_raw, dob = scrape_dob(profile_url)

            df.at[index, "dob_raw"] = dob_raw
            df.at[index, "dob"] = dob

            if dob:
                updated_count += 1
                print(f"    DOB: {dob_raw} -> {dob}")
            else:
                skipped_count += 1
                print(f"    DOB unavailable")

        except Exception as error:
            failed_count += 1
            print(f"    FAILED: {error}")

        time.sleep(delay_seconds)

    df.to_csv(FIGHTER_PROFILES_CSV, index=False)

    return {
        "rows_total": total_rows,
        "rows_processed": len(rows_to_process),
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "output_file": str(FIGHTER_PROFILES_CSV),
    }


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of fighter profiles to process for testing.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.25,
        help="Delay between requests in seconds.",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape DOB even when the dob column already has a value.",
    )

    args = parser.parse_args()

    result = enrich_fighter_profiles_with_dob(
        limit=args.limit,
        delay_seconds=args.delay,
        force=args.force,
    )

    print()
    print("DOB enrichment complete")
    print("=" * 60)

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()