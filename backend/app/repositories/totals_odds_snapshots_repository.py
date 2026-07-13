from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import pandas as pd

from app.db import connection, schema
from app.db.frame_contract import normalize_frame


COLUMNS_SPEC = schema.TOTALS_ODDS_SNAPSHOT_COLUMNS
COLUMN_NAMES = [name for name, _ in COLUMNS_SPEC]
COLUMN_TYPES = dict(COLUMNS_SPEC)

# Local retrieval time is deliberately excluded: requesting the same upstream quote
# twice should not create two observations. A changed source timestamp, line, or price
# produces a new immutable snapshot.
_IDENTITY_COLUMNS = [
    "source",
    "odds_event_id",
    "fight_url",
    "fighter_1",
    "fighter_2",
    "bookmaker_key",
    "bookmaker_last_update",
    "rounds_line",
    "over_odds_american",
    "under_odds_american",
]


def _clean_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def make_snapshot_key(row: dict[str, Any]) -> str:
    identity = {name: _clean_scalar(row.get(name)) for name in _IDENTITY_COLUMNS}
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _coerce(name: str, value: Any) -> Any:
    value = _clean_scalar(value)
    if value is None:
        return None
    if COLUMN_TYPES[name] == "REAL":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return str(value)


def _row_values(row: dict[str, Any]) -> list[Any]:
    normalized = dict(row)
    normalized["snapshot_key"] = normalized.get("snapshot_key") or make_snapshot_key(row)
    return [_coerce(name, normalized.get(name)) for name in COLUMN_NAMES]


def append_snapshots(rows: list[dict[str, Any]]) -> int:
    """Insert previously unseen upstream quote versions without rewriting history."""
    if not rows:
        return 0

    columns = ", ".join(COLUMN_NAMES)
    placeholders = ", ".join(["?"] * len(COLUMN_NAMES))

    with connection.transaction() as conn:
        schema.init_db(conn)
        before = conn.total_changes
        conn.executemany(
            f"INSERT OR IGNORE INTO totals_odds_snapshots ({columns}) "
            f"VALUES ({placeholders})",
            [_row_values(row) for row in rows],
        )
        return int(conn.total_changes - before)


def read_all_df() -> pd.DataFrame:
    columns = ", ".join(COLUMN_NAMES)
    with connection.transaction() as conn:
        schema.init_db(conn)
        rows = conn.execute(
            f"SELECT {columns} FROM totals_odds_snapshots "
            "ORDER BY captured_at, fight_url, bookmaker_key, rounds_line"
        ).fetchall()

    if not rows:
        return pd.DataFrame(columns=COLUMN_NAMES)
    frame = pd.DataFrame([dict(row) for row in rows], columns=COLUMN_NAMES)
    return normalize_frame(frame, COLUMNS_SPEC)


def count() -> int:
    with connection.transaction() as conn:
        schema.init_db(conn)
        return int(
            conn.execute("SELECT COUNT(*) FROM totals_odds_snapshots").fetchone()[0]
        )
