"""
Tests for per-account prediction stats: record + accuracy (primary), method accuracy,
and the best-effort "vs model" (beat-the-engine) comparison built from saved model picks.

Runs under pytest, or standalone:  python tests/test_predictions_stats.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.repositories import (  # noqa: E402
    event_fights_repository,
    saved_predictions_repository,
    user_predictions_repository,
)
from app.services import auth_service, predictions_stats_service  # noqa: E402

UP = "http://ufcstats.com/fight-details/"
RES = "http://www.ufcstats.com/fight-details/"


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _result(fight_url, f1, f2, winner, method):
    return {
        "event_name": "UFC 999", "event_date": "January 1, 2026",
        "event_url": "u", "fight_url": fight_url, "fighter_1": f1, "fighter_2": f2,
        "winner": winner, "loser": f2 if winner == f1 else f1,
        "weight_class": "Lightweight", "method": method,
    }


def _fight(fight_url, f1, f2):
    return {
        "fight_url": fight_url, "event_id": "evt1", "event_name": "UFC 999",
        "event_url": "u", "event_date": "January 1, 2026",
        "fighter_1": f1, "fighter_2": f2, "weight_class": "Lightweight",
    }


def _model_pick(fight_url, predicted_winner):
    return {"event_id": "evt1", "fight_url": fight_url, "predicted_winner": predicted_winner}


def _snapshot(fight_url, f1, f2, f1_market, predicted_winner):
    return {
        "event_id": "evt1", "fight_url": fight_url, "fighter_1": f1, "fighter_2": f2,
        "fighter_1_market_probability": f1_market,
        "fighter_2_market_probability": 1 - f1_market,
        "predicted_winner": predicted_winner,
    }


def test_user_stats_record_accuracy_and_vs_model(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    user = auth_service.register_user("s@example.com", "password123")

    event_fights_repository.replace_all([
        _result(RES + "f1", "Conor McGregor", "Max Holloway", "Conor McGregor", "KO/TKO Punches"),
        _result(RES + "f2", "Dustin Poirier", "Justin Gaethje", "Justin Gaethje", "U-DEC"),
        _result(RES + "f3", "Tom Aspinall", "Ciryl Gane", "Tom Aspinall", "KO/TKO"),
    ])
    # Model picks for f1 (wrong) and f2 (right); none for f3.
    saved_predictions_repository.import_rows([
        _model_pick(RES + "f1", "Max Holloway"),
        _model_pick(RES + "f2", "Justin Gaethje"),
    ])

    user_predictions_repository.upsert(user["id"], _fight(UP + "f1", "Conor McGregor", "Max Holloway"), "Conor McGregor", "ko_tko")
    user_predictions_repository.upsert(user["id"], _fight(UP + "f2", "Dustin Poirier", "Justin Gaethje"), "Dustin Poirier", None)
    user_predictions_repository.upsert(user["id"], _fight(UP + "f3", "Tom Aspinall", "Ciryl Gane"), "Tom Aspinall", None)

    stats = predictions_stats_service.build_user_stats(user["id"])

    assert stats["record"] == {"wins": 2, "losses": 1}
    assert stats["graded"] == 3
    assert abs(stats["accuracy"] - 2 / 3) < 1e-9
    assert stats["pending"] == 0

    # Method: one method pick (f1 ko_tko), and it hit.
    assert stats["method"]["picks"] == 1 and stats["method"]["accuracy"] == 1.0

    # vs model: overlap on f1 + f2; user beat the model once, model beat user once.
    vm = stats["vs_model"]
    assert vm["overlap"] == 2
    assert vm["user_beats"] == 1 and vm["model_beats"] == 1
    assert vm["delta"] == 0.0


def test_empty_stats(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    user = auth_service.register_user("e@example.com", "password123")

    stats = predictions_stats_service.build_user_stats(user["id"])
    assert stats["rating"] == 1000  # everyone starts at 1000
    assert stats["record"] == {"wins": 0, "losses": 0}
    assert stats["graded"] == 0
    assert stats["accuracy"] is None
    assert stats["streak"] is None
    assert stats["vs_model"] is None


def test_rating_rewards_correct_underdog(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    user = auth_service.register_user("u@example.com", "password123")

    # Underdog (market 30%) actually wins; the user called it.
    event_fights_repository.replace_all([
        _result(RES + "u1", "Underdog", "Favorite", "Underdog", "KO/TKO"),
    ])
    saved_predictions_repository.import_rows([
        _snapshot(RES + "u1", "Underdog", "Favorite", 0.30, "Favorite"),
    ])
    user_predictions_repository.upsert(
        user["id"], _fight(UP + "u1", "Underdog", "Favorite"), "Underdog", None
    )

    stats = predictions_stats_service.build_user_stats(user["id"])
    # K=40 (provisional), E=0.30, S=1 -> 1000 + 40*(1-0.30) = 1028.
    assert stats["rating"] == 1028
    # And the user beat the model (which had the favorite).
    assert stats["vs_model"]["user_beats"] == 1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all stats tests passed")
