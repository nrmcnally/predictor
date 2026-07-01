"""
Tests for automatic forward migrations: adding a column to a table's canonical spec
backfills existing DBs on the next open, for every spec-driven table (not just users).
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import schema  # noqa: E402


def test_forward_migration_backfills_spec_columns():
    conn = sqlite3.connect(Path(tempfile.mkdtemp()) / "old.db")
    # Simulate old tables that predate later columns. They keep their original indexed
    # columns (event_id / fight_url) but lack the columns added since.
    conn.execute(
        "CREATE TABLE saved_model_predictions (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "saved_at TEXT, event_id TEXT, fight_url TEXT)"
    )
    conn.execute(
        "CREATE TABLE user_predictions (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER, event_id TEXT, fight_url TEXT, status TEXT)"
    )
    conn.commit()

    schema.init_db(conn)

    model_cols = {r[1] for r in conn.execute("PRAGMA table_info(saved_model_predictions)")}
    assert {"model_version", "model_recipe_hash", "model_trained_at", "model_git_commit"} <= model_cols

    pick_cols = {r[1] for r in conn.execute("PRAGMA table_info(user_predictions)")}
    assert {"picked_method", "method_correct", "event_date", "created_at"} <= pick_cols
    conn.close()


def test_init_db_is_idempotent():
    conn = sqlite3.connect(Path(tempfile.mkdtemp()) / "fresh.db")
    schema.init_db(conn)
    schema.init_db(conn)  # second call must not error or duplicate columns
    for table in ("saved_model_predictions", "user_predictions", "event_fights", "event_controls"):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        assert len(cols) == len(set(cols)), table
    conn.close()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all schema-migration tests passed")
