from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from app.db import connection, schema

_FULL_COLUMNS = "id, email, display_name, password_hash, role, is_public, created_at"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_user(
    email: str,
    password_hash: str,
    display_name: str | None = None,
    role: str = "user",
) -> dict[str, Any]:
    """Insert a user. Raises ValueError if the email is already registered."""
    with connection.transaction() as conn:
        schema.init_db(conn)
        try:
            cursor = conn.execute(
                "INSERT INTO users (email, display_name, password_hash, role, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (email, display_name, password_hash, role, _now()),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("An account with that email already exists.") from error

        row = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM users WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return dict(row)


def get_by_email(email: str) -> dict[str, Any] | None:
    with connection.transaction() as conn:
        schema.init_db(conn)
        row = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM users WHERE email = ?", (email,)
        ).fetchone()
    return dict(row) if row is not None else None


def get_by_id(user_id: Any) -> dict[str, Any] | None:
    with connection.transaction() as conn:
        schema.init_db(conn)
        row = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row is not None else None


def get_by_display_name(display_name: str) -> dict[str, Any] | None:
    """Case-insensitive lookup by the unique display name / username."""
    with connection.transaction() as conn:
        schema.init_db(conn)
        row = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM users WHERE display_name = ? COLLATE NOCASE",
            (display_name,),
        ).fetchone()
    return dict(row) if row is not None else None


def set_role(user_id: Any, role: str) -> bool:
    with connection.transaction() as conn:
        schema.init_db(conn)
        cursor = conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        return cursor.rowcount > 0


def update_password(user_id: Any, password_hash: str) -> bool:
    with connection.transaction() as conn:
        schema.init_db(conn)
        cursor = conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
        )
        return cursor.rowcount > 0


def set_visibility(user_id: Any, is_public: bool) -> bool:
    with connection.transaction() as conn:
        schema.init_db(conn)
        cursor = conn.execute(
            "UPDATE users SET is_public = ? WHERE id = ?", (1 if is_public else 0, user_id)
        )
        return cursor.rowcount > 0


def update_profile(user_id: Any, email: str, display_name: str | None) -> bool:
    """Update a user's email + display name. Raises ValueError on a duplicate email."""
    with connection.transaction() as conn:
        schema.init_db(conn)
        try:
            cursor = conn.execute(
                "UPDATE users SET email = ?, display_name = ? WHERE id = ?",
                (email, display_name, user_id),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("That email is already in use.") from error
        return cursor.rowcount > 0


def list_users() -> list[dict[str, Any]]:
    with connection.transaction() as conn:
        schema.init_db(conn)
        rows = conn.execute(
            "SELECT id, email, display_name, role, created_at FROM users ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def list_public_users() -> list[dict[str, Any]]:
    """Users who opted into public profiles/leaderboards (is_public = 1)."""
    with connection.transaction() as conn:
        schema.init_db(conn)
        rows = conn.execute(
            "SELECT id, display_name, role, created_at FROM users "
            "WHERE is_public = 1 ORDER BY id"
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
        "email": user["email"],
        "display_name": user.get("display_name"),
        "role": user["role"],
        "is_public": bool(user.get("is_public", 0)),
        "created_at": user.get("created_at"),
    }
