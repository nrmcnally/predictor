from __future__ import annotations

"""One-time / idempotent import of legacy transactional CSVs into the SQLite layer.

Run:  python -m app.db.migrate_csv

Re-runnable: rows are upserted by primary key, so importing twice is a no-op beyond
refreshing values. As more datasets move to SQLite (saved predictions, results,
future cards), add their importers here.
"""

from pathlib import Path

import pandas as pd

from app.db import connection
from app.repositories import (
    event_fights_repository,
    future_cards_repository,
    future_fight_odds_repository,
    odds_track_repository,
    saved_model_predictions_repository,
    saved_predictions_repository,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
FIGHT_ODDS_TRACK_CSV = PROCESSED_DATA_DIR / "fight_odds_track.csv"
SAVED_CARD_PREDICTIONS_CSV = PROCESSED_DATA_DIR / "saved_card_predictions.csv"
SAVED_MODEL_PREDICTIONS_CSV = PROCESSED_DATA_DIR / "saved_model_predictions.csv"
EVENT_FIGHTS_CSV = RAW_DATA_DIR / "event_fights.csv"
UPCOMING_EVENTS_CSV = RAW_DATA_DIR / "upcoming_events.csv"
UPCOMING_FIGHTS_CSV = RAW_DATA_DIR / "upcoming_fights.csv"
FUTURE_FIGHT_ODDS_CSV = PROCESSED_DATA_DIR / "future_fight_odds.csv"


def _import_csv(path, importer):
    if not path.exists():
        return 0
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return 0
    return importer(df.to_dict(orient="records"))


def migrate_fight_odds_track() -> int:
    if not FIGHT_ODDS_TRACK_CSV.exists():
        return 0
    try:
        df = pd.read_csv(FIGHT_ODDS_TRACK_CSV)
    except pd.errors.EmptyDataError:
        return 0
    return odds_track_repository.import_rows(df.to_dict(orient="records"))


def migrate_saved_card_predictions() -> int:
    if not SAVED_CARD_PREDICTIONS_CSV.exists():
        return 0
    try:
        df = pd.read_csv(SAVED_CARD_PREDICTIONS_CSV)
    except pd.errors.EmptyDataError:
        return 0
    return saved_predictions_repository.import_rows(df.to_dict(orient="records"))


def migrate_saved_model_predictions() -> int:
    if not SAVED_MODEL_PREDICTIONS_CSV.exists():
        return 0
    try:
        df = pd.read_csv(SAVED_MODEL_PREDICTIONS_CSV)
    except pd.errors.EmptyDataError:
        return 0
    return saved_model_predictions_repository.import_rows(df.to_dict(orient="records"))


def migrate_event_fights() -> int:
    if not EVENT_FIGHTS_CSV.exists():
        return 0
    try:
        df = pd.read_csv(EVENT_FIGHTS_CSV)
    except pd.errors.EmptyDataError:
        return 0
    return event_fights_repository.import_rows(df.to_dict(orient="records"))


def migrate_future_cards() -> tuple[int, int]:
    events = _import_csv(UPCOMING_EVENTS_CSV, future_cards_repository.replace_upcoming_events)
    fights = _import_csv(UPCOMING_FIGHTS_CSV, future_cards_repository.replace_upcoming_fights)
    return events, fights


def migrate_future_fight_odds() -> int:
    return _import_csv(FUTURE_FIGHT_ODDS_CSV, future_fight_odds_repository.replace_all)


def main() -> None:
    track = migrate_fight_odds_track()
    saved = migrate_saved_card_predictions()
    saved_model = migrate_saved_model_predictions()
    results = migrate_event_fights()
    up_events, up_fights = migrate_future_cards()
    future_odds = migrate_future_fight_odds()
    print(
        f"Imported {track} fight_odds_track, {saved} saved_card_predictions, "
        f"{saved_model} saved_model_predictions, {results} event_fights, "
        f"{up_events} upcoming_events, {up_fights} upcoming_fights, "
        f"{future_odds} future_fight_odds row(s) into {connection.get_db_path()}"
    )


if __name__ == "__main__":
    main()
