from __future__ import annotations

from datetime import datetime
from typing import Any

from app.db import connection, schema

# Tiny key/value store for runtime-tunable switches (admin-controlled, no redeploy).


def get(key: str) -> str | None:
    with connection.transaction() as conn:
        schema.init_db(conn)
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
    return row[0] if row is not None else None


def set(key: str, value: Any) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with connection.transaction() as conn:
        schema.init_db(conn)
        conn.execute(
            "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at",
            (key, str(value), now),
        )
