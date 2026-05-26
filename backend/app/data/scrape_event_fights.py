from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

import pandas as pd
from bs4 import BeautifulSoup

from app.data.ufcstats_fetcher import fetch_ufcstats_html


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
COMPLETED_EVENTS_CSV = RAW_DATA_DIR / "completed_events.csv"
EVENT_FIGHTS_CSV = RAW_DATA_DIR / "event_fights.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 UFC predictor learning project "
        "(contact: local-development)"
    )
}


@dataclass
class EventFight:
    event_name: str
    event_date: str
    event_location: str
    event_url: str

    fight_url: str

    fighter_1: str
    fighter_2: str

    result_1: str
    result_2: str

    winner: str
    loser: str

    weight_class: str
    method: str
    round: str
    time: str


def clean_text(value: str) -> str:
    """
    Normalizes messy website text.

    Example:
        '  Islam\\n\\n Makhachev  ' -> 'Islam Makhachev'
    """
    return " ".join(value.split())


def get_soup(url: str) -> BeautifulSoup:
    """Downloads UFCStats HTML and turns it into BeautifulSoup."""
    html = fetch_ufcstats_html(url)
    return BeautifulSoup(html, "html.parser")


def safe_column_text(columns: list, index: int) -> str:
    """
    Safely pulls text out of a table column.

    If the column does not exist, return an empty string instead of crashing.
    """
    if index >= len(columns):
        return ""

    return clean_text(columns[index].get_text(" ", strip=True))


def determine_winner_and_loser(
    fighter_1: str,
    fighter_2: str,
    result_1: str,
    result_2: str,
) -> tuple[str, str]:
    """
    Determines winner and loser from result labels.

    Normal completed fights should become:
        result_1 = win
        result_2 = loss

    Draws and no contests intentionally return blank winner/loser.
    """
    r1 = str(result_1).lower().strip()
    r2 = str(result_2).lower().strip()

    if r1 == "win" and r2 == "loss":
        return fighter_1, fighter_2

    if r2 == "win" and r1 == "loss":
        return fighter_2, fighter_1

    return "", ""


def extract_fighter_names(columns: list) -> tuple[str, str]:
    """
    Extracts the two fighter names from the fighter column.

    The fighter names are usually inside <a> tags.
    """
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

    # Fallback: sometimes names can be stored in <p> tags.
    fighter_paragraphs = fighter_column.find_all("p")
    fallback_names = [
        clean_text(paragraph.get_text(" ", strip=True))
        for paragraph in fighter_paragraphs
        if clean_text(paragraph.get_text(" ", strip=True))
    ]

    if len(fallback_names) >= 2:
        return fallback_names[0], fallback_names[1]

    return "", ""


def extract_fighter_results(columns: list) -> tuple[str, str]:
    """
    Extracts the result labels for the two fighters.

    Important UFCStats behavior:
    The completed event table often lists the winner first and only shows
    one visible result label, usually:
        win

    In that case, we safely infer:
        fighter_1 = win
        fighter_2 = loss

    For draw/no contest rows, we keep both fighters as draw/nc.
    """
    if len(columns) < 1:
        return "", ""

    result_column = columns[0]

    valid_results = {"win", "loss", "draw", "nc"}

    raw_results = []

    for text in result_column.stripped_strings:
        result_text = clean_text(text).lower()

        if result_text in valid_results:
            raw_results.append(result_text)

    cleaned_results = []

    for result in raw_results:
        if not cleaned_results or cleaned_results[-1] != result:
            cleaned_results.append(result)

    if len(cleaned_results) >= 2:
        return cleaned_results[0], cleaned_results[1]

    if len(cleaned_results) == 1:
        only_result = cleaned_results[0]

        if only_result == "win":
            return "win", "loss"

        if only_result == "loss":
            return "loss", "win"

        if only_result in {"draw", "nc"}:
            return only_result, only_result

    return "", ""


