from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

from app.data.ufcstats_fetcher import fetch_ufcstats_html
from app.repositories import future_cards_repository


BASE_URL = "http://ufcstats.com"
UPCOMING_EVENTS_URL = f"{BASE_URL}/statistics/events/upcoming?page=all"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
UPCOMING_EVENTS_CSV = RAW_DATA_DIR / "upcoming_events.csv"
UPCOMING_FIGHTS_CSV = RAW_DATA_DIR / "upcoming_fights.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 UFC predictor learning project "
        "(contact: local-development)"
    )
}


@dataclass
class UpcomingEvent:
    event_id: str
    event_name: str
    event_date: str
    event_location: str
    event_url: str


@dataclass
class UpcomingFight:
    event_id: str
    event_name: str
    event_date: str
    event_location: str
    event_url: str

    fight_url: str
    fighter_1: str
    fighter_2: str
    weight_class: str


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def get_soup(url: str) -> BeautifulSoup:
    """Downloads UFCStats HTML and turns it into BeautifulSoup."""
    html = fetch_ufcstats_html(url)
    return BeautifulSoup(html, "html.parser")


def make_event_id(event_url: str) -> str:
    """
    UFCStats event URLs usually end with the event hash.

    Example:
        http://ufcstats.com/event-details/abc123
        -> abc123
    """
    event_url = clean_text(event_url)
    return event_url.rstrip("/").split("/")[-1]


def make_fight_id(fight_url: str) -> str:
    fight_url = clean_text(fight_url)
    return fight_url.rstrip("/").split("/")[-1]


def fetch_upcoming_events() -> list[UpcomingEvent]:
    soup = get_soup(UPCOMING_EVENTS_URL)

    events: list[UpcomingEvent] = []

    event_links = soup.find_all("a", href=True)

    for link in event_links:
        href = link["href"].strip()

        if "/event-details/" not in href:
            continue

        event_name = clean_text(link.get_text(" ", strip=True))

        if not event_name:
            continue

        row = link.find_parent("tr")

        event_date = ""
        event_location = ""

        if row is not None:
            date_element = row.select_one(".b-statistics__date")

            if date_element is not None:
                event_date = clean_text(date_element.get_text(" ", strip=True))

            columns = row.find_all("td")

            if len(columns) >= 2:
                event_location = clean_text(columns[-1].get_text(" ", strip=True))

        event_url = href
        event_id = make_event_id(event_url)

        events.append(
            UpcomingEvent(
                event_id=event_id,
                event_name=event_name,
                event_date=event_date,
                event_location=event_location,
                event_url=event_url,
            )
        )

    seen = set()
    unique_events: list[UpcomingEvent] = []

    for event in events:
        if event.event_id in seen:
            continue

        unique_events.append(event)
        seen.add(event.event_id)

    return unique_events


def safe_column_text(columns: list, index: int) -> str:
    if index >= len(columns):
        return ""

    return clean_text(columns[index].get_text(" ", strip=True))


def extract_fighter_names(columns: list) -> tuple[str, str]:
    if len(columns) < 2:
        return "", ""

    fighter_column = columns[1]

    fighter_links = fighter_column.find_all("a")
    fighter_names = [
        clean_text(link.get_text(" ", strip=True))
        for link in fighter_links
        if clean_text(link.get_text(" ", strip=True))
    ]

    if len(fighter_names) >= 2:
        return fighter_names[0], fighter_names[1]

    fighter_paragraphs = fighter_column.find_all("p")
    fallback_names = [
        clean_text(paragraph.get_text(" ", strip=True))
        for paragraph in fighter_paragraphs
        if clean_text(paragraph.get_text(" ", strip=True))
    ]

    if len(fallback_names) >= 2:
        return fallback_names[0], fallback_names[1]

    return "", ""


def fetch_upcoming_fights_for_event(event: UpcomingEvent) -> list[UpcomingFight]:
    soup = get_soup(event.event_url)

    fights: list[UpcomingFight] = []

    fight_rows = soup.select("tr.b-fight-details__table-row")

    for row in fight_rows:
        fight_url = clean_text(row.get("data-link", ""))

        # Upcoming fights may or may not already have individual fight-detail URLs.
        # If no data-link exists, we still create a stable-ish ID from event/fighter names later.
        columns = row.find_all("td")

        fighter_1, fighter_2 = extract_fighter_names(columns)

        if not fighter_1 or not fighter_2:
            continue

        weight_class = safe_column_text(columns, 6)

        if not fight_url:
            fight_url = (
                f"upcoming://{event.event_id}/"
                f"{fighter_1.lower().replace(' ', '-')}-vs-"
                f"{fighter_2.lower().replace(' ', '-')}"
            )

        fights.append(
            UpcomingFight(
                event_id=event.event_id,
                event_name=event.event_name,
                event_date=event.event_date,
                event_location=event.event_location,
                event_url=event.event_url,
                fight_url=fight_url,
                fighter_1=fighter_1,
                fighter_2=fighter_2,
                weight_class=weight_class,
            )
        )

    return fights


def save_csvs(events: list[UpcomingEvent], fights: list[UpcomingFight]) -> None:
    # Full-replace both future-card tables in SQLite (kept the name for callers).
    future_cards_repository.replace_upcoming_events([asdict(event) for event in events])
    future_cards_repository.replace_upcoming_fights([asdict(fight) for fight in fights])


def scrape_upcoming_cards() -> tuple[list[UpcomingEvent], list[UpcomingFight]]:
    print("Fetching upcoming UFC events...")

    events = fetch_upcoming_events()

    print(f"Found {len(events)} upcoming events.")

    all_fights: list[UpcomingFight] = []

    for index, event in enumerate(events, start=1):
        print(f"[{index}/{len(events)}] Scraping fights for: {event.event_name}")

        try:
            fights = fetch_upcoming_fights_for_event(event)
            print(f"    Found {len(fights)} fights.")
            all_fights.extend(fights)

        except Exception as error:
            print(f"    ERROR scraping event: {error}")

        time.sleep(0.25)

    return events, all_fights


def main() -> None:
    events, fights = scrape_upcoming_cards()

    save_csvs(events, fights)

    print()
    print(f"Saved {len(events)} upcoming events.")
    print(f"Upcoming events file: {UPCOMING_EVENTS_CSV}")

    print()
    print(f"Saved {len(fights)} upcoming fights.")
    print(f"Upcoming fights file: {UPCOMING_FIGHTS_CSV}")

    print()
    print("Upcoming events preview:")
    for event in events[:10]:
        print(f"- {event.event_name} | {event.event_date} | {event.event_location}")

    print()
    print("Upcoming fights preview:")
    for fight in fights[:20]:
        print(
            f"- {fight.event_name}: "
            f"{fight.fighter_1} vs {fight.fighter_2} | {fight.weight_class}"
        )


if __name__ == "__main__":
    main()