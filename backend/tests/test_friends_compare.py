"""
Tests for friend head-to-head compare: shared graded picks only, per-card breakdown
with actual winners, card-win record, and that non-friends can't compare.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.repositories import event_fights_repository, user_predictions_repository  # noqa: E402
from app.services import auth_service, friends_compare_service, friends_service  # noqa: E402

UP = "http://ufcstats.com/fight-details/"
RES = "http://www.ufcstats.com/fight-details/"


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _result(fight_url, f1, f2, winner):
    return {
        "event_name": "UFC 999", "event_date": "January 1, 2026", "event_url": "u",
        "fight_url": fight_url, "fighter_1": f1, "fighter_2": f2,
        "winner": winner, "loser": f2 if winner == f1 else f1,
        "weight_class": "Lightweight", "method": "U-DEC",
    }


def _fight(fight_url, f1, f2):
    return {
        "fight_url": fight_url, "event_id": "evt1", "event_name": "UFC 999",
        "event_url": "u", "event_date": "January 1, 2026",
        "fighter_1": f1, "fighter_2": f2, "weight_class": "Lightweight",
    }


def _befriend(a, b):
    friends_service.send_friend_request(a["id"], "Boz")
    fid = friends_service.get_overview(b["id"])["incoming"][0]["friendship_id"]
    friends_service.respond_to_request(b["id"], fid, True)


def test_compare_records_shared_picks_and_card_winner(tmp_path=None):
    _use_temp_db(tmp_path or tempfile.mkdtemp())
    a = auth_service.register_user("ada@example.com", "password123", "Ada")
    b = auth_service.register_user("boz@example.com", "password123", "Boz")
    _befriend(a, b)

    event_fights_repository.replace_all([
        _result(RES + "f1", "Underdog", "Favorite", "Underdog"),
        _result(RES + "f2", "Chalk", "Dog", "Chalk"),
    ])
    # Ada sweeps the card; Boz misses both.
    user_predictions_repository.upsert(a["id"], _fight(UP + "f1", "Underdog", "Favorite"), "Underdog", None)
    user_predictions_repository.upsert(a["id"], _fight(UP + "f2", "Chalk", "Dog"), "Chalk", None)
    user_predictions_repository.upsert(b["id"], _fight(UP + "f1", "Underdog", "Favorite"), "Favorite", None)
    user_predictions_repository.upsert(b["id"], _fight(UP + "f2", "Chalk", "Dog"), "Dog", None)

    cmp = friends_compare_service.build_compare(a["id"], b["id"])

    assert cmp["friend"]["display_name"] == "Boz"
    assert cmp["shared"] == 2
    assert cmp["you"]["correct"] == 2 and cmp["them"]["correct"] == 0
    assert cmp["card_record"] == {"you": 1, "them": 0, "tied": 0}

    assert len(cmp["cards"]) == 1
    card = cmp["cards"][0]
    assert card["total"] == 2 and card["winner"] == "you"

    f1 = next(f for f in card["fights"] if f["actual_winner"] == "Underdog")
    assert f1["your_pick"] == "Underdog" and f1["your_correct"] is True
    assert f1["their_pick"] == "Favorite" and f1["their_correct"] is False


def test_only_shared_picks_count(tmp_path=None):
    _use_temp_db(tmp_path or tempfile.mkdtemp())
    a = auth_service.register_user("ada@example.com", "password123", "Ada")
    b = auth_service.register_user("boz@example.com", "password123", "Boz")
    _befriend(a, b)

    event_fights_repository.replace_all([
        _result(RES + "f1", "Underdog", "Favorite", "Underdog"),
        _result(RES + "solo", "Solo", "Nobody", "Solo"),
    ])
    user_predictions_repository.upsert(a["id"], _fight(UP + "f1", "Underdog", "Favorite"), "Underdog", None)
    user_predictions_repository.upsert(a["id"], _fight(UP + "solo", "Solo", "Nobody"), "Solo", None)
    # Boz only picked f1 — the solo pick is not shared.
    user_predictions_repository.upsert(b["id"], _fight(UP + "f1", "Underdog", "Favorite"), "Underdog", None)

    cmp = friends_compare_service.build_compare(a["id"], b["id"])
    assert cmp["shared"] == 1


def test_cannot_compare_with_non_friend(tmp_path=None):
    _use_temp_db(tmp_path or tempfile.mkdtemp())
    a = auth_service.register_user("ada@example.com", "password123", "Ada")
    b = auth_service.register_user("boz@example.com", "password123", "Boz")
    try:
        friends_compare_service.build_compare(a["id"], b["id"])
        assert False, "expected ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all compare tests passed")
