from __future__ import annotations

"""
Scrapes per-round fight statistics from UFCStats fight-detail pages.

The existing scraper (scrape_fight_details.py) keeps only the full-fight totals,
which throws away cardio/pace information. Each UFCStats fight page also exposes a
"Per round" breakdown in two tables (class `js-fight-table`): one with KD / strikes
/ takedowns / control, and one with the significant-strike target/position split.

This module parses those per-round tables into one row per fighter per round and
writes them to data/raw/fight_round_stats.csv. It reuses the parsing helpers from
scrape_fight_details so the number formats and fighter-name handling stay identical.

Run it standalone:
    python -m app.data.scrape_fight_round_stats              # missing fights only
    python -m app.data.scrape_fight_round_stats --rebuild    # re-scrape everything
    python -m app.data.scrape_fight_round_stats --limit 25   # test on a few fights
"""

import argparse
import re
import time
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from bs4 import BeautifulSoup

from app.data.scrape_fight_details import (
    clean_text,
    get_two_values_from_cell,
    load_event_fights,
    parse_control_time_to_seconds,
    parse_int,
    parse_landed_attempted,
)
from app.data.ufcstats_fetcher import UfcStatsSession


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
EVENT_FIGHTS_CSV = RAW_DATA_DIR / "event_fights.csv"
FIGHT_ROUND_STATS_CSV = RAW_DATA_DIR / "fight_round_stats.csv"


ROUND_HEADER_CLASS = "b-fight-details__table-row_type_head"

OUTPUT_COLUMNS = [
    "event_name",
    "event_date",
    "fight_url",
    "fighter",
    "opponent",
    "round",
    "kd",
    "sig_str_landed",
    "sig_str_attempted",
    "total_str_landed",
    "total_str_attempted",
    "td_landed",
    "td_attempted",
    "sub_att",
    "rev",
    "ctrl_seconds",
    "head_landed",
    "body_landed",
    "leg_landed",
    "distance_landed",
    "clinch_landed",
    "ground_landed",
]


def parse_round_number(text: str) -> Optional[int]:
    match = re.search(r"round\s*(\d+)", clean_text(text), flags=re.IGNORECASE)

    if not match:
        return None

    return int(match.group(1))


def find_per_round_tables(soup) -> tuple[Any, Any]:
    """
    Returns (totals_per_round_table, sig_strikes_per_round_table).

    Both are the collapsible "Per round" tables (class js-fight-table). They are
    told apart by their column headers, the same way scrape_fight_details tells the
    two summary tables apart.
    """
    totals_table = None
    sig_table = None

    for table in soup.find_all("table", class_="js-fight-table"):
        header_text = clean_text(
            " ".join(th.get_text(" ", strip=True) for th in table.find_all("th"))
        ).upper()

        is_totals = (
            "KD" in header_text
            and "TOTAL STR" in header_text
            and "CTRL" in header_text
        )
        is_sig = (
            "HEAD" in header_text
            and "BODY" in header_text
            and "LEG" in header_text
            and "DISTANCE" in header_text
        )

        if totals_table is None and is_totals:
            totals_table = table
        elif sig_table is None and is_sig:
            sig_table = table

    return totals_table, sig_table


def iter_round_data_rows(table) -> list[tuple[int, list]]:
    """
    Walks a per-round table and yields (round_number, [td cells]) for each round's
    data row. The table alternates a "Round N" header thead with a one-row data
    tbody, so we track the most recent round header as we go.
    """
    # Round number is assigned by POSITION: UFCStats lists per-round data rows in
    # order (round 1, 2, ...), so the k-th data row is round k. This is robust to
    # UFCStats' malformed table HTML, which different parsers nest differently — a
    # browser pairs each "Round N" header with its row, but BeautifulSoup on the raw
    # bytes scatters the thead/tbody structure. A data row is any <tr> with the full
    # stat columns (>= 9 <td>); header rows use <th> and are skipped automatically.
    results: list[tuple[int, list]] = []
    round_number = 0

    for row in table.find_all("tr"):
        cells = row.find_all("td", recursive=False)

        if len(cells) >= 9:
            round_number += 1
            results.append((round_number, cells))

    return results


