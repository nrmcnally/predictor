from __future__ import annotations

import sqlite3
from pathlib import Path

# Refreshing a deployed instance from a locally-built bundle must NOT touch the
# tables that live on the server: accounts, picks, friendships, and admin lock
# controls are created there and exist nowhere else. Everything the local Data Ops
# pipeline produces is "shared". Snapshot tables are replaced wholesale; append-only
# observation tables are merged so deploying a bundle cannot erase server captures.
SHARED_TABLES = [
    "event_fights",
    "upcoming_events",
    "upcoming_fights",
    "future_fight_odds",
    "fight_odds_track",
    "saved_card_predictions",
    "saved_model_predictions",
    "model_runs",
    "totals_odds_snapshots",
]
APPEND_ONLY_SHARED_TABLES = {"totals_odds_snapshots"}
PERSONAL_TABLES = ["users", "user_predictions", "friendships", "event_controls"]


def _columns(conn: sqlite3.Connection, schema_name: str, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA {schema_name}.table_info({table})").fetchall()
    return [row[1] for row in rows]


def sync_shared_tables(live_db: Path | str, bundle_db: Path | str) -> dict[str, int]:
    """Replace the shared/global tables in ``live_db`` with the versions from
    ``bundle_db``, leaving the personal tables untouched. Column-name-aware, so a
    minor schema drift between the two files doesn't corrupt rows. Runs in one
    transaction: an error rolls everything back."""
    live_db = Path(live_db)
    bundle_db = Path(bundle_db)
    if not live_db.is_file():
        raise FileNotFoundError(f"live DB not found: {live_db}")
    if not bundle_db.is_file():
        raise FileNotFoundError(f"bundle DB not found: {bundle_db}")

    # Both files should have been created by the same code generation; run the
    # forward migrations on the live side first so new columns exist.
    from app.db import schema

    conn = sqlite3.connect(live_db)
    try:
        schema.init_db(conn)
        conn.execute("ATTACH DATABASE ? AS bundle", (str(bundle_db),))
        bundle_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM bundle.sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

        replaced: dict[str, int] = {}
        for table in SHARED_TABLES:
            if table not in bundle_tables:
                continue
            shared_columns = [
                column
                for column in _columns(conn, "main", table)
                if column in set(_columns(conn, "bundle", table))
            ]
            if not shared_columns:
                continue
            column_list = ", ".join(shared_columns)
            if table in APPEND_ONLY_SHARED_TABLES:
                cursor = conn.execute(
                    f"INSERT OR IGNORE INTO main.{table} ({column_list}) "
                    f"SELECT {column_list} FROM bundle.{table}"
                )
            else:
                conn.execute(f"DELETE FROM main.{table}")
                cursor = conn.execute(
                    f"INSERT INTO main.{table} ({column_list}) "
                    f"SELECT {column_list} FROM bundle.{table}"
                )
            replaced[table] = cursor.rowcount

        conn.commit()
        return replaced
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
