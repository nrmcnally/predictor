from __future__ import annotations

import math
from typing import Any

import pandas as pd

from app.db import connection, schema

COLUMN_NAMES = [name for name, _ in schema.SAVED_CARD_COLUMNS]
COLUMN_TYPES = dict(schema.SAVED_CARD_COLUMNS)


def _coerce(name: str, value: Any) -> Any:
    """Coerce a raw value (Python native or pandas/numpy from a CSV) to the column type."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None

    sql_type = COLUMN_TYPES[name]

    if sql_type == "REAL":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    if sql_type == "INTEGER":
        if isinstance(value, bool):
            return 1 if value else 0
        text = str(value).strip().lower()
        if text in {"true", "yes", "y"}:
            return 1
        if text in {"false", "no", "n"}:
            return 0
        if text == "":
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    # TEXT — keep empty strings as-is (consumers distinguish "" from NULL).
    return str(value)


def _row_values(row: dict[str, Any]) -> list[Any]:
    return [_coerce(name, row.get(name)) for name in COLUMN_NAMES]


def read_all_df() -> pd.DataFrame:
    """All saved card predictions as a DataFrame matching the legacy CSV columns."""
    columns = ", ".join(COLUMN_NAMES)
    with connection.transaction() as conn:
        schema.init_db(conn)
        rows = conn.execute(f"SELECT {columns} FROM saved_card_predictions").fetchall()

    if not rows:
        return pd.DataFrame(columns=COLUMN_NAMES)

    return pd.DataFrame([dict(row) for row in rows], columns=COLUMN_NAMES)


def replace_card(event_id: str, rows: list[dict[str, Any]]) -> int:
    """Atomically replace all saved predictions for one event: delete the event's rows,
    insert the new ones, in a single transaction (one latest snapshot per card)."""
    columns = ", ".join(COLUMN_NAMES)
    placeholders = ", ".join(["?"] * len(COLUMN_NAMES))

    with connection.transaction() as conn:
        schema.init_db(conn)
        conn.execute(
            "DELETE FROM saved_card_predictions WHERE event_id = ?", (str(event_id),)
        )
        for row in rows:
            conn.execute(
                f"INSERT INTO saved_card_predictions ({columns}) VALUES ({placeholders})",
                _row_values(row),
            )
    return len(rows)


def import_rows(rows: list[dict[str, Any]]) -> int:
    """Full replace of the table from a list of rows (used for the one-time CSV import)."""
    columns = ", ".join(COLUMN_NAMES)
    placeholders = ", ".join(["?"] * len(COLUMN_NAMES))

    with connection.transaction() as conn:
        schema.init_db(conn)
        conn.execute("DELETE FROM saved_card_predictions")
        for row in rows:
            conn.execute(
                f"INSERT INTO saved_card_predictions ({columns}) VALUES ({placeholders})",
                _row_values(row),
            )
    return len(rows)


def count() -> int:
    with connection.transaction() as conn:
        schema.init_db(conn)
        return int(conn.execute("SELECT COUNT(*) FROM saved_card_predictions").fetchone()[0])