def build_round_rows(fight_row: pd.Series, soup) -> list[dict[str, Any]]:
    totals_table, sig_table = find_per_round_tables(soup)

    if totals_table is None:
        raise ValueError("Could not find a per-round totals table on the fight page.")

    event_name = clean_text(str(fight_row.get("event_name", "")))
    event_date = clean_text(str(fight_row.get("event_date", "")))
    fight_url = clean_text(str(fight_row.get("fight_url", "")))

    # (round, fighter_index) -> row dict
    records: dict[tuple[int, int], dict[str, Any]] = {}

    for round_number, cells in iter_round_data_rows(totals_table):
        fighter_pair = get_two_values_from_cell(cells[0])
        # cells[1:] -> KD, Sig, Sig%, Total, TD, TD%, Sub, Rev, Ctrl
        values = [get_two_values_from_cell(cell) for cell in cells[1:]]

        for fighter_index in (0, 1):
            opponent_index = 1 - fighter_index

            sig_landed, sig_attempted = parse_landed_attempted(values[1][fighter_index])
            total_landed, total_attempted = parse_landed_attempted(values[3][fighter_index])
            td_landed, td_attempted = parse_landed_attempted(values[4][fighter_index])

            records[(round_number, fighter_index)] = {
                "event_name": event_name,
                "event_date": event_date,
                "fight_url": fight_url,
                "fighter": clean_text(fighter_pair[fighter_index]),
                "opponent": clean_text(fighter_pair[opponent_index]),
                "round": round_number,
                "kd": parse_int(values[0][fighter_index]),
                "sig_str_landed": sig_landed,
                "sig_str_attempted": sig_attempted,
                "total_str_landed": total_landed,
                "total_str_attempted": total_attempted,
                "td_landed": td_landed,
                "td_attempted": td_attempted,
                "sub_att": parse_int(values[6][fighter_index]),
                "rev": parse_int(values[7][fighter_index]),
                "ctrl_seconds": parse_control_time_to_seconds(values[8][fighter_index]),
                "head_landed": None,
                "body_landed": None,
                "leg_landed": None,
                "distance_landed": None,
                "clinch_landed": None,
                "ground_landed": None,
            }

    if sig_table is not None:
        for round_number, cells in iter_round_data_rows(sig_table):
            # cells[1:] -> Sig, Sig%, Head, Body, Leg, Distance, Clinch, Ground
            values = [get_two_values_from_cell(cell) for cell in cells[1:]]

            for fighter_index in (0, 1):
                record = records.get((round_number, fighter_index))

                if record is None:
                    continue

                head_landed, _ = parse_landed_attempted(values[2][fighter_index])
                body_landed, _ = parse_landed_attempted(values[3][fighter_index])
                leg_landed, _ = parse_landed_attempted(values[4][fighter_index])
                distance_landed, _ = parse_landed_attempted(values[5][fighter_index])
                clinch_landed, _ = parse_landed_attempted(values[6][fighter_index])
                ground_landed, _ = parse_landed_attempted(values[7][fighter_index])

                record.update(
                    head_landed=head_landed,
                    body_landed=body_landed,
                    leg_landed=leg_landed,
                    distance_landed=distance_landed,
                    clinch_landed=clinch_landed,
                    ground_landed=ground_landed,
                )

    if not records:
        raise ValueError("No per-round rows parsed from the fight page.")

    return [records[key] for key in sorted(records.keys())]


def read_existing_round_stats() -> pd.DataFrame:
    if not FIGHT_ROUND_STATS_CSV.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(FIGHT_ROUND_STATS_CSV)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def save_round_stats(df: pd.DataFrame) -> None:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Stable, predictable column order.
    ordered = [column for column in OUTPUT_COLUMNS if column in df.columns]
    remaining = [column for column in df.columns if column not in ordered]
    df = df[ordered + remaining]

    df.to_csv(FIGHT_ROUND_STATS_CSV, index=False)


CHECKPOINT_EVERY = 25