def fetch_fights_for_event(
    event_name: str,
    event_date: str,
    event_location: str,
    event_url: str,
) -> List[EventFight]:
    """
    Scrapes all fights from a single UFCStats event page.
    """
    soup = get_soup(event_url)

    fights: List[EventFight] = []

    fight_rows = soup.select("tr.b-fight-details__table-row")

    for row in fight_rows:
        fight_url = row.get("data-link", "")

        if not fight_url:
            continue

        columns = row.find_all("td")

        fighter_1, fighter_2 = extract_fighter_names(columns)
        result_1, result_2 = extract_fighter_results(columns)

        if not fighter_1 or not fighter_2:
            continue

        winner, loser = determine_winner_and_loser(
            fighter_1=fighter_1,
            fighter_2=fighter_2,
            result_1=result_1,
            result_2=result_2,
        )

        weight_class = safe_column_text(columns, 6)
        method = safe_column_text(columns, 7)
        round_number = safe_column_text(columns, 8)
        fight_time = safe_column_text(columns, 9)

        fights.append(
            EventFight(
                event_name=event_name,
                event_date=event_date,
                event_location=event_location,
                event_url=event_url,
                fight_url=fight_url,
                fighter_1=fighter_1,
                fighter_2=fighter_2,
                result_1=result_1,
                result_2=result_2,
                winner=winner,
                loser=loser,
                weight_class=weight_class,
                method=method,
                round=round_number,
                time=fight_time,
            )
        )

    return fights


def load_completed_events(limit: Optional[int] = None) -> pd.DataFrame:
    """
    Loads completed events from the CSV created in Milestone 1.
    """
    if not COMPLETED_EVENTS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {COMPLETED_EVENTS_CSV}. "
            "Run the completed events scraper first."
        )

    events_df = pd.read_csv(COMPLETED_EVENTS_CSV)

    if limit is not None:
        events_df = events_df.head(limit)

    return events_df


def save_event_fights_csv(fights: List[EventFight]) -> None:
    """
    Saves all scraped fights to backend/data/raw/event_fights.csv.
    """
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    fight_rows = [asdict(fight) for fight in fights]
    df = pd.DataFrame(fight_rows)

    df.to_csv(EVENT_FIGHTS_CSV, index=False)


def scrape_event_fights(limit: Optional[int] = None) -> List[EventFight]:
    """
    Scrapes fights from completed UFC events.
    """
    events_df = load_completed_events(limit=limit)

    all_fights: List[EventFight] = []

    total_events = len(events_df)

    for index, event in events_df.iterrows():
        event_name = str(event["name"])
        event_date = str(event["date"])
        event_location = str(event["location"])
        event_url = str(event["url"])

        print(f"[{index + 1}/{total_events}] Scraping fights for: {event_name}")

        try:
            event_fights = fetch_fights_for_event(
                event_name=event_name,
                event_date=event_date,
                event_location=event_location,
                event_url=event_url,
            )

            print(f"    Found {len(event_fights)} fights.")

            all_fights.extend(event_fights)

        except Exception as error:
            print(f"    ERROR scraping {event_name}: {error}")

        # Small delay so we are not hammering the site.
        time.sleep(0.25)

    return all_fights


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only scrape the first N completed events. Useful for testing.",
    )

    args = parser.parse_args()

    print("Scraping UFC event fights...")

    fights = scrape_event_fights(limit=args.limit)

    if not fights:
        raise RuntimeError("No fights were scraped.")

    save_event_fights_csv(fights)

    print()
    print(f"Saved {len(fights)} fights.")
    print(f"Output file: {EVENT_FIGHTS_CSV}")

    print()
    print("Most recent 5 fights found:")
    for fight in fights[:5]:
        print(
            f"- {fight.fighter_1} vs {fight.fighter_2} | "
            f"{fight.weight_class} | {fight.method} | Winner: {fight.winner}"
        )


if __name__ == "__main__":
    main()