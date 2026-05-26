from __future__ import annotations

import string
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

from app.data.ufcstats_fetcher import fetch_ufcstats_html

import re

BASE_URL = "http://ufcstats.com"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
FIGHTER_PROFILES_CSV = RAW_DATA_DIR / "fighter_profiles.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 UFC predictor learning project "
        "(contact: local-development)"
    )
}


@dataclass
class FighterProfile:
    fighter: str
    first_name: str
    last_name: str
    nickname: str
    profile_url: str

    height_raw: str
    weight_raw: str
    reach_raw: str
    stance: str

    height_inches: float | None
    weight_lbs: float | None
    reach_inches: float | None

    current_wins: int | None
    current_losses: int | None
    current_draws: int | None
    belt: str

    dob_raw: str
    dob: str


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def get_soup(url: str) -> BeautifulSoup:
    """Downloads UFCStats HTML and turns it into BeautifulSoup."""
    html = fetch_ufcstats_html(url)
    return BeautifulSoup(html, "html.parser")


def parse_height_to_inches(value: Any) -> float | None:
    """
    Converts UFCStats height values like:
        5' 11"
    into:
        71.0
    """
    value = clean_text(value)

    if not value or value == "--":
        return None

    try:
        feet_part, inches_part = value.split("'", 1)

        feet = float(feet_part.strip())

        inches_text = (
            inches_part
            .replace('"', "")
            .replace("”", "")
            .replace("in", "")
            .strip()
        )

        inches = float(inches_text)

        return feet * 12.0 + inches

    except ValueError:
        return None


def parse_weight_lbs(value: Any) -> float | None:
    """
    Converts values like:
        155 lbs.
    into:
        155.0
    """
    value = clean_text(value)

    if not value or value == "--":
        return None

    cleaned = (
        value
        .replace("lbs.", "")
        .replace("lbs", "")
        .replace("lb.", "")
        .replace("lb", "")
        .strip()
    )

    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_reach_inches(value: Any) -> float | None:
    """
    Converts values like:
        75.0"
    into:
        75.0
    """
    value = clean_text(value)

    if not value or value == "--":
        return None

    cleaned = (
        value
        .replace('"', "")
        .replace("”", "")
        .replace("in", "")
        .strip()
    )

    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    value = clean_text(value)

    if not value or value == "--":
        return None

    try:
        return int(value)
    except ValueError:
        return None


def parse_dob_to_iso(value: Any) -> str:
    value = clean_text(value)

    if not value or value == "--":
        return ""

    parsed_date = pd.to_datetime(value, errors="coerce")

    if pd.isna(parsed_date):
        return ""

    return parsed_date.date().isoformat()


def parse_profile_detail_items(soup: BeautifulSoup) -> dict[str, str]:
    details: dict[str, str] = {}

    for item in soup.select("li.b-list__box-list-item"):
        title_element = item.select_one("i.b-list__box-item-title")

        if title_element is None:
            continue

        label = clean_text(title_element.get_text()).replace(":", "").lower()

        full_text = clean_text(item.get_text(" "))
        label_text = clean_text(title_element.get_text(" "))
        value = clean_text(full_text.replace(label_text, "", 1))

        details[label] = value

    return details

def extract_dob_text(text: Any) -> str:
    text = clean_text(text)

    if not text or "DOB:" not in text:
        return ""

    match = re.search(
        r"DOB:\s*([A-Za-z]{3}\s+\d{1,2},\s+\d{4})",
        text,
    )

    if not match:
        return ""

    return clean_text(match.group(1))

def scrape_dob_from_profile_page(profile_url: str) -> tuple[str, str]:
    profile_url = clean_text(profile_url)

    if not profile_url:
        return "", ""

    soup = get_soup(profile_url)

    # UFCStats often stores all profile details in one list item, so we extract
    # the DOB date pattern directly from the item text.
    for item in soup.select("li.b-list__box-list-item"):
        dob_raw = extract_dob_text(item.get_text(" "))

        if dob_raw:
            return dob_raw, parse_dob_to_iso(dob_raw)

    # Fallback: search all list items.
    for item in soup.select("li"):
        dob_raw = extract_dob_text(item.get_text(" "))

        if dob_raw:
            return dob_raw, parse_dob_to_iso(dob_raw)

    # Final fallback: search the whole page.
    dob_raw = extract_dob_text(soup.get_text(" "))

    if dob_raw:
        return dob_raw, parse_dob_to_iso(dob_raw)

    return "", ""


def load_existing_dob_lookup() -> dict[str, tuple[str, str]]:
    """
    Reads the existing fighter_profiles.csv, if present, so DOB values are preserved
    between scraper runs.

    This prevents the profile-list scrape from wiping dob_raw/dob every time.
    """
    if not FIGHTER_PROFILES_CSV.exists():
        return {}

    try:
        existing_df = pd.read_csv(FIGHTER_PROFILES_CSV)
    except pd.errors.EmptyDataError:
        return {}

    required_columns = {"profile_url", "dob_raw", "dob"}

    if not required_columns.issubset(existing_df.columns):
        return {}

    lookup: dict[str, tuple[str, str]] = {}

    for _, row in existing_df.iterrows():
        profile_url = clean_text(row.get("profile_url", ""))
        dob_raw = clean_text(row.get("dob_raw", ""))
        dob = clean_text(row.get("dob", ""))

        if not profile_url:
            continue

        if dob:
            lookup[profile_url] = (dob_raw, dob)

    return lookup


