from __future__ import annotations

from typing import Any

from app.db import connection, schema
from app.repositories._snapshot_table import SnapshotTable

# Future cards: upcoming events + their fights. The scraper full-replaces both on
# every refresh, so these are plain full-replace tables (read / replace_all / count).
_events = SnapshotTable("upcoming_events", schema.UPCOMING_EVENTS_COLUMNS)
_fights = SnapshotTable("upcoming_fights", schema.UPCOMING_FIGHTS_COLUMNS)

read_upcoming_events_df = _events.read_all_df
replace_upcoming_events = _events.replace_all
count_upcoming_events = _events.count

read_upcoming_fights_df = _fights.read_all_df
replace_upcoming_fights = _fights.replace_all
count_upcoming_fights = _fights.count


def get_upcoming_fight(fight_url: str) -> dict[str, Any] | None:
    """Fetch a single upcoming fight by its (stable) fight_url, or None if the bout
    is no longer on any upcoming card (e.g. cancelled or already moved to results)."""
    columns = ", ".join(_fights.column_names)
    with connection.transaction() as conn:
        schema.init_db(conn)
        row = conn.execute(
            f"SELECT {columns} FROM upcoming_fights WHERE fight_url = ?", (fight_url,)
        ).fetchone()
    return dict(row) if row is not None else None
