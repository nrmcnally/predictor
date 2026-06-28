from __future__ import annotations

import math
from typing import Any

import pandas as pd

from app.db import connection, schema

COLUMN_NAMES = [name for name, _ in schema.EVENT_FIGHTS_COLUMNS]
COLUMN_TYPES = dict(schema.EVENT_FIGHTS_COLUMNS)


def _coerce(name: str, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None

    if COLUMN_TYPES[name] == "INTEGER":
        if isinstance(value, bool):
            return int(value)
        text = str(value).strip()
        if text == "":
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    # TEXT — treat empty as NULL to mirror read_csv (empty cell -> NaN), so every
    # consumer sees identical values whether reading from the DB or the old CSV.
    text = str(value)
    return text if text != "" else None


def _row_values(row: dict[str, Any]) -> list[Any]:
    return [_coerce(name, row.get(name)) for name in COLUMN_NAMES]


def read_all_df() -> pd.DataFrame:
    columns = ", ".join(COLUMN_NAMES)
    with connection.transaction() as conn:
        schema.init_db(conn)
        rows = conn.execute(f"SELECT {columns} FROM event_fights").fetchall()

    if not rows:
        return pd.DataFrame(columns=COLUMN_NAMES)

    return pd.DataFrame([dict(row) for row in rows], columns=COLUMN_NAMES)


def replace_all(rows: list[dict[str, Any]]) -> int:
    """Full overwrite of the results table (used by the full scrape and CSV import)."""
    columns = ", ".join(COLUMN_NAMES)
    placeholders = ", ".join(["?"] * len(COLUMN_NAMES))

    with connection.transaction() as conn:
        schema.init_db(conn)
        conn.execute("DELETE FROM event_fights")
        for row in rows:
            conn.execute(
                f"INSERT INTO event_fights ({columns}) VALUES ({placeholders})",
                _row_values(row),
            )
    return len(rows)


# Migration import is just a full replace.
import_rows = replace_all


def upsert_fights(rows: list[dict[str, Any]]) -> int:
    """Insert new fights and overwrite existing ones by fight_url (keep last) — the
    incremental-merge semantics, done atomically per fight."""
    columns = ", ".join(COLUMN_NAMES)
    placeholders = ", ".join(["?"] * len(COLUMN_NAMES))
    updates = ", ".join(
        f"{name} = excluded.{name}" for name in COLUMN_NAMES if name != "fight_url"
    )

    with connection.transaction() as conn:
        schema.init_db(conn)
        for row in rows:
            conn.execute(
                f"INSERT INTO event_fights ({columns}) VALUES ({placeholders}) "
                f"ON CONFLICT(fight_url) DO UPDATE SET {updates}",
                _row_values(row),
            )
    return len(rows)


def count() -> int:
    with connection.transaction() as conn:
        schema.init_db(conn)
        return int(conn.execute("SELECT COUNT(*) FROM event_fights").fetchone()[0])
