"""
Regression tests for the walk-forward backtest fold logic.

Runs under pytest, or standalone:  python tests/test_walk_forward.py
(Standalone mode requires no extra dependencies.)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Make `app` importable whether run via pytest or directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.walk_forward_evaluation_service import (  # noqa: E402
    _summarize,
    build_fold_plan,
)


def _synthetic_matchups() -> pd.DataFrame:
    """Two mirrored rows per fight, ~100 fights per year across several years."""
    rows = []
    for year in range(2018, 2025):
        for fight_index in range(100):
            fight_url = f"http://x/{year}-{fight_index}"
            for orientation in (0, 1):
                rows.append(
                    {
                        "fight_url": fight_url,
                        "event_date_parsed": pd.Timestamp(f"{year}-06-15"),
                        "year": year,
                        "target": orientation,
                    }
                )
    return pd.DataFrame(rows)


def test_folds_are_expanding_and_out_of_sample():
    df = _synthetic_matchups()
    folds = build_fold_plan(df, n_folds=4, min_test_fights=50, min_train_fights=100)

    # Most recent 4 eligible years.
    assert [f["test_year"] for f in folds] == [2021, 2022, 2023, 2024]

    # Train window must only contain fights strictly before the test year, and
    # it must grow each fold (expanding window).
    train_counts = [f["train_fights"] for f in folds]
    assert train_counts == sorted(train_counts)
    assert all(count > 0 for count in train_counts)
    assert folds[0]["train_fights"] == 300  # 2018, 2019, 2020 -> 3 * 100


def test_min_train_fights_filters_early_years():
    df = _synthetic_matchups()
    # Require 250 prior fights -> first scorable year is 2021 (300 priors).
    folds = build_fold_plan(df, n_folds=10, min_test_fights=50, min_train_fights=250)
    assert min(f["test_year"] for f in folds) == 2021


def test_min_test_fights_excludes_thin_years():
    df = _synthetic_matchups()
    # No year has 500 fights, so nothing is eligible.
    folds = build_fold_plan(df, n_folds=10, min_test_fights=500, min_train_fights=10)
    assert folds == []


def test_summarize_confidence_interval():
    summary = _summarize([0.6, 0.62, 0.58, 0.64])
    assert summary["n"] == 4
    assert abs(summary["mean"] - 0.61) < 1e-9
    assert summary["ci95"] > 0

    empty = _summarize([None, float("nan")])
    assert empty["mean"] is None
    assert empty["n"] == 0


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
