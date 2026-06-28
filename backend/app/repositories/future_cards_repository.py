from __future__ import annotations

from app.db import schema
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
