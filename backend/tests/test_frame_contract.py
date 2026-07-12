"""
Tests for the read-side missing-value contract (app/db/frame_contract.py):
TEXT columns come back as str-or-None (never NaN, never "nan"), numeric
columns stay numeric with NaN. Includes the repository round-trip that
reproduces the 2026-07-11 scoring crash input.

Runs under pytest, or standalone:  python tests/test_frame_contract.py
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

import app.db.connection as db_connection  # noqa: E402
from app.db.frame_contract import clean_text_cell, normalize_frame  # noqa: E402
from app.repositories import event_fights_repository  # noqa: E402


def test_clean_text_cell_missing_forms():
    assert clean_text_cell(None) is None
    assert clean_text_cell(float("nan")) is None
    assert clean_text_cell("") is None
    assert clean_text_cell("   ") is None
    assert clean_text_cell("nan") is None
    assert clean_text_cell("None") is None
    assert clean_text_cell("NULL") is None


def test_clean_text_cell_present_values():
    assert clean_text_cell("  KO/TKO  ") == "KO/TKO"
    assert clean_text_cell(3) == "3"
    assert clean_text_cell("Nando Nandez") == "Nando Nandez"


def test_normalize_frame_types():
    df = pd.DataFrame(
        {
            "name": ["Ada", float("nan"), "nan", None],
            "score": ["1.5", None, float("nan"), "junk"],
            "count": [1, None, "2", ""],
        }
    )
    spec = [("name", "TEXT"), ("score", "REAL"), ("count", "INTEGER")]
    out = normalize_frame(df, spec)

    assert list(out["name"]) == ["Ada", None, None, None]
    assert out["score"][0] == 1.5
    assert math.isnan(out["score"][3])  # junk coerces to NaN, stays numeric
    assert out["count"][0] == 1


def test_event_fights_round_trip_never_yields_nan_text():
    """Write a partial result row (the Friday-morning scrape state) and confirm
    the read side hands consumers None, not float NaN, in TEXT columns."""
    with tempfile.TemporaryDirectory() as tmp:
        db_connection.set_db_path(Path(tmp) / "app.db")

        event_fights_repository.replace_all(
            [
                {
                    "event_name": "UFC Test",
                    "fight_url": "http://f/1",
                    "fighter_1": "Ada",
                    "fighter_2": "Boz",
                    "winner": "Ada",
                    "method": float("nan"),  # result still posting
                    "round": None,
                }
            ]
        )

        df = event_fights_repository.read_all_df()
        row = df.iloc[0]

        assert row["method"] is None  # the 2026-07-11 crash input, now impossible
        assert row["winner"] == "Ada"
        assert isinstance(row["fighter_1"], str)
        # numeric missing stays NaN in a numeric column
        assert pd.isna(row["round"])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all frame-contract tests passed")
