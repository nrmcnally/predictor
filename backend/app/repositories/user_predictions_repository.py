from __future__ import annotations

from datetime import datetime
from typing import Any

from app.db import connection, schema

# Per-account winner picks on upcoming fights (Phase 6). One pick per user per fight
# (UNIQUE(user_id, fight_url)); snapshotted fighters let scoring detect card changes.

_FULL_COLUMNS = (
    "id, user_id, fight_url, event_id, event_name, event_url, event_date, "
    "fighter_1, fighter_2, weight_class, picked_fighter, picked_method, status, "
    "result_correct, method_correct, scored_at, created_at, updated_at"
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def upsert(
    user_id: Any,
    fight: dict[str, Any],
    picked_fighter: str,
    picked_method: str | None,
) -> dict[str, Any]:
    """Insert or update this user's pick for ``fight`` (a current upcoming-fight row).
    Re-picking refreshes the fighter snapshot + pick and resets status to ``open``."""
    fight_url = fight["fight_url"]
    now = _now()
    with connection.transaction() as conn:
        schema.init_db(conn)
        existing = conn.execute(
            "SELECT id FROM user_predictions WHERE user_id = ? AND fight_url = ?",
            (user_id, fight_url),
        ).fetchone()

        if existing is not None:
            conn.execute(
                "UPDATE user_predictions SET "
                "event_id = ?, event_name = ?, event_url = ?, event_date = ?, "
                "fighter_1 = ?, fighter_2 = ?, weight_class = ?, "
                "picked_fighter = ?, picked_method = ?, status = 'open', updated_at = ? "
                "WHERE id = ?",
                (
                    fight.get("event_id"),
                    fight.get("event_name"),
                    fight.get("event_url"),
                    fight.get("event_date"),
                    fight.get("fighter_1"),
                    fight.get("fighter_2"),
                    fight.get("weight_class"),
                    picked_fighter,
                    picked_method,
                    now,
                    existing["id"],
                ),
            )
            row_id = existing["id"]
        else:
            cursor = conn.execute(
                "INSERT INTO user_predictions ("
                "user_id, fight_url, event_id, event_name, event_url, event_date, "
                "fighter_1, fighter_2, weight_class, picked_fighter, picked_method, "
                "status, created_at, updated_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)",
                (
                    user_id,
                    fight_url,
                    fight.get("event_id"),
                    fight.get("event_name"),
                    fight.get("event_url"),
                    fight.get("event_date"),
                    fight.get("fighter_1"),
                    fight.get("fighter_2"),
                    fight.get("weight_class"),
                    picked_fighter,
                    picked_method,
                    now,
                    now,
                ),
            )
            row_id = cursor.lastrowid

        row = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM user_predictions WHERE id = ?", (row_id,)
        ).fetchone()
    return dict(row)


def get(user_id: Any, fight_url: str) -> dict[str, Any] | None:
    with connection.transaction() as conn:
        schema.init_db(conn)
        row = conn.execute(
            f"SELECT {_FULL_COLUMNS} FROM user_predictions "
            "WHERE user_id = ? AND fight_url = ?",
            (user_id, fight_url),
        ).fetchone()
    return dict(row) if row is not None else None


def list_for_user(user_id: Any, event_id: str | None = None) -> list[dict[str, Any]]:
    with connection.transaction() as conn:
        schema.init_db(conn)
        if event_id is None:
            rows = conn.execute(
                f"SELECT {_FULL_COLUMNS} FROM user_predictions "
                "WHERE user_id = ? ORDER BY event_date, id",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_FULL_COLUMNS} FROM user_predictions "
                "WHERE user_id = ? AND event_id = ? ORDER BY id",
                (user_id, event_id),
            ).fetchall()
    return [dict(row) for row in rows]


def list_pending(user_id: Any | None = None) -> list[dict[str, Any]]:
    """Not-yet-resolved picks (status 'open') for the scoring pass — all users, or one."""
    with connection.transaction() as conn:
        schema.init_db(conn)
        if user_id is None:
            rows = conn.execute(
                f"SELECT {_FULL_COLUMNS} FROM user_predictions WHERE status = 'open' "
                "ORDER BY id"
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_FULL_COLUMNS} FROM user_predictions "
                "WHERE status = 'open' AND user_id = ? ORDER BY id",
                (user_id,),
            ).fetchall()
    return [dict(row) for row in rows]


def list_reconcilable(user_id: Any | None = None) -> list[dict[str, Any]]:
    """Picks that may still change as official result data settles.

    ``open`` picks need their first settlement. ``void`` picks are included because
    a provider can briefly publish an incomplete or mismatched result row before the
    clean official result arrives. Scored picks remain terminal.
    """
    with connection.transaction() as conn:
        schema.init_db(conn)
        if user_id is None:
            rows = conn.execute(
                f"SELECT {_FULL_COLUMNS} FROM user_predictions "
                "WHERE status IN ('open', 'void') ORDER BY id"
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_FULL_COLUMNS} FROM user_predictions "
                "WHERE status IN ('open', 'void') AND user_id = ? ORDER BY id",
                (user_id,),
            ).fetchall()
    return [dict(row) for row in rows]


def delete(user_id: Any, fight_url: str) -> bool:
    with connection.transaction() as conn:
        schema.init_db(conn)
        cursor = conn.execute(
            "DELETE FROM user_predictions WHERE user_id = ? AND fight_url = ?",
            (user_id, fight_url),
        )
        return cursor.rowcount > 0


def mark_scored(
    prediction_id: Any, result_correct: bool, method_correct: bool | None
) -> bool:
    """Record the graded outcome of a pick (used by the scoring pass)."""
    with connection.transaction() as conn:
        schema.init_db(conn)
        cursor = conn.execute(
            "UPDATE user_predictions SET status = 'scored', result_correct = ?, "
            "method_correct = ?, scored_at = ? WHERE id = ?",
            (
                1 if result_correct else 0,
                None if method_correct is None else (1 if method_correct else 0),
                _now(),
                prediction_id,
            ),
        )
        return cursor.rowcount > 0


def mark_void(prediction_id: Any) -> bool:
    """Void a pick (cancelled bout / fighter swap / draw / no-contest) — never graded."""
    with connection.transaction() as conn:
        schema.init_db(conn)
        cursor = conn.execute(
            "UPDATE user_predictions SET status = 'void', result_correct = NULL, "
            "method_correct = NULL, scored_at = ? WHERE id = ?",
            (_now(), prediction_id),
        )
        return cursor.rowcount > 0
