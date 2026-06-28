"""
Tests for the saved-model-predictions repository (Phase 1 #16 — SQLite data layer).

Shares the SnapshotTable engine with saved_card_predictions, so this focuses on the
config being correct: the right table, atomic per-card replace, and isolation from
the saved_card_predictions table.

Runs under pytest, or standalone:  python tests/test_saved_model_predictions_repository.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.repositories import saved_model_predictions_repository as model_repo  # noqa: E402
from app.repositories import saved_predictions_repository as card_repo  # noqa: E402


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _row(event_id, model_name, fight_id="f1"):
    return {
        "event_id": event_id,
        "snapshot_id": f"{event_id}::{fight_id}::{model_name}",
        "fight_id": fight_id,
        "fight_url": f"http://x/{fight_id}",
        "model_name": model_name,
        "is_best_model": model_name == "best",
        "prediction_available": True,
        "predicted_winner": "A",
        "fighter_1_probability": 0.6,
    }


def test_replace_card_roundtrip(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    model_repo.replace_card("e1", [_row("e1", "best"), _row("e1", "xgboost")])

    df = model_repo.read_all_df()
    assert len(df) == 2
    assert set(df["model_name"]) == {"best", "xgboost"}
    assert df[df["model_name"] == "best"].iloc[0]["is_best_model"] == 1


def test_replace_card_isolated_per_event(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    model_repo.replace_card("e1", [_row("e1", "best")])
    model_repo.replace_card("e2", [_row("e2", "best"), _row("e2", "xgboost")])
    model_repo.replace_card("e1", [_row("e1", "best"), _row("e1", "logistic")])

    df = model_repo.read_all_df()
    assert len(df[df["event_id"] == "e1"]) == 2
    assert len(df[df["event_id"] == "e2"]) == 2


def test_isolated_from_saved_card_table(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    model_repo.replace_card("e1", [_row("e1", "best"), _row("e1", "xgboost")])
    # The two snapshot repos must hit different tables.
    assert model_repo.count() == 2
    assert card_repo.count() == 0


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
