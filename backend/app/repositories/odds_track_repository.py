from __future__ import annotations

import math
from typing import Any

import pandas as pd

from app.db import connection, schema
from app.db.frame_contract import normalize_frame

# Column order mirrors the legacy fight_odds_track.csv so existing consumers
# (clv_evaluation_service) see an identical DataFrame shape.
# Typed spec mirroring the fight_odds_track CREATE TABLE in schema.py; feeds
# the frame contract on read.
TRACK_COLUMNS_SPEC: list[tuple[str, str]] = [
    ("fight_url", "TEXT"),
    ("fighter_1", "TEXT"),
    ("fighter_2", "TEXT"),
    ("opening_fighter_1_probability", "REAL"),
    ("opening_fighter_2_probability", "REAL"),
    ("opening_captured_at", "TEXT"),
    ("closing_fighter_1_probability", "REAL"),
    ("closing_fighter_2_probability", "REAL"),
    ("closing_captured_at", "TEXT"),
    ("capture_count", "INTEGER"),
]

TRACK_COLUMNS = [
    "fight_url",
    "fighter_1",
    "fighter_2",
    "opening_fighter_1_probability",
    "opening_fighter_2_probability",
    "opening_captured_at",
    "closing_fighter_1_probability",
    "closing_fighter_2_probability",
    "closing_captured_at",
    "capture_count",
]


def _coerce_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw row (e.g. from a CSV with pandas NaNs) to the table columns."""
    out: dict[str, Any] = {}
    for column in TRACK_COLUMNS:
        value = row.get(column)
        if value is None or (isinstance(value, float) and math.isnan(value)):
            out[column] = None
        else:
            out[column] = value

    capture_count = out.get("capture_count")
    out["capture_count"] = int(capture_count) if capture_count not in (None, "") else 1
    return out


def read_all_df() -> pd.DataFrame:
    """The full odds track as a DataFrame (empty-with-headers if none)."""
    with connection.transaction() as conn:
        schema.init_db(conn)
        rows = conn.execute("SELECT * FROM fight_odds_track ORDER BY fight_url").fetchall()

    if not rows:
        return pd.DataFrame(columns=TRACK_COLUMNS)

    df = pd.DataFrame([dict(row) for row in rows], columns=TRACK_COLUMNS)
    return normalize_frame(df, TRACK_COLUMNS_SPEC)


def record_capture(
    fight_url: str,
    fighter_1: str,
    fighter_2: str,
    fighter_1_probability: float | None,
    fighter_2_probability: float | None,
    captured_at: str,
) -> None:
    """Record one odds capture for a fight, atomically.

    First sight freezes the OPENING line (and sets it as the closing line too);
    every later capture updates only the CLOSING line and bumps capture_count.
    Fights never re-captured simply keep their last-seen row — no rewrite needed.
    """
    with connection.transaction() as conn:
        schema.init_db(conn)
        conn.execute(
            """
            INSERT INTO fight_odds_track (
                fight_url, fighter_1, fighter_2,
                opening_fighter_1_probability, opening_fighter_2_probability,
                opening_captured_at,
                closing_fighter_1_probability, closing_fighter_2_probability,
                closing_captured_at,
                capture_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(fight_url) DO UPDATE SET
                fighter_1 = excluded.fighter_1,
                fighter_2 = excluded.fighter_2,
                closing_fighter_1_probability = excluded.closing_fighter_1_probability,
                closing_fighter_2_probability = excluded.closing_fighter_2_probability,
                closing_captured_at = excluded.closing_captured_at,
                capture_count = fight_odds_track.capture_count + 1
            """,
            (
                fight_url,
                fighter_1,
                fighter_2,
                fighter_1_probability,
                fighter_2_probability,
                captured_at,
                fighter_1_probability,
                fighter_2_probability,
                captured_at,
            ),
        )


def import_rows(rows: list[dict[str, Any]]) -> int:
    """Bulk-import existing track rows (e.g. the legacy CSV), preserving each row's
    opening/closing/capture_count exactly. Existing fight_urls are overwritten."""
    if not rows:
        return 0

    with connection.transaction() as conn:
        schema.init_db(conn)
        for row in rows:
            conn.execute(
                """
                INSERT INTO fight_odds_track (
                    fight_url, fighter_1, fighter_2,
                    opening_fighter_1_probability, opening_fighter_2_probability,
                    opening_captured_at,
                    closing_fighter_1_probability, closing_fighter_2_probability,
                    closing_captured_at,
                    capture_count
                )
                VALUES (
                    :fight_url, :fighter_1, :fighter_2,
                    :opening_fighter_1_probability, :opening_fighter_2_probability,
                    :opening_captured_at,
                    :closing_fighter_1_probability, :closing_fighter_2_probability,
                    :closing_captured_at,
                    :capture_count
                )
                ON CONFLICT(fight_url) DO UPDATE SET
                    fighter_1 = excluded.fighter_1,
                    fighter_2 = excluded.fighter_2,
                    opening_fighter_1_probability = excluded.opening_fighter_1_probability,
                    opening_fighter_2_probability = excluded.opening_fighter_2_probability,
                    opening_captured_at = excluded.opening_captured_at,
                    closing_fighter_1_probability = excluded.closing_fighter_1_probability,
                    closing_fighter_2_probability = excluded.closing_fighter_2_probability,
                    closing_captured_at = excluded.closing_captured_at,
                    capture_count = excluded.capture_count
                """,
                _coerce_row(row),
            )
    return len(rows)
