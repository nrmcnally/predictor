from __future__ import annotations

import argparse
import re
import time
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

from app.repositories import future_cards_repository, saved_predictions_repository


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

FIGHTER_IMAGES_CSV = RAW_DATA_DIR / "fighter_images.csv"
UPCOMING_FIGHTS_CSV = RAW_DATA_DIR / "upcoming_fights.csv"
SAVED_CARD_PREDICTIONS_CSV = PROCESSED_DATA_DIR / "saved_card_predictions.csv"
CURRENT_FIGHTER_FEATURES_CSV = PROCESSED_DATA_DIR / "current_fighter_features.csv"

UFC_ATHLETE_BASE_URL = "https://www.ufc.com/athlete"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    )
}


@dataclass
class FighterImage:
    fighter: str
    image_url: str
    source_url: str
    slug: str
    page_title: str


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def normalize_name(value: Any) -> str:
    text = clean_text(value).lower()
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def slugify_name(value: Any) -> str:
    normalized = normalize_name(value)
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")


def build_slug_candidates(fighter: str) -> list[str]:
    base_slug = slugify_name(fighter)

    candidates = [base_slug]

    # Common UFC.com variations.
    cleaned = normalize_name(fighter)

    # Handle names like O'Malley where UFC.com may remove the apostrophe
    # without inserting a hyphen: Sean O'Malley -> sean-omalley
    if "'" in fighter or "’" in fighter:
        no_apostrophe = (
            clean_text(fighter)
            .replace("'", "")
            .replace("’", "")
        )
        candidates.append(slugify_name(no_apostrophe))

    suffixes = [" jr", " sr", " ii", " iii", " iv"]

    for suffix in suffixes:
        if cleaned.endswith(suffix):
            candidates.append(slugify_name(cleaned[: -len(suffix)]))

    # Some pages omit particles or punctuation-like parts.
    candidates.append(slugify_name(cleaned.replace(" de ", " ")))
    candidates.append(slugify_name(cleaned.replace(" da ", " ")))
    candidates.append(slugify_name(cleaned.replace(" dos ", " ")))

    unique_candidates = []

    for candidate in candidates:
        if candidate and candidate not in unique_candidates:
            unique_candidates.append(candidate)

    return unique_candidates


def load_existing_images() -> dict[str, FighterImage]:
    if not FIGHTER_IMAGES_CSV.exists():
        return {}

    try:
        df = pd.read_csv(FIGHTER_IMAGES_CSV)
    except pd.errors.EmptyDataError:
        return {}

    if "fighter" not in df.columns or "image_url" not in df.columns:
        return {}

    lookup: dict[str, FighterImage] = {}

    for _, row in df.iterrows():
        fighter = clean_text(row.get("fighter", ""))
        image_url = clean_text(row.get("image_url", ""))

        if not fighter or not image_url:
            continue

        lookup[normalize_name(fighter)] = FighterImage(
            fighter=fighter,
            image_url=image_url,
            source_url=clean_text(row.get("source_url", "")),
            slug=clean_text(row.get("slug", "")),
            page_title=clean_text(row.get("page_title", "")),
        )

    return lookup


def load_fighters_from_upcoming() -> list[str]:
    df = future_cards_repository.read_upcoming_fights_df()

    names = []

    for column in ["fighter_1", "fighter_2"]:
        if column in df.columns:
            names.extend(df[column].dropna().astype(str).tolist())

    return names


def load_fighters_from_saved_predictions() -> list[str]:
    df = saved_predictions_repository.read_all_df()

    names = []

    for column in ["fighter_1", "fighter_2"]:
        if column in df.columns:
            names.extend(df[column].dropna().astype(str).tolist())

    return names


def load_fighters_from_current_features() -> list[str]:
    if not CURRENT_FIGHTER_FEATURES_CSV.exists():
        return []

    try:
        df = pd.read_csv(CURRENT_FIGHTER_FEATURES_CSV)
    except pd.errors.EmptyDataError:
        return []

    if "fighter" not in df.columns:
        return []

    return df["fighter"].dropna().astype(str).tolist()


def unique_names(names: list[str]) -> list[str]:
    seen = set()
    output = []

    for name in names:
        cleaned = clean_text(name)
        normalized = normalize_name(cleaned)

        if not cleaned or not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)
        output.append(cleaned)

    return output


