"""
Tests for the saved-predictions repository (Phase 1 #16 — SQLite data layer).

Verifies atomic per-card replace, that one card's rows don't touch another's, and
that raw CSV-style values (bools as "True"/"False", numeric strings) coerce to the
typed columns.

Runs under pytest, or standalone:  python tests/test_saved_predictions_repository.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.repositories import saved_predictions_repository as repo  # noqa: E402


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _row(event_id, fight_id, **overrides):
    base = {
        "event_id": event_id,
        "fight_id": fight_id,
        "fight_url": f"http://x/{fight_id}",
        "fighter_1": "A",
        "fighter_2": "B",
        "weight_class": "Lightweight",
        "prediction_available": True,
        "predicted_winner": "A",
        "fighter_1_probability": 0.6,
    }
    base.update(overrides)
    return base


def test_replace_card_roundtrip(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.replace_card("e1", [_row("e1", "f1"), _row("e1", "f2")])

    df = repo.read_all_df()
    assert len(df) == 2
    assert set(df["fight_id"]) == {"f1", "f2"}
    row = df[df["fight_id"] == "f1"].iloc[0]
    assert row["fighter_1_probability"] == 0.6
    assert row["prediction_available"] == 1  # bool stored as 0/1


def test_replace_card_only_affects_one_event(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.replace_card("e1", [_row("e1", "f1")])
    repo.replace_card("e2", [_row("e2", "g1"), _row("e2", "g2")])
    # Re-save e1 with a different fight set; e2 must be untouched.
    repo.replace_card("e1", [_row("e1", "f9")])

    df = repo.read_all_df()
    assert set(df[df["event_id"] == "e1"]["fight_id"]) == {"f9"}
    assert len(df[df["event_id"] == "e2"]) == 2


def test_import_rows_coerces_csv_style_values(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    n = repo.import_rows([
        {
            "event_id": "e1", "fight_id": "f1",
            "prediction_available": "True", "odds_available": "False",
            "fighter_1_probability": "0.7", "bookmakers_matched": "3",
        },
    ])
    assert n == 1

    row = repo.read_all_df().iloc[0]
    assert row["prediction_available"] == 1
    assert row["odds_available"] == 0
    assert row["fighter_1_probability"] == 0.7
    assert row["bookmakers_matched"] == 3


def test_count(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    repo.replace_card("e1", [_row("e1", "f1"), _row("e1", "f2")])
    assert repo.count() == 2


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
