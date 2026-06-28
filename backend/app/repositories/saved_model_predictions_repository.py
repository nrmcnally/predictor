from __future__ import annotations

from app.db import schema
from app.repositories._snapshot_table import SnapshotTable

# saved_model_predictions: one prospective snapshot per model per fight; the latest
# snapshot per card is kept (replaced atomically per event).
_table = SnapshotTable("saved_model_predictions", schema.SAVED_MODEL_COLUMNS)

COLUMN_NAMES = _table.column_names

read_all_df = _table.read_all_df
replace_card = _table.replace_card
import_rows = _table.import_rows
count = _table.count
