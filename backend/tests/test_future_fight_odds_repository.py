"""
Tests for the future-fight-odds repository (Phase 1 — SQLite, full-replace).

Runs under pytest, or standalone:  python tests/test_future_fight_odds_repository.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.repositories import future_fight_odds_repository as repo  # noqa: E402


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def test_roundtrip_and_full_replace(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.replace_all([
        {"fight_url": "f1", "fighter_1": "A", "fighter_2": "B", "odds_available": True,
         "fighter_1_market_probability": 0.6, "fighter_2_market_probability": 0.4,
         "market_favorite": "A"},
        {"fight_url": "f2", "fighter_1": "C", "fighter_2": "D", "odds_available": False},
    ])

    assert repo.count() == 2
    df = repo.read_all_df()
    assert set(df["fight_url"]) == {"f1", "f2"}
    assert df[df["fight_url"] == "f1"].iloc[0]["fighter_1_market_probability"] == 0.6

    # A fresh odds refresh full-replaces the table.
    repo.replace_all([{"fight_url": "f3", "fighter_1": "E", "fighter_2": "F", "odds_available": True}])
    assert list(repo.read_all_df()["fight_url"]) == ["f3"]


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
