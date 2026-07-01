"""
Tests for event lock controls: odds-derived start suggestions, manual overrides,
and force-open / force-locked modes for the prediction game.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.repositories import (  # noqa: E402
    future_cards_repository,
    future_fight_odds_repository,
)
from app.services import event_lock_service  # noqa: E402


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _seed_event():
    event = {
        "event_id": "evt1",
        "event_name": "UFC 999",
        "event_date": "July 11, 2026",
        "event_location": "Las Vegas",
        "event_url": "http://ufcstats.com/event-details/evt1",
    }
    fights = [
        {
            **event,
            "fight_url": "http://ufcstats.com/fight-details/one",
            "fighter_1": "A",
            "fighter_2": "B",
            "weight_class": "Heavyweight",
        },
        {
            **event,
            "fight_url": "http://ufcstats.com/fight-details/two",
            "fighter_1": "C",
            "fighter_2": "D",
            "weight_class": "Lightweight",
        },
    ]
    future_cards_repository.replace_upcoming_events([event])
    future_cards_repository.replace_upcoming_fights(fights)
    future_fight_odds_repository.replace_all(
        [
            {
                "fight_url": fights[0]["fight_url"],
                "odds_available": 1,
                "odds_commence_time": "2026-07-11T22:00:00Z",
                "odds_match_low_confidence": 0,
            },
            {
                "fight_url": fights[1]["fight_url"],
                "odds_available": 1,
                "odds_commence_time": "2026-07-11T23:30:00Z",
                "odds_match_low_confidence": 0,
            },
        ]
    )
    return event, fights


def _dt(value):
    return event_lock_service.parse_datetime_utc(value)


def test_auto_lock_uses_earliest_matched_odds_time(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    event, fights = _seed_event()
    fight_urls = [fight["fight_url"] for fight in fights]

    before = event_lock_service.build_event_lock_state(
        event, fight_urls=fight_urls, now=_dt("2026-07-11T21:59:00Z")
    )
    after = event_lock_service.build_event_lock_state(
        event, fight_urls=fight_urls, now=_dt("2026-07-11T22:01:00Z")
    )

    assert before["effective_start_at_utc"] == "2026-07-11T22:00:00Z"
    assert before["effective_source"] == "odds"
    assert before["suggested_match_count"] == 2
    assert before["locked"] is False
    assert after["locked"] is True


def test_manual_controls_override_auto_lock(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    event, fights = _seed_event()

    event_lock_service.set_event_control(
        "evt1", lock_mode="force_open", event_start_at_utc=None, updated_by=7
    )
    force_open = event_lock_service.build_event_lock_state(
        event, fight_urls=[fight["fight_url"] for fight in fights], now=_dt("2026-07-12T01:00:00Z")
    )
    assert force_open["locked"] is False
    assert force_open["lock_reason"] == "force_open"

    event_lock_service.set_event_control(
        "evt1", lock_mode="force_locked", event_start_at_utc=None, updated_by=7
    )
    force_locked = event_lock_service.build_event_lock_state(
        event, fight_urls=[fight["fight_url"] for fight in fights], now=_dt("2026-07-10T01:00:00Z")
    )
    assert force_locked["locked"] is True
    assert force_locked["lock_reason"] == "force_locked"

    event_lock_service.set_event_control(
        "evt1",
        lock_mode="auto",
        event_start_at_utc="2026-07-12T02:00:00-04:00",
        updated_by=7,
    )
    manual = event_lock_service.build_event_lock_state(
        event, fight_urls=[fight["fight_url"] for fight in fights], now=_dt("2026-07-12T05:59:00Z")
    )
    assert manual["effective_start_at_utc"] == "2026-07-12T06:00:00Z"
    assert manual["effective_source"] == "manual"
    assert manual["locked"] is False


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all event lock tests passed")
