from __future__ import annotations

import math
from typing import Any

import pandas as pd

from app.db import connection, schema

COLUMN_NAMES = [name for name, _ in schema.MODEL_RUNS_COLUMNS]
COLUMN_TYPES = dict(schema.MODEL_RUNS_COLUMNS)


def _coerce(name: str, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if COLUMN_TYPES[name] == "INTEGER":
        if isinstance(value, bool):
            return 1 if value else 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return str(value)


def record_run(run: dict[str, Any]) -> None:
    """Append one training-run record (audit log; never overwritten)."""
    columns = ", ".join(COLUMN_NAMES)
    placeholders = ", ".join(["?"] * len(COLUMN_NAMES))
    values = [_coerce(name, run.get(name)) for name in COLUMN_NAMES]

    with connection.transaction() as conn:
        schema.init_db(conn)
        conn.execute(
            f"INSERT INTO model_runs ({columns}) VALUES ({placeholders})", values
        )


def read_all_df() -> pd.DataFrame:
    """All training runs, newest first."""
    columns = ", ".join(COLUMN_NAMES)
    with connection.transaction() as conn:
        schema.init_db(conn)
        rows = conn.execute(
            f"SELECT {columns} FROM model_runs ORDER BY id DESC"
        ).fetchall()

    if not rows:
        return pd.DataFrame(columns=COLUMN_NAMES)

    return pd.DataFrame([dict(row) for row in rows], columns=COLUMN_NAMES)


def latest() -> dict[str, Any] | None:
    """The most recent training run as a dict, or None if there are no runs."""
    columns = ", ".join(COLUMN_NAMES)
    with connection.transaction() as conn:
        schema.init_db(conn)
        row = conn.execute(
            f"SELECT {columns} FROM model_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()

    return dict(row) if row is not None else None


def count() -> int:
    with connection.transaction() as conn:
        schema.init_db(conn)
        return int(conn.execute("SELECT COUNT(*) FROM model_runs").fetchone()[0])
