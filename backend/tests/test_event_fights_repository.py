"""
Tests for the event-fights (results) repository (Phase 1 #16 — SQLite data layer).

event_fights is the core results table feeding both the app and the ML training
pipeline (build_matchups), so its contract is pinned down first, TDD-style:

  - read_all_df()        -> DataFrame with the canonical columns
  - replace_all(rows)    -> full overwrite (the scraper's full scrape)
  - upsert_fights(rows)  -> insert-or-replace by fight_url (incremental merge, keep last)
  - import_rows(rows)    -> one-time CSV import (full replace)
  - count()

Runs under pytest, or standalone:  python tests/test_event_fights_repository.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.repositories import event_fights_repository as repo  # noqa: E402


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _fight(fight_url, **overrides):
    base = {
        "event_name": "UFC X",
        "event_date": "2026-01-01",
        "event_location": "Las Vegas",
        "event_url": "http://e/1",
        "fight_url": fight_url,
        "fighter_1": "A",
        "fighter_2": "B",
        "result_1": "win",
        "result_2": "loss",
        "winner": "A",
        "loser": "B",
        "weight_class": "Lightweight",
        "method": "Decision",
        "round": 3,
        "time": "5:00",
    }
    base.update(overrides)
    return base


def test_replace_all_and_read(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.replace_all([_fight("f1"), _fight("f2", winner="C", fighter_1="C")])

    df = repo.read_all_df()
    assert len(df) == 2
    assert set(repo.COLUMN_NAMES).issubset(set(df.columns))
    assert set(df["fight_url"]) == {"f1", "f2"}
    assert df[df["fight_url"] == "f1"].iloc[0]["winner"] == "A"


def test_replace_all_overwrites_everything(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.replace_all([_fight("f1"), _fight("f2")])
    repo.replace_all([_fight("f3")])  # a fresh full scrape replaces the table

    assert set(repo.read_all_df()["fight_url"]) == {"f3"}


def test_upsert_inserts_new_and_updates_existing(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.replace_all([_fight("f1", winner="A")])
    # Incremental merge: add f2, and correct f1's winner (keep last).
    repo.upsert_fights([_fight("f2"), _fight("f1", winner="B")])

    df = repo.read_all_df().set_index("fight_url")
    assert set(df.index) == {"f1", "f2"}
    assert df.loc["f1", "winner"] == "B"


def test_round_is_nullable(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.replace_all([_fight("f1", round=None)])
    value = repo.read_all_df().iloc[0]["round"]
    assert value is None or pd.isna(value)


def test_count(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.replace_all([_fight("f1"), _fight("f2"), _fight("f3")])
    assert repo.count() == 3


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
