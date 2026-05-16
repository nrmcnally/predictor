from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
EVENT_FIGHTS_CSV = RAW_DATA_DIR / "event_fights.csv"
FIGHT_STATS_CSV = RAW_DATA_DIR / "fight_stats.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 UFC predictor learning project "
        "(contact: local-development)"
    )
}


@dataclass
class FighterFightStats:
    event_name: str
    event_date: str
    event_location: str
    fight_url: str

    fighter: str
    opponent: str
    result: str
    is_winner: int

    weight_class: str
    method: str
    round: str
    time: str

    kd: Optional[int]

    sig_str_landed: Optional[int]
    sig_str_attempted: Optional[int]
    sig_str_pct: Optional[float]

    total_str_landed: Optional[int]
    total_str_attempted: Optional[int]

    td_landed: Optional[int]
    td_attempted: Optional[int]
    td_pct: Optional[float]

    sub_att: Optional[int]
    rev: Optional[int]
    ctrl_seconds: Optional[int]

    head_landed: Optional[int]
    head_attempted: Optional[int]

    body_landed: Optional[int]
    body_attempted: Optional[int]

    leg_landed: Optional[int]
    leg_attempted: Optional[int]

    distance_landed: Optional[int]
    distance_attempted: Optional[int]

    clinch_landed: Optional[int]
    clinch_attempted: Optional[int]

    ground_landed: Optional[int]
    ground_attempted: Optional[int]


def clean_text(value: str) -> str:
    return " ".join(str(value).split())


