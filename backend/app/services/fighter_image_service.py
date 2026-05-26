from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIGHTER_IMAGES_CSV = PROJECT_ROOT / "data" / "raw" / "fighter_images.csv"


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def normalize_fighter_name(value: Any) -> str:
    return clean_text(value).lower()


def get_initials(fighter_name: Any) -> str:
    fighter = clean_text(fighter_name)

    if not fighter:
        return "?"

    parts = [part for part in fighter.replace("-", " ").split() if part]

    if not parts:
        return "?"

    if len(parts) == 1:
        return parts[0][:2].upper()

    return f"{parts[0][0]}{parts[-1][0]}".upper()


def load_fighter_image_lookup() -> dict[str, dict[str, Any]]:
    if not FIGHTER_IMAGES_CSV.exists():
        return {}

    try:
        images_df = pd.read_csv(FIGHTER_IMAGES_CSV)
    except pd.errors.EmptyDataError:
        return {}

    required_columns = {"fighter", "image_url"}

    if not required_columns.issubset(images_df.columns):
        return {}

    lookup: dict[str, dict[str, Any]] = {}

    for _, row in images_df.iterrows():
        fighter = clean_text(row.get("fighter", ""))
        image_url = clean_text(row.get("image_url", ""))
        source_url = clean_text(row.get("source_url", ""))
        slug = clean_text(row.get("slug", ""))
        page_title = clean_text(row.get("page_title", ""))

        if not fighter:
            continue

        lookup[normalize_fighter_name(fighter)] = {
            "fighter": fighter,
            "image_url": image_url,
            "source_url": source_url,
            "slug": slug,
            "page_title": page_title,
            "initials": get_initials(fighter),
            "image_available": bool(image_url),
        }

    return lookup


def get_fighter_image_data(
    fighter_name: Any,
    image_lookup: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fighter = clean_text(fighter_name)

    if image_lookup is None:
        image_lookup = load_fighter_image_lookup()

    image_data = image_lookup.get(normalize_fighter_name(fighter), {})

    image_url = clean_text(image_data.get("image_url", ""))
    source_url = clean_text(image_data.get("source_url", ""))

    return {
        "fighter": fighter,
        "fighter_image_url": image_url,
        "fighter_image_source_url": source_url,
        "fighter_initials": clean_text(image_data.get("initials", "")) or get_initials(fighter),
        "fighter_image_available": bool(image_url),
    }