def scrape_profiles_for_letter(letter: str) -> list[FighterProfile]:
    url = f"{BASE_URL}/statistics/fighters?char={letter}&page=all"

    print(f"Scraping fighters for letter '{letter}'...")

    soup = get_soup(url)

    profiles: list[FighterProfile] = []

    rows = soup.select("tr.b-statistics__table-row")

    for row in rows:
        cells = row.find_all("td")

        if len(cells) < 11:
            continue

        first_name = clean_text(cells[0].get_text(" ", strip=True))
        last_name = clean_text(cells[1].get_text(" ", strip=True))
        nickname = clean_text(cells[2].get_text(" ", strip=True))

        if not first_name and not last_name:
            continue

        fighter = clean_text(f"{first_name} {last_name}")

        profile_link = row.find("a", href=True)
        profile_url = profile_link["href"].strip() if profile_link else ""

        height_raw = clean_text(cells[3].get_text(" ", strip=True))
        weight_raw = clean_text(cells[4].get_text(" ", strip=True))
        reach_raw = clean_text(cells[5].get_text(" ", strip=True))
        stance = clean_text(cells[6].get_text(" ", strip=True))

        current_wins = parse_int(cells[7].get_text(" ", strip=True))
        current_losses = parse_int(cells[8].get_text(" ", strip=True))
        current_draws = parse_int(cells[9].get_text(" ", strip=True))
        belt = clean_text(cells[10].get_text(" ", strip=True))

        profiles.append(
            FighterProfile(
                fighter=fighter,
                first_name=first_name,
                last_name=last_name,
                nickname=nickname,
                profile_url=profile_url,

                height_raw=height_raw,
                weight_raw=weight_raw,
                reach_raw=reach_raw,
                stance=stance,

                height_inches=parse_height_to_inches(height_raw),
                weight_lbs=parse_weight_lbs(weight_raw),
                reach_inches=parse_reach_inches(reach_raw),

                current_wins=current_wins,
                current_losses=current_losses,
                current_draws=current_draws,
                belt=belt,

                dob_raw="",
                dob="",
            )
        )

    print(f"    Found {len(profiles)} fighters.")

    return profiles


def scrape_all_fighter_profiles() -> list[FighterProfile]:
    all_profiles: list[FighterProfile] = []

    for letter in string.ascii_lowercase:
        try:
            profiles = scrape_profiles_for_letter(letter)
            all_profiles.extend(profiles)

        except Exception as error:
            print(f"    ERROR scraping letter '{letter}': {error}")

        time.sleep(0.25)

    # Remove duplicates while preserving order.
    seen_urls = set()
    seen_names = set()
    unique_profiles: list[FighterProfile] = []

    for profile in all_profiles:
        unique_key = profile.profile_url or profile.fighter

        if unique_key in seen_urls or profile.fighter in seen_names:
            continue

        unique_profiles.append(profile)
        seen_urls.add(unique_key)
        seen_names.add(profile.fighter)

    return unique_profiles


def add_dobs_to_profiles(profiles: list[FighterProfile]) -> list[FighterProfile]:
    existing_dob_lookup = load_existing_dob_lookup()

    already_known_count = 0
    scraped_count = 0
    unavailable_count = 0
    failed_count = 0

    print()
    print("Adding DOB data to fighter profiles...")
    print(f"Existing known DOBs available: {len(existing_dob_lookup)}")
    print()

    for index, profile in enumerate(profiles, start=1):
        existing_dob = existing_dob_lookup.get(profile.profile_url)

        if existing_dob is not None:
            profile.dob_raw = existing_dob[0]
            profile.dob = existing_dob[1]
            already_known_count += 1
            continue

        print(f"[{index}/{len(profiles)}] Scraping DOB: {profile.fighter}")

        try:
            dob_raw, dob = scrape_dob_from_profile_page(profile.profile_url)

            profile.dob_raw = dob_raw
            profile.dob = dob

            if dob:
                scraped_count += 1
                print(f"    DOB: {dob_raw} -> {dob}")
            else:
                unavailable_count += 1
                print("    DOB unavailable")

        except Exception as error:
            failed_count += 1
            print(f"    FAILED DOB scrape for {profile.fighter}: {error}")

        time.sleep(0.25)

    print()
    print("DOB summary")
    print("-" * 60)
    print(f"Already known: {already_known_count}")
    print(f"Newly scraped: {scraped_count}")
    print(f"Unavailable:   {unavailable_count}")
    print(f"Failed:        {failed_count}")

    return profiles


def save_profiles_csv(profiles: list[FighterProfile]) -> None:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame([asdict(profile) for profile in profiles])
    df.to_csv(FIGHTER_PROFILES_CSV, index=False)


def main() -> None:
    print("Scraping UFC fighter profiles...")

    profiles = scrape_all_fighter_profiles()

    if not profiles:
        raise RuntimeError("No fighter profiles were scraped.")

    profiles = add_dobs_to_profiles(profiles)

    save_profiles_csv(profiles)

    print()
    print(f"Saved {len(profiles)} fighter profiles.")
    print(f"Output file: {FIGHTER_PROFILES_CSV}")

    print()
    print("Preview:")
    preview_columns = [
        "fighter",
        "height_raw",
        "height_inches",
        "reach_raw",
        "reach_inches",
        "stance",
        "weight_raw",
        "weight_lbs",
        "dob_raw",
        "dob",
    ]

    preview_df = pd.DataFrame([asdict(profile) for profile in profiles])
    print(preview_df[preview_columns].head(20))


if __name__ == "__main__":
    main()