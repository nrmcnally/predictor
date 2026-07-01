from __future__ import annotations

from typing import Any

import pandas as pd

# One SQLite/pandas-safe boolean parser for the whole app. Historically this logic was
# copy-pasted into ~7 services as `clean_text(v).lower() in {"true","1",...}`, which
# WRONGLY parses a pandas/SQLite float `1.0` (stringified to "1.0") as False — silently
# undercounting availability/coverage/correctness. This handles every representation.

_TRUE_TOKENS = {"true", "1", "yes", "y", "t"}
_FALSE_TOKENS = {"false", "0", "no", "n", "f"}


def parse_bool(value: Any, default: bool | None = False) -> bool | None:
    """Parse a boolean from any DB/CSV/pandas representation.

    Handles Python & NumPy bools, ints, floats (incl. 1.0/0.0), their string forms
    ("1", "0", "1.0", "true", "false", "yes", "no", "t", "f"), blanks, None, and NaN.
    Returns ``default`` for blank/null/unparseable values — pass ``default=None`` for a
    tri-state (unknown vs False) result.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    # NaN / NA (Python float nan, numpy nan, pd.NA) — never a real True/False.
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass

    if isinstance(value, (int, float)):
        return bool(value != 0)  # native bool, not numpy bool_ (JSON-safe)

    text = str(value).strip().lower()
    if text in _TRUE_TOKENS:
        return True
    if text in _FALSE_TOKENS:
        return False
    if text == "":
        return default
    try:
        return float(text) != 0.0  # numeric strings like "1.0" / "0.0"
    except ValueError:
        return default


def count_bool_column(df: pd.DataFrame, column: str, expected: bool = True) -> int:
    """Count rows in ``df`` where ``column`` parses (bool-safely) to ``expected``."""
    if df is None or df.empty or column not in df.columns:
        return 0
    return int((df[column].apply(lambda value: parse_bool(value)) == expected).sum())