def load_target_fighters(mode: str) -> list[str]:
    names = []

    if mode in {"priority", "future"}:
        names.extend(load_fighters_from_upcoming())
        names.extend(load_fighters_from_saved_predictions())

    if mode in {"priority", "current"}:
        names.extend(load_fighters_from_current_features())

    if mode == "all":
        names.extend(load_fighters_from_upcoming())
        names.extend(load_fighters_from_saved_predictions())
        names.extend(load_fighters_from_current_features())

    return unique_names(names)


def get_og_image_from_page(url: str) -> tuple[str, str]:
    response = requests.get(url, headers=HEADERS, timeout=30)

    if response.status_code == 404:
        return "", ""

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    image_meta = (
        soup.select_one('meta[property="og:image"]')
        or soup.select_one('meta[name="twitter:image"]')
    )

    if image_meta is None:
        return "", title

    image_url = clean_text(image_meta.get("content", ""))

    if not image_url:
        return "", title

    if "logo" in image_url.lower():
        return "", title

    return image_url, title


def scrape_image_for_fighter(fighter: str) -> FighterImage | None:
    for slug in build_slug_candidates(fighter):
        source_url = f"{UFC_ATHLETE_BASE_URL}/{slug}"

        try:
            image_url, page_title = get_og_image_from_page(source_url)
        except Exception as error:
            print(f"    ERROR {fighter} | {source_url}: {error}")
            continue

        if image_url:
            return FighterImage(
                fighter=fighter,
                image_url=image_url,
                source_url=source_url,
                slug=slug,
                page_title=page_title,
            )

    return None


def save_fighter_images(images_by_name: dict[str, FighterImage]) -> None:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    rows = [asdict(image) for image in images_by_name.values()]
    df = pd.DataFrame(rows)

    if df.empty:
        df = pd.DataFrame(
            columns=[
                "fighter",
                "image_url",
                "source_url",
                "slug",
                "page_title",
            ]
        )

    df = df.sort_values("fighter")
    df.to_csv(FIGHTER_IMAGES_CSV, index=False)


def scrape_fighter_images(
    mode: str,
    limit: int | None,
    delay_seconds: float,
    force: bool,
) -> dict[str, Any]:
    existing = load_existing_images()
    target_fighters = load_target_fighters(mode)

    if limit is not None:
        target_fighters = target_fighters[:limit]

    images_by_name = dict(existing)

    attempted_count = 0
    found_count = 0
    skipped_existing_count = 0
    missing_count = 0

    print(f"Target fighters: {len(target_fighters)}")
    print(f"Existing image records: {len(existing)}")
    print()

    for index, fighter in enumerate(target_fighters, start=1):
        normalized = normalize_name(fighter)

        if not force and normalized in images_by_name:
            skipped_existing_count += 1
            continue

        attempted_count += 1

        print(f"[{index}/{len(target_fighters)}] Scraping image: {fighter}")

        image = scrape_image_for_fighter(fighter)

        if image is None:
            missing_count += 1
            print("    Image unavailable")
        else:
            found_count += 1
            images_by_name[normalized] = image
            print(f"    Found: {image.image_url}")

        save_fighter_images(images_by_name)

        time.sleep(delay_seconds)

    save_fighter_images(images_by_name)

    return {
        "mode": mode,
        "target_fighters": len(target_fighters),
        "existing_before": len(existing),
        "attempted": attempted_count,
        "found": found_count,
        "missing": missing_count,
        "skipped_existing": skipped_existing_count,
        "total_saved": len(images_by_name),
        "output_file": str(FIGHTER_IMAGES_CSV),
    }


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        choices=["priority", "future", "current", "all"],
        default="future",
        help=(
            "future = upcoming/saved card fighters only; "
            "current = current fighter features only; "
            "priority = future/saved plus current; "
            "all = every available source."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of fighters to try.",
    )

    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.2,
        help="Delay between UFC.com requests.",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape fighters even if image data already exists.",
    )

    args = parser.parse_args()

    result = scrape_fighter_images(
        mode=args.mode,
        limit=args.limit,
        delay_seconds=args.delay_seconds,
        force=args.force,
    )

    print()
    print("Fighter image scrape complete")
    print("=" * 80)

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()