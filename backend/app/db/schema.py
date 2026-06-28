from __future__ import annotations

import sqlite3

# Idempotent DDL. Each transactional dataset migrated to SQLite adds its table here.
# (Phase 1 #16: results, saved predictions, odds track, future cards. First up: the
# odds track, whose accumulate-over-time upsert benefits most from atomic writes.)
SCHEMA_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS fight_odds_track (
        fight_url TEXT PRIMARY KEY,
        fighter_1 TEXT,
        fighter_2 TEXT,
        opening_fighter_1_probability REAL,
        opening_fighter_2_probability REAL,
        opening_captured_at TEXT,
        closing_fighter_1_probability REAL,
        closing_fighter_2_probability REAL,
        closing_captured_at TEXT,
        capture_count INTEGER NOT NULL DEFAULT 1
    )
    """,
]


def init_db(conn: sqlite3.Connection) -> None:
    """Create any missing tables. Safe to call on every connection."""
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
