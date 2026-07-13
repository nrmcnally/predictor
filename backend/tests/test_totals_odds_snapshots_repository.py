from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.repositories import totals_odds_snapshots_repository as repo  # noqa: E402


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _quote(**overrides):
    row = {
        "captured_at": "2026-07-13T10:00:00",
        "source": "the-odds-api",
        "odds_event_id": "evt-1",
        "fight_url": "fight-1",
        "fighter_1": "A",
        "fighter_2": "B",
        "bookmaker_key": "draftkings",
        "bookmaker_last_update": "2026-07-13T09:59:00Z",
        "rounds_line": 2.5,
        "over_odds_american": -120,
        "under_odds_american": 100,
        "over_market_probability": 0.5454545,
        "under_market_probability": 0.4545455,
    }
    row.update(overrides)
    return row


def test_append_retains_each_book_and_line(tmp_path=None):
    _use_temp_db(tmp_path or tempfile.mkdtemp())
    added = repo.append_snapshots(
        [
            _quote(),
            _quote(
                bookmaker_key="fanduel",
                bookmaker_last_update="2026-07-13T09:58:00Z",
                rounds_line=1.5,
                over_odds_american=-160,
                under_odds_american=130,
            ),
        ]
    )
    assert added == 2
    frame = repo.read_all_df()
    assert set(frame["bookmaker_key"]) == {"draftkings", "fanduel"}
    assert set(frame["rounds_line"]) == {1.5, 2.5}


def test_same_upstream_quote_is_idempotent_across_refreshes(tmp_path=None):
    _use_temp_db(tmp_path or tempfile.mkdtemp())
    assert repo.append_snapshots([_quote()]) == 1
    assert repo.append_snapshots([_quote(captured_at="2026-07-13T11:00:00")]) == 0
    assert repo.count() == 1


def test_changed_price_or_source_update_creates_new_snapshot(tmp_path=None):
    _use_temp_db(tmp_path or tempfile.mkdtemp())
    assert repo.append_snapshots([_quote()]) == 1
    assert repo.append_snapshots([_quote(over_odds_american=-125)]) == 1
    assert repo.append_snapshots(
        [_quote(bookmaker_last_update="2026-07-13T10:30:00Z")]
    ) == 1
    assert repo.count() == 3