def get_soup(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def parse_int(value: str) -> Optional[int]:
    value = clean_text(value)

    if value in {"", "--", "---"}:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def parse_percent(value: str) -> Optional[float]:
    value = clean_text(value).replace("%", "")

    if value in {"", "--", "---"}:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def parse_landed_attempted(value: str) -> tuple[Optional[int], Optional[int]]:
    """
    Parses values like:
        '12 of 30'

    Returns:
        landed, attempted
    """
    value = clean_text(value).lower()

    if value in {"", "--", "---"}:
        return None, None

    if " of " not in value:
        return None, None

    left, right = value.split(" of ", 1)

    return parse_int(left), parse_int(right)


def parse_control_time_to_seconds(value: str) -> Optional[int]:
    """
    Parses control time like:
        '2:31'

    Returns total seconds.
    """
    value = clean_text(value)

    if value in {"", "--", "---"}:
        return None

    if ":" not in value:
        return None

    minutes_text, seconds_text = value.split(":", 1)

    minutes = parse_int(minutes_text)
    seconds = parse_int(seconds_text)

    if minutes is None or seconds is None:
        return None

    return minutes * 60 + seconds


def get_two_values_from_cell(cell) -> tuple[str, str]:
    """
    UFCStats stat cells usually contain two <p> tags:
        first fighter's value
        second fighter's value
    """
    paragraphs = cell.find_all("p")

    values = [
        clean_text(paragraph.get_text(" ", strip=True))
        for paragraph in paragraphs
        if clean_text(paragraph.get_text(" ", strip=True))
    ]

    if len(values) >= 2:
        return values[0], values[1]

    if len(values) == 1:
        return values[0], ""

    text_chunks = [
        clean_text(text)
        for text in cell.stripped_strings
        if clean_text(text)
    ]

    if len(text_chunks) >= 2:
        return text_chunks[0], text_chunks[1]

    if len(text_chunks) == 1:
        return text_chunks[0], ""

    return "", ""


def extract_fighters_from_stats_row(row) -> tuple[str, str]:
    columns = get_row_columns(row)

    if not columns:
        return "", ""

    fighter_column = columns[0]

    fighter_links = fighter_column.find_all("a")

    fighter_names = [
        clean_text(link.get_text(" ", strip=True))
        for link in fighter_links
        if clean_text(link.get_text(" ", strip=True))
    ]

    if len(fighter_names) >= 2:
        return fighter_names[0], fighter_names[1]

    paragraphs = fighter_column.find_all("p")

    fallback_names = [
        clean_text(paragraph.get_text(" ", strip=True))
        for paragraph in paragraphs
        if clean_text(paragraph.get_text(" ", strip=True))
    ]

    if len(fallback_names) >= 2:
        return fallback_names[0], fallback_names[1]

    return "", ""


def find_stats_rows(soup: BeautifulSoup):
    """
    Finds the full-fight totals row and the full-fight significant-strikes row.

    We do NOT want to just grab the first two fighter rows on the page,
    because that can accidentally grab:
        1. totals table summary row
        2. totals table round 1 row

    Instead, we identify the correct tables by their headers.
    """
    totals_row = None
    sig_strikes_row = None

    tables = soup.find_all("table")

    for table in tables:
        header_text = clean_text(
            " ".join(
                header.get_text(" ", strip=True)
                for header in table.find_all(["th"])
            )
        ).upper()

        candidate_row = find_first_fighter_stats_row(table)

        if candidate_row is None:
            continue

        is_totals_table = (
            "KD" in header_text
            and "TOTAL STR" in header_text
            and "TD" in header_text
            and "CTRL" in header_text
        )

        is_sig_strikes_table = (
            "HEAD" in header_text
            and "BODY" in header_text
            and "LEG" in header_text
            and "DISTANCE" in header_text
            and "CLINCH" in header_text
            and "GROUND" in header_text
        )

        if totals_row is None and is_totals_table:
            totals_row = candidate_row

        elif sig_strikes_row is None and is_sig_strikes_table:
            sig_strikes_row = candidate_row

    if totals_row is None or sig_strikes_row is None:
        raise ValueError("Could not find both totals and significant-strikes tables.")

    return totals_row, sig_strikes_row

def values_from_row(row) -> list[tuple[str, str]]:
    columns = get_row_columns(row)

    values = []

    for cell in columns[1:]:
        values.append(get_two_values_from_cell(cell))

    return values


def value_for_fighter(values: list[tuple[str, str]], stat_index: int, fighter_index: int) -> str:
    """
    fighter_index:
        0 = first fighter in UFCStats row
        1 = second fighter in UFCStats row
    """
    if stat_index >= len(values):
        return ""

    pair = values[stat_index]

    if fighter_index == 0:
        return pair[0]

    return pair[1]


def build_fighter_stat_rows(fight_row: pd.Series, soup: BeautifulSoup) -> list[FighterFightStats]:
    totals_row, sig_strikes_row = find_stats_rows(soup)

    if totals_row is None or sig_strikes_row is None:
        raise ValueError("Could not find both stats tables on fight detail page.")

    parsed_fighter_1, parsed_fighter_2 = extract_fighters_from_stats_row(totals_row)

    fighter_1 = clean_text(parsed_fighter_1) or clean_text(str(fight_row["fighter_1"]))
    fighter_2 = clean_text(parsed_fighter_2) or clean_text(str(fight_row["fighter_2"]))

    winner = clean_text(str(fight_row.get("winner", "")))
    loser = clean_text(str(fight_row.get("loser", "")))

    totals_values = values_from_row(totals_row)
    sig_values = values_from_row(sig_strikes_row)

    rows: list[FighterFightStats] = []

    fighters = [
        (fighter_1, fighter_2, 0),
        (fighter_2, fighter_1, 1),
    ]

    for fighter, opponent, fighter_index in fighters:
        if winner and fighter == winner:
            result = "win"
            is_winner = 1
        elif loser and fighter == loser:
            result = "loss"
            is_winner = 0
        else:
            result = ""
            is_winner = 0

        # Totals table indexes:
        # 0 KD
        # 1 SIG. STR.
        # 2 SIG. STR. %
        # 3 TOTAL STR.
        # 4 TD
        # 5 TD %
        # 6 SUB. ATT
        # 7 REV.
        # 8 CTRL
        kd_text = value_for_fighter(totals_values, 0, fighter_index)
        sig_str_text = value_for_fighter(totals_values, 1, fighter_index)
        sig_str_pct_text = value_for_fighter(totals_values, 2, fighter_index)
        total_str_text = value_for_fighter(totals_values, 3, fighter_index)
        td_text = value_for_fighter(totals_values, 4, fighter_index)
        td_pct_text = value_for_fighter(totals_values, 5, fighter_index)
        sub_att_text = value_for_fighter(totals_values, 6, fighter_index)
        rev_text = value_for_fighter(totals_values, 7, fighter_index)
        ctrl_text = value_for_fighter(totals_values, 8, fighter_index)

        sig_str_landed, sig_str_attempted = parse_landed_attempted(sig_str_text)
        total_str_landed, total_str_attempted = parse_landed_attempted(total_str_text)
        td_landed, td_attempted = parse_landed_attempted(td_text)

        # Significant strikes table indexes:
        # 0 SIG. STR.
        # 1 SIG. STR. %
        # 2 HEAD
        # 3 BODY
        # 4 LEG
        # 5 DISTANCE
        # 6 CLINCH
        # 7 GROUND
        head_text = value_for_fighter(sig_values, 2, fighter_index)
        body_text = value_for_fighter(sig_values, 3, fighter_index)
        leg_text = value_for_fighter(sig_values, 4, fighter_index)
        distance_text = value_for_fighter(sig_values, 5, fighter_index)
        clinch_text = value_for_fighter(sig_values, 6, fighter_index)
        ground_text = value_for_fighter(sig_values, 7, fighter_index)

        head_landed, head_attempted = parse_landed_attempted(head_text)
        body_landed, body_attempted = parse_landed_attempted(body_text)
        leg_landed, leg_attempted = parse_landed_attempted(leg_text)
        distance_landed, distance_attempted = parse_landed_attempted(distance_text)
        clinch_landed, clinch_attempted = parse_landed_attempted(clinch_text)
        ground_landed, ground_attempted = parse_landed_attempted(ground_text)

        rows.append(
            FighterFightStats(
                event_name=clean_text(str(fight_row["event_name"])),
                event_date=clean_text(str(fight_row["event_date"])),
                event_location=clean_text(str(fight_row["event_location"])),
                fight_url=clean_text(str(fight_row["fight_url"])),

                fighter=fighter,
                opponent=opponent,
                result=result,
                is_winner=is_winner,

                weight_class=clean_text(str(fight_row["weight_class"])),
                method=clean_text(str(fight_row["method"])),
                round=clean_text(str(fight_row["round"])),
                time=clean_text(str(fight_row["time"])),

                kd=parse_int(kd_text),

                sig_str_landed=sig_str_landed,
                sig_str_attempted=sig_str_attempted,
                sig_str_pct=parse_percent(sig_str_pct_text),

                total_str_landed=total_str_landed,
                total_str_attempted=total_str_attempted,

                td_landed=td_landed,
                td_attempted=td_attempted,
                td_pct=parse_percent(td_pct_text),

                sub_att=parse_int(sub_att_text),
                rev=parse_int(rev_text),
                ctrl_seconds=parse_control_time_to_seconds(ctrl_text),

                head_landed=head_landed,
                head_attempted=head_attempted,

                body_landed=body_landed,
                body_attempted=body_attempted,

                leg_landed=leg_landed,
                leg_attempted=leg_attempted,

                distance_landed=distance_landed,
                distance_attempted=distance_attempted,

                clinch_landed=clinch_landed,
                clinch_attempted=clinch_attempted,

                ground_landed=ground_landed,
                ground_attempted=ground_attempted,
            )
        )

    return rows


def load_event_fights(limit: Optional[int] = None) -> pd.DataFrame:
    if not EVENT_FIGHTS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {EVENT_FIGHTS_CSV}. "
            "Run scrape_event_fights.py first."
        )

    fights_df = pd.read_csv(EVENT_FIGHTS_CSV)

    # For the model, we only want fights with a clear winner/loser.
    # Draws and no contests are not useful for basic winner prediction.
    fights_df = fights_df[
        fights_df["winner"].notna()
        & fights_df["loser"].notna()
        & (fights_df["winner"].astype(str).str.strip() != "")
        & (fights_df["loser"].astype(str).str.strip() != "")
    ].copy()

    if limit is not None:
        fights_df = fights_df.head(limit)

    return fights_df


