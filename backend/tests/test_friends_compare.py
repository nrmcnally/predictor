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


def test_fights_come_back_in_card_order_not_alphabetical(tmp_path=None):
    """Fights must follow the scraped card order (main event first, like My Picks).
    Names are chosen so alphabetical order would REVERSE the card order."""
    from app.repositories import future_cards_repository

    _use_temp_db(tmp_path or tempfile.mkdtemp())
    a = auth_service.register_user("ada@example.com", "password123", "Ada")
    b = auth_service.register_user("boz@example.com", "password123", "Boz")
    _befriend(a, b)

    # Completed card: results table rows are in card order — main event first.
    event_fights_repository.replace_all([
        _result(RES + "main", "Zed Mainman", "Yves Costar", "Zed Mainman"),
        _result(RES + "prelim", "Aaron Opener", "Bob Undercard", "Aaron Opener"),
    ])
    for user in (a, b):
        user_predictions_repository.upsert(user["id"], _fight(UP + "main", "Zed Mainman", "Yves Costar"), "Zed Mainman", None)
        user_predictions_repository.upsert(user["id"], _fight(UP + "prelim", "Aaron Opener", "Bob Undercard"), "Aaron Opener", None)

    # Upcoming card: same idea, seeded through the upcoming_fights table.
    upcoming = [
        {"event_id": "evt2", "event_name": "UFC 1000", "event_date": "December 31, 2099",
         "event_location": "Vegas", "event_url": "u2",
         "fight_url": UP + "up-main", "fighter_1": "Zola Headliner", "fighter_2": "Yuri Second",
         "weight_class": "Lightweight"},
        {"event_id": "evt2", "event_name": "UFC 1000", "event_date": "December 31, 2099",
         "event_location": "Vegas", "event_url": "u2",
         "fight_url": UP + "up-prelim", "fighter_1": "Abe Firstfight", "fighter_2": "Ben Prelim",
         "weight_class": "Lightweight"},
    ]
    future_cards_repository.replace_upcoming_fights(upcoming)
    for row in upcoming:
        fight = {**_fight(row["fight_url"], row["fighter_1"], row["fighter_2"]),
                 "event_id": "evt2", "event_date": "December 31, 2099"}
        # Both users pick: upcoming compare only includes fights both picked.
        user_predictions_repository.upsert(a["id"], fight, row["fighter_1"], None)
        user_predictions_repository.upsert(b["id"], fight, row["fighter_2"], None)

    cmp = friends_compare_service.build_compare(a["id"], b["id"])

    completed = cmp["cards"][0]["fights"]
    assert [f["fighter_1"] for f in completed] == ["Zed Mainman", "Aaron Opener"]

    upcoming_card = next(c for c in cmp["upcoming"] if c["event_id"] == "evt2")
    assert [f["fighter_1"] for f in upcoming_card["fights"]] == [
        "Zola Headliner", "Abe Firstfight",
    ]


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


def test_upcoming_only_shows_fights_both_picked_and_skips_past_events(tmp_path=None):
    """One-sided picks stay out of the head-to-head, and an 'open' pick whose
    event day has passed (a cancelled/changed bout waiting to be voided) must
    not show as an upcoming fight."""
    _use_temp_db(tmp_path or tempfile.mkdtemp())
    a = auth_service.register_user("ada2@example.com", "password123", "Ada")
    b = auth_service.register_user("boz2@example.com", "password123", "Boz")
    _befriend(a, b)

    future_fight = {**_fight(UP + "both", "Ann Both", "Bea Both"),
                    "event_id": "evt-f", "event_date": "December 31, 2099"}
    solo_fight = {**_fight(UP + "solo", "Cal Solo", "Dee Solo"),
                  "event_id": "evt-f", "event_date": "December 31, 2099"}
    cancelled = {**_fight(UP + "cancelled", "Eve Gone", "Fay Gone"),
                 "event_id": "evt-past", "event_date": "January 1, 2020"}

    user_predictions_repository.upsert(a["id"], future_fight, "Ann Both", None)
    user_predictions_repository.upsert(b["id"], future_fight, "Bea Both", None)
    user_predictions_repository.upsert(a["id"], solo_fight, "Cal Solo", None)
    user_predictions_repository.upsert(a["id"], cancelled, "Eve Gone", None)
    user_predictions_repository.upsert(b["id"], cancelled, "Eve Gone", None)

    cmp = friends_compare_service.build_compare(a["id"], b["id"])

    upcoming_keys = [
        f["fight_key"] for card in cmp["upcoming"] for f in card["fights"]
    ]
    assert any("both" in k for k in upcoming_keys)
    assert not any("solo" in k for k in upcoming_keys)
    assert not any("cancelled" in k for k in upcoming_keys)
    fight = cmp["upcoming"][0]["fights"][0]
    assert fight["their_pick"] == "Bea Both"
    assert fight["their_pick_hidden"] is False
    assert fight["agree"] is False


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
