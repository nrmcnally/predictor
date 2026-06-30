from __future__ import annotations

from app.db import schema
from app.repositories._snapshot_table import SnapshotTable

# Current market odds per upcoming fight. The odds refresh full-replaces the table.
_table = SnapshotTable("future_fight_odds", schema.FUTURE_FIGHT_ODDS_COLUMNS)

COLUMN_NAMES = _table.column_names

read_all_df = _table.read_all_df
replace_all = _table.replace_all
count = _table.count
