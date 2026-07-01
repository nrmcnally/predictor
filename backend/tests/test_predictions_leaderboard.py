"""
Tests for the user leaderboard: only public users appear, ranking is by FIGHT IQ
rating with provisional users sorted below established ones, the current user is
flagged, and emails are never exposed.

Runs under pytest, or standalone:  python tests/test_predictions_leaderboard.py
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.repositories import (  # noqa: E402
    event_fights_repository,
    saved_predictions_repository,
    user_predictions_repository,
    users_repository,
)
from app.services import auth_service, friends_service, predictions_stats_service  # noqa: E402

UP = "http://ufcstats.com/fight-details/"
RES = "http://www.ufcstats.com/fight-details/"


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _result(fight_url, f1, f2, winner, method="U-DEC", event_date="January 1, 2026"):
    return {
        "event_name": "UFC 999", "event_date": event_date, "event_url": "u",
        "fight_url": fight_url, "fighter_1": f1, "fighter_2": f2,
        "winner": winner, "loser": f2 if winner == f1 else f1,
        "weight_class": "Lightweight", "method": method,
    }


def _fight(fight_url, f1, f2, event_id="evt1", event_date="January 1, 2026"):
    return {
        "fight_url": fight_url, "event_id": event_id, "event_name": "UFC 999",
        "event_url": "u", "event_date": event_date,
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


def test_friends_scope_includes_private_accepted_friends_only(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    me = auth_service.register_user("me@example.com", "password123", "Me")
    friend = auth_service.register_user("friend@example.com", "password123", "Friend")
    stranger = auth_service.register_user("stranger@example.com", "password123", "Stranger")
    # Nobody opts into the public leaderboard; friends scope is still allowed.
    friends_service.send_friend_request(me["id"], "Friend")
    request_id = friends_service.get_overview(friend["id"])["incoming"][0]["friendship_id"]
    friends_service.respond_to_request(friend["id"], request_id, True)

    board = predictions_stats_service.build_leaderboard(
        current_user_id=me["id"],
        scope="friends",
    )

    names = {row["display_name"] for row in board}
    assert names == {"Me", "Friend"}
    assert "Stranger" not in names
    assert all("email" not in row for row in board)
    assert "example.com" not in str(board)
    assert any(row["is_me"] for row in board)


def test_leaderboard_windows_filter_scored_picks(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    user = auth_service.register_user("window@example.com", "password123", "Window")
    auth_service.set_visibility(user["id"], True)

    results = []
    for index in range(6):
        event_date = f"January {index + 1}, 2026"
        fight_url = f"{UP}w{index}"
        result_url = f"{RES}w{index}"
        event_id = f"evt{index}"
        results.append(_result(result_url, "A", "B", "A", event_date=event_date))
        user_predictions_repository.upsert(
            user["id"],
            _fight(fight_url, "A", "B", event_id=event_id, event_date=event_date),
            "A",
            None,
        )

    event_fights_repository.replace_all(results)

    all_time = predictions_stats_service.build_leaderboard(
        current_user_id=user["id"], window="all_time"
    )[0]
    last5 = predictions_stats_service.build_leaderboard(
        current_user_id=user["id"], window="last5"
    )[0]
    current_month = predictions_stats_service.build_leaderboard(
        current_user_id=user["id"], window="current_month", today=date(2026, 1, 20)
    )[0]
    other_month = predictions_stats_service.build_leaderboard(
        current_user_id=user["id"], window="current_month", today=date(2026, 2, 1)
    )[0]

    assert all_time["graded"] == 6
    assert last5["graded"] == 5
    assert current_month["graded"] == 6
    assert other_month["graded"] == 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all leaderboard tests passed")