def _save_checkpoint(buffered_rows: list[dict[str, Any]]) -> None:
    """Merge buffered rows into the CSV on disk and dedupe. Safe to call repeatedly."""
    if not buffered_rows:
        return

    new_df = pd.DataFrame(buffered_rows)
    existing_df = read_existing_round_stats()

    combined_df = new_df if existing_df.empty else pd.concat([existing_df, new_df], ignore_index=True)

    if {"fight_url", "fighter", "round"}.issubset(combined_df.columns):
        combined_df = combined_df.drop_duplicates(
            subset=["fight_url", "fighter", "round"],
            keep="last",
        )

    save_round_stats(combined_df)


def scrape_round_stats(
    limit: Optional[int] = None,
    only_missing: bool = True,
    sleep_seconds: float = 0.1,
    checkpoint_every: int = CHECKPOINT_EVERY,
) -> dict[str, Any]:
    """
    Scrapes per-round stats and merges them into fight_round_stats.csv.

    only_missing=True   -> only scrape fights not already in the CSV (incremental).
    only_missing=False  -> re-scrape every fight (full rebuild).

    Progress is checkpointed to disk every `checkpoint_every` fights and once more
    in a finally block, so the run is fully resumable: stopping it (Ctrl+C) keeps
    everything scraped so far, and rerunning skips fights already saved. One
    Chromium browser is reused for the whole run (see PlaywrightFetcher).
    """
    fights_df = load_event_fights(limit=None)

    existing_df = read_existing_round_stats()

    if only_missing and not existing_df.empty and "fight_url" in existing_df.columns:
        already_scraped = set(existing_df["fight_url"].dropna().astype(str))
    else:
        already_scraped = set()

    pending_df = fights_df[
        ~fights_df["fight_url"].astype(str).isin(already_scraped)
    ].copy()

    if limit is not None:
        pending_df = pending_df.head(limit)

    total = len(pending_df)
    print(f"Fights already in fight_round_stats.csv: {len(already_scraped)}")
    print(f"Fights to scrape this run: {total}")

    buffered_rows: list[dict[str, Any]] = []
    scraped_count = 0
    skipped: list[dict[str, Any]] = []

    try:
        with UfcStatsSession() as fetcher:
            for scrape_number, (_, fight_row) in enumerate(pending_df.iterrows(), start=1):
                fighter_1 = clean_text(str(fight_row.get("fighter_1", "")))
                fighter_2 = clean_text(str(fight_row.get("fighter_2", "")))
                fight_url = clean_text(str(fight_row.get("fight_url", "")))

                print(f"[{scrape_number}/{total}] Round stats: {fighter_1} vs {fighter_2}")

                try:
                    soup = BeautifulSoup(fetcher.fetch(fight_url), "html.parser")
                    buffered_rows.extend(build_round_rows(fight_row, soup))
                    scraped_count += 1
                except Exception as error:
                    print(f"    SKIPPING (no per-round stats): {error}")
                    skipped.append(
                        {"fighter_1": fighter_1, "fighter_2": fighter_2, "fight_url": fight_url, "reason": str(error)}
                    )

                if scrape_number % checkpoint_every == 0:
                    _save_checkpoint(buffered_rows)
                    buffered_rows = []
                    print(f"    checkpoint saved ({scrape_number}/{total})")

                time.sleep(sleep_seconds)
    finally:
        # Always persist whatever was scraped, even on Ctrl+C or an error.
        _save_checkpoint(buffered_rows)

    total_rows = len(read_existing_round_stats())

    return {
        "fights_checked": int(total),
        "fights_scraped": int(scraped_count),
        "skipped_fight_count": int(len(skipped)),
        "skipped_fights": skipped,
        "total_round_rows": int(total_rows),
        "output_file": str(FIGHT_ROUND_STATS_CSV),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape per-round UFC fight stats.")
    parser.add_argument("--limit", type=int, default=None, help="Only scrape the first N pending fights.")
    parser.add_argument("--rebuild", action="store_true", help="Re-scrape every fight, not just missing ones.")
    args = parser.parse_args()

    print("Scraping per-round UFC fight stats...")

    result = scrape_round_stats(limit=args.limit, only_missing=not args.rebuild)

    print()
    print(f"New round rows: {result['new_round_rows']}")
    print(f"Total round rows: {result['total_round_rows']}")
    print(f"Skipped fights: {result['skipped_fight_count']}")
    print(f"Output file: {result['output_file']}")


if __name__ == "__main__":
    main()