def scrape_fight_stats(limit: Optional[int] = None) -> list[FighterFightStats]:
    fights_df = load_event_fights(limit=limit)

    all_rows: list[FighterFightStats] = []

    total_fights = len(fights_df)

    for index, fight_row in fights_df.iterrows():
        fight_url = clean_text(str(fight_row["fight_url"]))
        fighter_1 = clean_text(str(fight_row["fighter_1"]))
        fighter_2 = clean_text(str(fight_row["fighter_2"]))

        print(f"[{len(all_rows) // 2 + 1}/{total_fights}] Scraping: {fighter_1} vs {fighter_2}")

        try:
            soup = get_soup(fight_url)
            fighter_rows = build_fighter_stat_rows(fight_row, soup)
            all_rows.extend(fighter_rows)

        except Exception as error:
            print(f"    ERROR scraping fight: {error}")

        time.sleep(0.25)

    return all_rows


def save_fight_stats_csv(rows: list[FighterFightStats]) -> None:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame([asdict(row) for row in rows])
    df.to_csv(FIGHT_STATS_CSV, index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only scrape the first N fights. Useful for testing.",
    )

    args = parser.parse_args()

    print("Scraping UFC fight details...")

    rows = scrape_fight_stats(limit=args.limit)

    if not rows:
        raise RuntimeError("No fight stats were scraped.")

    save_fight_stats_csv(rows)

    print()
    print(f"Saved {len(rows)} fighter-fight stat rows.")
    print(f"Output file: {FIGHT_STATS_CSV}")

    print()
    print("Most recent rows:")
    for row in rows[:6]:
        print(
            f"- {row.fighter} vs {row.opponent} | "
            f"{row.result} | SIG: {row.sig_str_landed}/{row.sig_str_attempted} | "
            f"TD: {row.td_landed}/{row.td_attempted}"
        )


def get_row_columns(row) -> list:
    """
    Gets only the direct table cells for a row.

    This helps prevent accidentally grabbing nested cells or nearby table data.
    """
    columns = row.find_all("td", recursive=False)

    if columns:
        return columns

    return row.find_all("td")

def find_first_fighter_stats_row(table):
    """
    Finds the first real fighter stats row inside a table.

    UFCStats tables may include summary rows and round-by-round rows.
    For now, we want the first real fighter row, which is usually the
    full-fight summary row.
    """
    rows = table.select("tr.b-fight-details__table-row")

    for row in rows:
        columns = get_row_columns(row)

        if len(columns) < 8:
            continue

        fighter_1, fighter_2 = extract_fighters_from_stats_row(row)

        if fighter_1 and fighter_2:
            return row

    return None

if __name__ == "__main__":
    main()