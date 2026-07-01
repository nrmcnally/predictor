"""
Tests for the user leaderboard: only public users appear, ranking is by FIGHT IQ
rating with provisional users sorted below established ones, the current user is
flagged, and emails are never exposed.

Runs under pytest, or standalone:  python tests/test_predictions_leaderboard.py
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
    users_repository,
)
from app.services import auth_service, predictions_stats_service  # noqa: E402

UP = "http://ufcstats.com/fight-details/"
RES = "http://www.ufcstats.com/fight-details/"


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _result(fight_url, f1, f2, winner, method="U-DEC"):
    return {
        "event_name": "UFC 999", "event_date": "January 1, 2026", "event_url": "u",
        "fight_url": fight_url, "fighter_1": f1, "fighter_2": f2,
        "winner": winner, "loser": f2 if winner == f1 else f1,
        "weight_class": "Lightweight", "method": method,
    }


def _fight(fight_url, f1, f2):
    return {
        "fight_url": fight_url, "event_id": "evt1", "event_name": "UFC 999",
        "event_url": "u", "event_date": "January 1, 2026",
        "fighter_1": f1, "fighter_2": f2, "weight_class": "Lightweight",
    }


def test_public_name_never_uses_email():
    assert predictions_stats_service._public_name(
        {"display_name": "Nate", "email": "nate@x.com"}
    ) == "Nate"
    assert predictions_stats_service._public_name(
        {"display_name": "", "email": "nate@x.com"}
    ) == "Unnamed User"
    assert predictions_stats_service._public_name(
        {"display_name": "nate@x.com", "email": "nate@x.com"}
    ) == "Unnamed User"


def test_leaderboard_only_public_ranked_by_rating(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    # Two public users + one private; results for two fights.
    pub_a = auth_service.register_user("a@example.com", "password123", "Ada")
    pub_b = auth_service.register_user("b@example.com", "password123", "Boz")
    priv = auth_service.register_user("c@example.com", "password123", "Cyd")
    auth_service.set_visibility(pub_a["id"], True)
    auth_service.set_visibility(pub_b["id"], True)
    # priv stays private (default).

    event_fights_repository.replace_all([
        _result(RES + "f1", "Underdog", "Favorite", "Underdog", "KO/TKO"),
        _result(RES + "f2", "Chalk", "Dog", "Chalk", "U-DEC"),
    ])
    saved_predictions_repository.import_rows([
        {"event_id": "evt1", "fight_url": RES + "f1", "fighter_1": "Underdog",
         "fighter_2": "Favorite", "fighter_1_market_probability": 0.3,
         "fighter_2_market_probability": 0.7, "predicted_winner": "Favorite"},
    ])

    # Ada nails the underdog (big rating gain); Boz takes the favorite who lost.
    user_predictions_repository.upsert(pub_a["id"], _fight(UP + "f1", "Underdog", "Favorite"), "Underdog", None)
    user_predictions_repository.upsert(pub_b["id"], _fight(UP + "f1", "Underdog", "Favorite"), "Favorite", None)
    # priv also picks (should never appear).
    user_predictions_repository.upsert(priv["id"], _fight(UP + "f2", "Chalk", "Dog"), "Chalk", None)

    board = predictions_stats_service.build_leaderboard(current_user_id=pub_a["id"])

    names = [row["name"] for row in board]
    assert "Cyd" not in names  # private user excluded
    assert names == ["Ada", "Boz"]  # Ada (correct underdog) outranks Boz
    assert board[0]["rank"] == 1 and board[0]["rating"] > board[1]["rating"]
    assert board[0]["is_me"] is True  # current user flagged
    assert board[0]["provisional"] is True  # < 10 graded picks
    assert board[0]["provisional_threshold"] == predictions_stats_service.PROVISIONAL_THRESHOLD
    assert board[0]["picks_until_established"] == 9
    assert all("email" not in row for row in board)
    assert all("@" not in row["display_name"] for row in board)


def test_leaderboard_falls_back_without_exposing_email(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    user = auth_service.register_user("noname@example.com", "password123", "Visible")
    users_repository.update_profile(user["id"], "noname@example.com", "")
    auth_service.set_visibility(user["id"], True)

    board = predictions_stats_service.build_leaderboard(current_user_id=user["id"])

    assert board[0]["display_name"] == "Unnamed User"
    assert board[0]["name"] == "Unnamed User"
    assert "email" not in board[0]
    assert "noname@example.com" not in str(board)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all leaderboard tests passed")
