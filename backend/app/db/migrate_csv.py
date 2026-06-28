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
from app.repositories import odds_track_repository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
FIGHT_ODDS_TRACK_CSV = PROCESSED_DATA_DIR / "fight_odds_track.csv"


def migrate_fight_odds_track() -> int:
    if not FIGHT_ODDS_TRACK_CSV.exists():
        return 0
    try:
        df = pd.read_csv(FIGHT_ODDS_TRACK_CSV)
    except pd.errors.EmptyDataError:
        return 0
    return odds_track_repository.import_rows(df.to_dict(orient="records"))


def main() -> None:
    count = migrate_fight_odds_track()
    print(f"Imported {count} fight_odds_track row(s) into {connection.get_db_path()}")


if __name__ == "__main__":
    main()
