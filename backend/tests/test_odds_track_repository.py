"""
Tests for the odds-track repository (Phase 1 #16 — SQLite data layer).

Verifies the freeze-opening / update-closing / bump-count upsert semantics the CLV
tracker depends on, plus that fights not re-captured are preserved.

Runs under pytest, or standalone:  python tests/test_odds_track_repository.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.repositories import odds_track_repository as repo  # noqa: E402


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def test_first_capture_freezes_opening(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.record_capture("f1", "A", "B", 0.40, 0.60, "t1")

    df = repo.read_all_df()
    assert len(df) == 1
    row = df.iloc[0]
    assert row["opening_fighter_1_probability"] == 0.40
    assert row["closing_fighter_1_probability"] == 0.40  # opening == closing on first sight
    assert row["opening_captured_at"] == "t1"
    assert row["capture_count"] == 1


def test_second_capture_updates_closing_keeps_opening(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.record_capture("f1", "A", "B", 0.40, 0.60, "t1")
    repo.record_capture("f1", "A", "B", 0.55, 0.45, "t2")

    row = repo.read_all_df().iloc[0]
    assert row["opening_fighter_1_probability"] == 0.40   # frozen
    assert row["opening_captured_at"] == "t1"             # frozen
    assert row["closing_fighter_1_probability"] == 0.55   # updated
    assert row["closing_captured_at"] == "t2"             # updated
    assert row["capture_count"] == 2


def test_uncaptured_fight_is_preserved(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.record_capture("f1", "A", "B", 0.40, 0.60, "t1")
    repo.record_capture("f2", "C", "D", 0.70, 0.30, "t1")
    # Re-capture only f1; f2 must remain untouched.
    repo.record_capture("f1", "A", "B", 0.50, 0.50, "t2")

    df = repo.read_all_df().set_index("fight_url")
    assert df.loc["f2", "capture_count"] == 1
    assert df.loc["f2", "closing_fighter_1_probability"] == 0.70
    assert df.loc["f1", "capture_count"] == 2


def test_import_rows_preserves_values(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.import_rows([
        {"fight_url": "f1", "fighter_1": "A", "fighter_2": "B",
         "opening_fighter_1_probability": 0.40, "opening_fighter_2_probability": 0.60,
         "opening_captured_at": "t1",
         "closing_fighter_1_probability": 0.55, "closing_fighter_2_probability": 0.45,
         "closing_captured_at": "t2", "capture_count": 3},
    ])

    row = repo.read_all_df().iloc[0]
    assert row["opening_fighter_1_probability"] == 0.40
    assert row["closing_fighter_1_probability"] == 0.55
    assert row["capture_count"] == 3


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
