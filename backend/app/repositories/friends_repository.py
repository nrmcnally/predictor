from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from app.db import connection, schema

# Mutual-accept friendships: one directed row per pair (requester -> addressee),
# status 'pending' until the addressee accepts. A UNIQUE(requester_id, addressee_id)
# index keeps it to one row per direction.

_FULL_COLUMNS = "id, requester_id, addressee_id, status, created_at, updated_at"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def get_by_id(friendship_id: Any) -> dict[str, Any] | None:
    with connection.transaction() as conn:
        schema.init_db(conn)
        row = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM friendships WHERE id = ?", (friendship_id,)
        ).fetchone()
    return dict(row) if row is not None else None


def get_pair(user_a: Any, user_b: Any) -> dict[str, Any] | None:
    """The friendship row joining two users in either direction, or None."""
    with connection.transaction() as conn:
        schema.init_db(conn)
        row = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM friendships "
            "WHERE (requester_id = ? AND addressee_id = ?) "
            "OR (requester_id = ? AND addressee_id = ?)",
            (user_a, user_b, user_b, user_a),
        ).fetchone()
    return dict(row) if row is not None else None


def create_request(requester_id: Any, addressee_id: Any) -> dict[str, Any]:
    """Insert a pending request. Raises ValueError if one already exists for the pair."""
    now = _now()
    with connection.transaction() as conn:
        schema.init_db(conn)
        try:
            cursor = conn.execute(
                "INSERT INTO friendships (requester_id, addressee_id, status, "
                "created_at, updated_at) VALUES (?, ?, 'pending', ?, ?)",
                (requester_id, addressee_id, now, now),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("A request already exists for that pair.") from error
        row = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM friendships WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return dict(row)


def set_status(friendship_id: Any, status: str) -> bool:
    with connection.transaction() as conn:
        schema.init_db(conn)
        cursor = conn.execute(
            "UPDATE friendships SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), friendship_id),
        )
        return cursor.rowcount > 0


def delete(friendship_id: Any) -> bool:
    with connection.transaction() as conn:
        schema.init_db(conn)
        cursor = conn.execute("DELETE FROM friendships WHERE id = ?", (friendship_id,))
        return cursor.rowcount > 0


def list_for_user(user_id: Any) -> list[dict[str, Any]]:
    """All friendship rows the user is part of (either side), for building the
    friends / incoming / outgoing lists."""
    with connection.transaction() as conn:
        schema.init_db(conn)
        rows = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM friendships "
            "WHERE requester_id = ? OR addressee_id = ? ORDER BY id",
            (user_id, user_id),
        ).fetchall()
    return [dict(row) for row in rows]


def list_friend_ids(user_id: Any) -> list[int]:
    """Ids of the user's accepted friends."""
    friends = []
    for row in list_for_user(user_id):
        if row["status"] != "accepted":
            continue
        other = row["addressee_id"] if row["requester_id"] == user_id else row["requester_id"]
        friends.append(int(other))
    return friends
