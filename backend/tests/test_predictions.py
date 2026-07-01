"""
Tests for account-based fight predictions (Phase 6): making/updating/deleting a
winner pick on an upcoming fight, fighter-membership + method validation, the
event-day lock, and per-user isolation.

Runs under pytest, or standalone:  python tests/test_predictions.py
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.repositories import event_fights_repository, future_cards_repository  # noqa: E402
from app.services import auth_service, event_lock_service, predictions_service  # noqa: E402


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _raises_value_error(fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
        return False
    except ValueError:
        return True


def _seed_fight(fight_url="http://ufcstats.com/fight-details/abc123", event_date="December 31, 2099"):
    event = {
        "event_id": "evt1",
        "event_name": "UFC 999",
        "event_date": event_date,
        "event_location": "Las Vegas",
        "event_url": "http://ufcstats.com/event-details/evt1",
    }
    future_cards_repository.replace_upcoming_events([event])
    future_cards_repository.replace_upcoming_fights(
        [
            {
                **event,
                "fight_url": fight_url,
                "fighter_1": "Conor McGregor",
                "fighter_2": "Max Holloway",
                "weight_class": "Welterweight",
            }
        ]
    )
    return fight_url


def _result(fight_url, fighter_1, fighter_2, winner, method="U-DEC"):
    return {
        "event_name": "UFC 999",
        "event_date": "January 1, 2026",
        "event_url": "http://www.ufcstats.com/event-details/evt1",
        "fight_url": fight_url,
        "fighter_1": fighter_1,
        "fighter_2": fighter_2,
        "winner": winner,
        "loser": fighter_2 if winner == fighter_1 else fighter_1,
        "weight_class": "Welterweight",
        "method": method,
    }


# --- making picks -------------------------------------------------------------

def test_make_and_update_prediction(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    user = auth_service.register_user("picker@example.com", "password123", "Picker")
    fight_url = _seed_fight()

    pred = predictions_service.make_prediction(user["id"], fight_url, "Conor McGregor")
    assert pred["picked_fighter"] == "Conor McGregor"
    assert pred["status"] == "open"
    assert pred["locked"] is False
    assert pred["picked_method"] is None

    # Re-picking the other fighter updates the SAME row (one pick per user per fight).
    updated = predictions_service.make_prediction(
        user["id"], fight_url, "Max Holloway", "submission"
    )
    assert updated["picked_fighter"] == "Max Holloway"
    assert updated["picked_method"] == "submission"
    assert len(predictions_service.list_predictions(user["id"])) == 1


def test_validation_rejects_bad_picks(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    user = auth_service.register_user("v@example.com", "password123")
    fight_url = _seed_fight()

    # Fighter not in this bout.
    assert _raises_value_error(
        predictions_service.make_prediction, user["id"], fight_url, "Jon Jones"
    )
    # Invalid method bucket.
    assert _raises_value_error(
        predictions_service.make_prediction,
        user["id"], fight_url, "Conor McGregor", "spinning-wheel",
    )
    # Unknown fight.
    assert _raises_value_error(
        predictions_service.make_prediction, user["id"], "http://nope", "Conor McGregor"
    )
    # Nothing got saved.
    assert predictions_service.list_predictions(user["id"]) == []


# --- the event-day lock -------------------------------------------------------

def test_locked_event_blocks_pick_and_delete(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    user = auth_service.register_user("late@example.com", "password123")
    fight_url = _seed_fight(event_date="January 1, 2020")

    assert _raises_value_error(
        predictions_service.make_prediction, user["id"], fight_url, "Conor McGregor"
    )
    assert predictions_service.is_locked("December 31, 2099") is False
    assert predictions_service.is_locked("January 1, 2020") is True
    # On the event day itself it's locked.
    assert predictions_service.is_locked("July 11, 2026", today=date(2026, 7, 11)) is True
    assert predictions_service.is_locked("July 11, 2026", today=date(2026, 7, 10)) is False


def test_event_controls_override_pick_lock(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    user = auth_service.register_user("control@example.com", "password123")
    fight_url = _seed_fight(event_date="January 1, 2020")

    event_lock_service.set_event_control(
        "evt1", lock_mode="force_open", event_start_at_utc=None, updated_by=user["id"]
    )
    pred = predictions_service.make_prediction(user["id"], fight_url, "Conor McGregor")
    assert pred["locked"] is False

    event_lock_service.set_event_control(
        "evt1", lock_mode="force_locked", event_start_at_utc=None, updated_by=user["id"]
    )
    assert predictions_service.list_predictions(user["id"])[0]["locked"] is True
    assert _raises_value_error(predictions_service.remove_prediction, user["id"], fight_url)


# --- delete + isolation -------------------------------------------------------

def test_delete_and_user_isolation(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    a = auth_service.register_user("a@example.com", "password123")
    b = auth_service.register_user("b@example.com", "password123")
    fight_url = _seed_fight()

    predictions_service.make_prediction(a["id"], fight_url, "Conor McGregor")
    predictions_service.make_prediction(b["id"], fight_url, "Max Holloway")

    # Each user sees only their own pick.
    assert predictions_service.list_predictions(a["id"])[0]["picked_fighter"] == "Conor McGregor"
    assert predictions_service.list_predictions(b["id"])[0]["picked_fighter"] == "Max Holloway"

    assert predictions_service.remove_prediction(a["id"], fight_url) is True
    assert predictions_service.list_predictions(a["id"]) == []
    # b's pick is untouched.
    assert len(predictions_service.list_predictions(b["id"])) == 1
    # Deleting a pick that isn't there is a no-op, not an error.
    assert predictions_service.remove_prediction(a["id"], fight_url) is False


def test_list_predictions_lazily_scores_completed_picks(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    user = auth_service.register_user("score-on-read@example.com", "password123")
    fight_url = _seed_fight()

    predictions_service.make_prediction(user["id"], fight_url, "Conor McGregor", "decision")
    event_fights_repository.replace_all([
        _result(
            "http://www.ufcstats.com/fight-details/abc123",
            "Conor McGregor",
            "Max Holloway",
            "Conor McGregor",
            "U-DEC",
        )
    ])

    listed = predictions_service.list_predictions(user["id"])

    assert listed[0]["status"] == "scored"
    assert listed[0]["result_correct"] == 1
    assert listed[0]["method_correct"] == 1
    assert listed[0]["scored_at"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all prediction tests passed")
