"""
Tests for the centralized SQLite/pandas-safe boolean parser. The key regression: a
pandas/SQLite integer column comes back as 1.0/0.0, and the old per-service parsers
(`clean_text(v).lower() in {"true","1",...}`) parsed "1.0" as False, undercounting
availability/coverage/correctness across the app.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.utils.bool_parsing import count_bool_column, parse_bool  # noqa: E402


def test_truthy_representations():
    for value in [True, 1, 1.0, "1", "1.0", "true", "True", "YES", "y", "t",
                  np.True_, np.int64(1), np.float64(1.0)]:
        assert parse_bool(value) is True, value


def test_falsy_representations():
    for value in [False, 0, 0.0, "0", "0.0", "false", "False", "no", "n", "f",
                  np.False_, np.int64(0), np.float64(0.0)]:
        assert parse_bool(value) is False, value


def test_blank_and_null_use_default():
    for value in [None, "", "   ", float("nan"), np.nan, pd.NA]:
        assert parse_bool(value) is False        # default False
        assert parse_bool(value, None) is None   # tri-state


def test_unparseable_uses_default():
    assert parse_bool("maybe") is False
    assert parse_bool("maybe", None) is None


def test_count_bool_column_counts_float_ones():
    # The historical bug: 1.0/0.0 floats were counted as 0. Now three truthy rows.
    df = pd.DataFrame({"odds_available": [1.0, 0.0, 1.0, "true", "False", None]})
    assert count_bool_column(df, "odds_available", True) == 3
    assert count_bool_column(df, "missing_col", True) == 0
    assert count_bool_column(pd.DataFrame(), "odds_available", True) == 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all bool-parsing tests passed")
