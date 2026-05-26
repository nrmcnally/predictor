from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import List

import pandas as pd
from bs4 import BeautifulSoup

from app.data.ufcstats_fetcher import fetch_ufcstats_html


BASE_URL = "http://www.ufcstats.com"
COMPLETED_EVENTS_URL = f"{BASE_URL}/statistics/events/completed?page=all"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
COMPLETED_EVENTS_CSV = RAW_DATA_DIR / "completed_events.csv"
APP_TIMEZONE = ZoneInfo("America/New_York")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 UFC predictor learning project "
        "(contact: local-development)"
    )
}


@dataclass
class UFCEvent:
    name: str
    date: str
    location: str
    url: str


def clean_text(value: str) -> str:
    """
    Normalizes messy website text.

    Example:
        '  UFC 300\\n\\n Las Vegas ' -> 'UFC 300 Las Vegas'
    """
    return " ".join(value.split())

def is_future_event(event_date: str) -> bool:
    """
    Returns True if the event date is after today's date.

    This protects us from UFCStats accidentally listing upcoming events
    on the completed-events page.
    """
    parsed_date = pd.to_datetime(event_date, errors="coerce")

    if pd.isna(parsed_date):
        return False

    event_day = parsed_date.date()
    today = datetime.now(APP_TIMEZONE).date()

    return event_day > today

def get_soup(url: str) -> BeautifulSoup:
    """Downloads UFCStats HTML and turns it into BeautifulSoup."""
    html = fetch_ufcstats_html(url)
    return BeautifulSoup(html, "html.parser")


def fetch_completed_events() -> List[UFCEvent]:
    """
    Scrapes the UFCStats completed events page.

    Returns:
        A list of UFCEvent objects.
    """
    soup = get_soup(COMPLETED_EVENTS_URL)

    events: List[UFCEvent] = []

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
        location = ""

        if row is not None:
            date_element = row.select_one(".b-statistics__date")

            if date_element is not None:
                event_date = clean_text(date_element.get_text(" ", strip=True))

            columns = row.find_all("td")

            if len(columns) >= 2:
                location = clean_text(columns[-1].get_text(" ", strip=True))

        if is_future_event(event_date):
            print(f"Skipping future event: {event_name} | {event_date}")
            continue

        events.append(
            UFCEvent(
                name=event_name,
                date=event_date,
                location=location,
                url=href,
            )
        )   

    # Remove duplicates while preserving order.
    seen_urls = set()
    unique_events: List[UFCEvent] = []

    for event in events:
        if event.url not in seen_urls:
            unique_events.append(event)
            seen_urls.add(event.url)

    return unique_events


def save_completed_events_csv(events: List[UFCEvent]) -> None:
    """
    Saves completed UFC events to backend/data/raw/completed_events.csv.
    """
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    event_rows = [asdict(event) for event in events]
    df = pd.DataFrame(event_rows)

    df.to_csv(COMPLETED_EVENTS_CSV, index=False)


def main() -> None:
    print("Fetching completed UFC events...")

    events = fetch_completed_events()

    if not events:
        raise RuntimeError("No events were found. The page structure may have changed.")

    save_completed_events_csv(events)

    print(f"Saved {len(events)} completed events.")
    print(f"Output file: {COMPLETED_EVENTS_CSV}")

    print("\nMost recent 5 events found:")
    for event in events[:5]:
        print(f"- {event.name} | {event.date} | {event.location}")


if __name__ == "__main__":
    main()