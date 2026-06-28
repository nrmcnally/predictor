"""
Tests for the future-cards repository (Phase 1 #16 — SQLite data layer).

Two narrow full-replace tables: upcoming_events + upcoming_fights.

Runs under pytest, or standalone:  python tests/test_future_cards_repository.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.repositories import future_cards_repository as repo  # noqa: E402


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def test_events_roundtrip_and_full_replace(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.replace_upcoming_events([
        {"event_id": "e1", "event_name": "UFC 1", "event_date": "2026-01-01",
         "event_location": "Vegas", "event_url": "http://e/1"},
        {"event_id": "e2", "event_name": "UFC 2", "event_date": "2026-02-01",
         "event_location": "NYC", "event_url": "http://e/2"},
    ])
    assert repo.count_upcoming_events() == 2

    # A fresh scrape full-replaces.
    repo.replace_upcoming_events([
        {"event_id": "e3", "event_name": "UFC 3", "event_date": "2026-03-01",
         "event_location": "LA", "event_url": "http://e/3"},
    ])
    assert list(repo.read_upcoming_events_df()["event_id"]) == ["e3"]


def test_fights_roundtrip(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.replace_upcoming_fights([
        {"event_id": "e1", "fight_url": "f1", "fighter_1": "A", "fighter_2": "B",
         "weight_class": "Lightweight"},
        {"event_id": "e1", "fight_url": "f2", "fighter_1": "C", "fighter_2": "D",
         "weight_class": "Welterweight"},
    ])

    df = repo.read_upcoming_fights_df()
    assert repo.count_upcoming_fights() == 2
    assert set(df["fight_url"]) == {"f1", "f2"}
    assert df[df["fight_url"] == "f1"].iloc[0]["fighter_1"] == "A"


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
