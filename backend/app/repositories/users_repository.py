from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from app.db import connection, schema

_FULL_COLUMNS = "id, username, password_hash, role, created_at"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_user(username: str, password_hash: str, role: str = "user") -> dict[str, Any]:
    """Insert a user. Raises ValueError if the username is already taken."""
    with connection.transaction() as conn:
        schema.init_db(conn)
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) "
                "VALUES (?, ?, ?, ?)",
                (username, password_hash, role, _now()),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("Username is already taken.") from error

        row = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM users WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return dict(row)


def get_by_username(username: str) -> dict[str, Any] | None:
    with connection.transaction() as conn:
        schema.init_db(conn)
        row = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM users WHERE username = ?", (username,)
        ).fetchone()
    return dict(row) if row is not None else None


def get_by_id(user_id: Any) -> dict[str, Any] | None:
    with connection.transaction() as conn:
        schema.init_db(conn)
        row = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row is not None else None


def set_role(user_id: Any, role: str) -> bool:
    with connection.transaction() as conn:
        schema.init_db(conn)
        cursor = conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        return cursor.rowcount > 0


def list_users() -> list[dict[str, Any]]:
    with connection.transaction() as conn:
        schema.init_db(conn)
        rows = conn.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def count() -> int:
    with connection.transaction() as conn:
        schema.init_db(conn)
        return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])


def count_admins() -> int:
    with connection.transaction() as conn:
        schema.init_db(conn)
        return int(
            conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
        )


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    """Strip the password hash for anything client-facing."""
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "created_at": user.get("created_at"),
    }
