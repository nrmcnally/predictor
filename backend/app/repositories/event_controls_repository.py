from __future__ import annotations

from datetime import datetime
from typing import Any

from app.db import connection, schema

_FULL_COLUMNS = (
    "event_id, event_name, event_date, event_url, event_start_at_utc, "
    "lock_mode, updated_by, updated_at"
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def get(event_id: Any) -> dict[str, Any] | None:
    with connection.transaction() as conn:
        schema.init_db(conn)
        row = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM event_controls WHERE event_id = ?",
            (str(event_id),),
        ).fetchone()
    return dict(row) if row is not None else None


def upsert(
    event: dict[str, Any],
    *,
    event_start_at_utc: str | None,
    lock_mode: str,
    updated_by: Any | None,
) -> dict[str, Any]:
    event_id = str(event.get("event_id") or "").strip()
    now = _now()

    with connection.transaction() as conn:
        schema.init_db(conn)
        conn.execute(
            """
            INSERT INTO event_controls (
                event_id, event_name, event_date, event_url, event_start_at_utc,
                lock_mode, updated_by, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                event_name = excluded.event_name,
                event_date = excluded.event_date,
                event_url = excluded.event_url,
                event_start_at_utc = excluded.event_start_at_utc,
                lock_mode = excluded.lock_mode,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at
            """,
            (
                event_id,
                event.get("event_name"),
                event.get("event_date"),
                event.get("event_url"),
                event_start_at_utc,
                lock_mode,
                updated_by,
                now,
            ),
        )
        row = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM event_controls WHERE event_id = ?",
            (event_id,),
        ).fetchone()

    return dict(row)
