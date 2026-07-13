"""
Tests for the deploy bundle DB merge: refreshing a live server DB from a
locally-built bundle replaces the shared tables (results, cards, odds) but
preserves everything created on the server (accounts, picks, friendships).
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import schema  # noqa: E402
from app.db.bundle_sync import sync_shared_tables  # noqa: E402


def _make_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    schema.init_db(conn)
    return conn


def test_sync_replaces_shared_and_preserves_personal():
    tmp = Path(tempfile.mkdtemp())
    live_path, bundle_path = tmp / "live.db", tmp / "bundle.db"

    # Live server DB: one account + pick, and a stale results table.
    live = _make_db(live_path)
    live.execute(
        "INSERT INTO users (email, display_name, password_hash) VALUES ('a@x.com', 'Ada', 'h')"
    )
    live.execute(
        "INSERT INTO user_predictions (user_id, fight_url, picked_fighter, status) "
        "VALUES (1, 'u/f1', 'A', 'open')"
    )
    live.execute(
        "INSERT INTO event_fights (fight_url, fighter_1, fighter_2, winner) "
        "VALUES ('u/old', 'A', 'B', 'A')"
    )
    live.commit()
    live.close()

    # Fresh local bundle: two new results, no users (stripped by design anyway).
    bundle = _make_db(bundle_path)
    for i in range(2):
        bundle.execute(
            "INSERT INTO event_fights (fight_url, fighter_1, fighter_2, winner) "
            f"VALUES ('u/new{i}', 'C', 'D', 'C')"
        )
    bundle.execute(
        "INSERT INTO upcoming_fights (event_id, fighter_1, fighter_2, fight_url) "
        "VALUES ('evt9', 'E', 'F', 'u/up1')"
    )
    bundle.commit()
    bundle.close()

    replaced = sync_shared_tables(live_path, bundle_path)
    assert replaced["event_fights"] == 2
    assert replaced["upcoming_fights"] == 1

    check = sqlite3.connect(live_path)
    # Shared tables now match the bundle.
    urls = {r[0] for r in check.execute("SELECT fight_url FROM event_fights")}
    assert urls == {"u/new0", "u/new1"}  # the stale row is gone
    # Personal tables untouched.
    assert check.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    assert check.execute("SELECT COUNT(*) FROM user_predictions").fetchone()[0] == 1
    check.close()


def test_sync_survives_missing_bundle_tables():
    tmp = Path(tempfile.mkdtemp())
    live_path, bundle_path = tmp / "live.db", tmp / "bundle.db"
    _make_db(live_path).close()

    # A bundle DB with only one shared table present.
    conn = sqlite3.connect(bundle_path)
    conn.execute("CREATE TABLE event_fights (fight_url TEXT PRIMARY KEY, winner TEXT)")
    conn.execute("INSERT INTO event_fights VALUES ('u/x', 'A')")
    conn.commit()
    conn.close()

    replaced = sync_shared_tables(live_path, bundle_path)
    # Column-intersection insert worked despite the narrower bundle schema.
    assert replaced["event_fights"] == 1
    check = sqlite3.connect(live_path)
    assert check.execute("SELECT winner FROM event_fights").fetchone()[0] == "A"
    check.close()


def test_sync_merges_totals_history_without_erasing_live_captures():
    tmp = Path(tempfile.mkdtemp())
    live_path, bundle_path = tmp / "live.db", tmp / "bundle.db"
    live = _make_db(live_path)
    bundle = _make_db(bundle_path)

    columns = (
        "snapshot_key, captured_at, source, fight_url, fighter_1, fighter_2, "
        "bookmaker_key, rounds_line, over_odds_american, under_odds_american"
    )
    live.execute(
        f"INSERT INTO totals_odds_snapshots ({columns}) "
        "VALUES ('live-only', 't2', 'api', 'f1', 'A', 'B', 'book-a', 2.5, -110, -110)"
    )
    bundle.execute(
        f"INSERT INTO totals_odds_snapshots ({columns}) "
        "VALUES ('bundle-only', 't1', 'api', 'f1', 'A', 'B', 'book-a', 1.5, -120, 100)"
    )
    live.commit()
    bundle.commit()
    live.close()
    bundle.close()

    replaced = sync_shared_tables(live_path, bundle_path)
    assert replaced["totals_odds_snapshots"] == 1

    check = sqlite3.connect(live_path)
    keys = {
        row[0]
        for row in check.execute(
            "SELECT snapshot_key FROM totals_odds_snapshots ORDER BY snapshot_key"
        )
    }
    assert keys == {"bundle-only", "live-only"}
    check.close()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all bundle-sync tests passed")
