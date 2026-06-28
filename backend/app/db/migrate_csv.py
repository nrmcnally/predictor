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
from app.repositories import odds_track_repository, saved_predictions_repository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
FIGHT_ODDS_TRACK_CSV = PROCESSED_DATA_DIR / "fight_odds_track.csv"
SAVED_CARD_PREDICTIONS_CSV = PROCESSED_DATA_DIR / "saved_card_predictions.csv"


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


def main() -> None:
    track = migrate_fight_odds_track()
    saved = migrate_saved_card_predictions()
    print(
        f"Imported {track} fight_odds_track row(s) and "
        f"{saved} saved_card_predictions row(s) into {connection.get_db_path()}"
    )


if __name__ == "__main__":
    main()
