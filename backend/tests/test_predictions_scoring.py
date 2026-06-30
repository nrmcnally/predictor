"""
Tests for scoring account picks against completed results: correct/incorrect grading,
the optional method-of-victory bonus, the void rules (fighter swap, no-contest/draw),
pending picks with no result yet, and the fight_url host + accent normalization.

Runs under pytest, or standalone:  python tests/test_predictions_scoring.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.repositories import (  # noqa: E402
    event_fights_repository,
    user_predictions_repository,
)
from app.services import auth_service, predictions_scoring_service  # noqa: E402


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _result(fight_url, fighter_1, fighter_2, winner, method):
    return {
        "event_name": "UFC 999",
        "event_date": "January 1, 2026",
        "event_url": "http://www.ufcstats.com/event-details/e",
        "fight_url": fight_url,
        "fighter_1": fighter_1,
        "fighter_2": fighter_2,
        "winner": winner,
        "loser": fighter_2 if winner == fighter_1 else fighter_1,
        "weight_class": "Lightweight",
        "method": method,
    }


def _fight(fight_url, fighter_1, fighter_2):
    return {
        "fight_url": fight_url,
        "event_id": "evt1",
        "event_name": "UFC 999",
        "event_url": "http://ufcstats.com/event-details/e",
        "event_date": "January 1, 2026",
        "fighter_1": fighter_1,
        "fighter_2": fighter_2,
        "weight_class": "Lightweight",
    }


# Upcoming fights are scraped from ufcstats.com; results carry the www. host.
UP = "http://ufcstats.com/fight-details/"
RES = "http://www.ufcstats.com/fight-details/"


def test_grades_winner_and_method(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    user = auth_service.register_user("g@example.com", "password123")

    event_fights_repository.replace_all([
        _result(RES + "f1", "Conor McGregor", "Max Holloway", "Conor McGregor", "KO/TKO Punches"),
        _result(RES + "f2", "Dustin Poirier", "Justin Gaethje", "Justin Gaethje", "U-DEC"),
    ])
    # Correct winner + correct method.
    user_predictions_repository.upsert(
        user["id"], _fight(UP + "f1", "Conor McGregor", "Max Holloway"),
        "Conor McGregor", "ko_tko",
    )
    # Wrong winner, no method.
    user_predictions_repository.upsert(
        user["id"], _fight(UP + "f2", "Dustin Poirier", "Justin Gaethje"),
        "Dustin Poirier", None,
    )

    summary = predictions_scoring_service.score_all_pending()
    assert summary == {"scored": 2, "voided": 0, "still_pending": 0}

    p1 = user_predictions_repository.get(user["id"], UP + "f1")
    assert p1["status"] == "scored" and p1["result_correct"] == 1 and p1["method_correct"] == 1

    p2 = user_predictions_repository.get(user["id"], UP + "f2")
    assert p2["status"] == "scored" and p2["result_correct"] == 0 and p2["method_correct"] is None


def test_method_bonus_can_be_wrong(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    user = auth_service.register_user("m@example.com", "password123")

    event_fights_repository.replace_all([
        _result(RES + "f1", "A Fighter", "B Fighter", "A Fighter", "U-DEC"),
    ])
    # Right winner, but predicted a submission — method_correct is False, winner still right.
    user_predictions_repository.upsert(
        user["id"], _fight(UP + "f1", "A Fighter", "B Fighter"), "A Fighter", "submission"
    )

    predictions_scoring_service.score_all_pending()
    p = user_predictions_repository.get(user["id"], UP + "f1")
    assert p["result_correct"] == 1 and p["method_correct"] == 0


def test_voids_swap_and_no_contest(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    user = auth_service.register_user("v@example.com", "password123")

    event_fights_repository.replace_all([
        # f3: the bout that actually happened swapped in a different opponent.
        _result(RES + "f3", "A Fighter", "C Replacement", "A Fighter", "KO/TKO"),
        # f4: a no-contest — no gradable winner.
        _result(RES + "f4", "D Fighter", "E Fighter", "", "CNC"),
    ])
    user_predictions_repository.upsert(
        user["id"], _fight(UP + "f3", "A Fighter", "B Fighter"), "A Fighter", None
    )
    user_predictions_repository.upsert(
        user["id"], _fight(UP + "f4", "D Fighter", "E Fighter"), "D Fighter", None
    )

    summary = predictions_scoring_service.score_all_pending()
    assert summary["voided"] == 2 and summary["scored"] == 0

    for fid in ("f3", "f4"):
        p = user_predictions_repository.get(user["id"], UP + fid)
        assert p["status"] == "void" and p["result_correct"] is None


def test_pending_without_result_and_idempotent(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    user = auth_service.register_user("p@example.com", "password123")

    event_fights_repository.replace_all([
        _result(RES + "done", "Won Guy", "Lost Guy", "Won Guy", "U-DEC"),
    ])
    user_predictions_repository.upsert(
        user["id"], _fight(UP + "done", "Won Guy", "Lost Guy"), "Won Guy", None
    )
    # This bout has no result row yet -> stays pending.
    user_predictions_repository.upsert(
        user["id"], _fight(UP + "future", "X", "Y"), "X", None
    )

    first = predictions_scoring_service.score_all_pending()
    assert first == {"scored": 1, "voided": 0, "still_pending": 1}
    # Re-running doesn't re-grade the already-scored pick (only 'open' is considered).
    second = predictions_scoring_service.score_all_pending()
    assert second == {"scored": 0, "voided": 0, "still_pending": 1}

    assert user_predictions_repository.get(user["id"], UP + "future")["status"] == "open"


def test_matches_across_host_and_accents(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    user = auth_service.register_user("a@example.com", "password123")

    # Result: www. host + accented spelling; pick: bare host + unaccented spelling.
    event_fights_repository.replace_all([
        _result(RES + "x9", "Benoît Saint Denis", "Joel Alvarez", "Benoît Saint Denis", "SUB Guillotine Choke"),
    ])
    user_predictions_repository.upsert(
        user["id"], _fight(UP + "x9", "Benoit Saint Denis", "Joel Alvarez"),
        "Benoit Saint Denis", "submission",
    )

    predictions_scoring_service.score_all_pending()
    p = user_predictions_repository.get(user["id"], UP + "x9")
    assert p["status"] == "scored" and p["result_correct"] == 1 and p["method_correct"] == 1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all scoring tests passed")
