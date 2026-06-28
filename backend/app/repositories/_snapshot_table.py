from __future__ import annotations

import math
from typing import Any

import pandas as pd

from app.db import connection, schema

# Shared repository for a wide "replace-by-event_id" prediction-snapshot table
# (typed columns from a canonical spec). Used by both saved_card_predictions and
# saved_model_predictions, which differ only in table name + column set.


class SnapshotTable:
    def __init__(self, table_name: str, columns: list[tuple[str, str]]):
        self.table = table_name
        self.column_names = [name for name, _ in columns]
        self.column_types = dict(columns)

    def _coerce(self, name: str, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, float) and math.isnan(value):
            return None

        sql_type = self.column_types[name]

        if sql_type == "REAL":
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        if sql_type == "INTEGER":
            if isinstance(value, bool):
                return 1 if value else 0
            text = str(value).strip().lower()
            if text in {"true", "yes", "y"}:
                return 1
            if text in {"false", "no", "n"}:
                return 0
            if text == "":
                return None
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return None

        # TEXT — keep empty strings as-is (consumers distinguish "" from NULL).
        return str(value)

    def _row_values(self, row: dict[str, Any]) -> list[Any]:
        return [self._coerce(name, row.get(name)) for name in self.column_names]

    def read_all_df(self) -> pd.DataFrame:
        columns = ", ".join(self.column_names)
        with connection.transaction() as conn:
            schema.init_db(conn)
            rows = conn.execute(f"SELECT {columns} FROM {self.table}").fetchall()

        if not rows:
            return pd.DataFrame(columns=self.column_names)

        return pd.DataFrame([dict(row) for row in rows], columns=self.column_names)

    def replace_card(self, event_id: str, rows: list[dict[str, Any]]) -> int:
        """Atomically replace all rows for one event (delete + insert in one txn)."""
        columns = ", ".join(self.column_names)
        placeholders = ", ".join(["?"] * len(self.column_names))

        with connection.transaction() as conn:
            schema.init_db(conn)
            conn.execute(f"DELETE FROM {self.table} WHERE event_id = ?", (str(event_id),))
            for row in rows:
                conn.execute(
                    f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
                    self._row_values(row),
                )
        return len(rows)

    def import_rows(self, rows: list[dict[str, Any]]) -> int:
        """Full replace of the table (one-time CSV import)."""
        columns = ", ".join(self.column_names)
        placeholders = ", ".join(["?"] * len(self.column_names))

        with connection.transaction() as conn:
            schema.init_db(conn)
            conn.execute(f"DELETE FROM {self.table}")
            for row in rows:
                conn.execute(
                    f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
                    self._row_values(row),
                )
        return len(rows)

    def count(self) -> int:
        with connection.transaction() as conn:
            schema.init_db(conn)
            return int(conn.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0])
