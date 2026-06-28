"""
Tests for #17 (real reproducibility): the training-data hash + the model_runs
audit table (Phase 1, SQLite data layer).

Runs under pytest, or standalone:  python tests/test_model_runs.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.models.model_version import compute_training_data_hash  # noqa: E402
from app.repositories import model_runs_repository as repo  # noqa: E402


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


# --- training-data hash -------------------------------------------------------

def test_hash_is_deterministic_and_order_independent():
    df1 = pd.DataFrame({"a": [1, 2, 3], "b": [0.1, 0.2, 0.3], "c": ["x", "y", "z"]})
    df2 = df1.iloc[::-1].reset_index(drop=True)  # same rows, reversed order
    cols = ["a", "b", "c"]
    assert compute_training_data_hash(df1, cols) == compute_training_data_hash(df2, cols)


def test_hash_changes_when_a_value_changes():
    df1 = pd.DataFrame({"a": [1, 2, 3], "b": [0.1, 0.2, 0.3]})
    df2 = pd.DataFrame({"a": [1, 2, 4], "b": [0.1, 0.2, 0.3]})  # one cell differs
    assert compute_training_data_hash(df1, ["a", "b"]) != compute_training_data_hash(df2, ["a", "b"])


def test_hash_changes_with_column_set():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [0.1, 0.2, 0.3]})
    assert compute_training_data_hash(df, ["a", "b"]) != compute_training_data_hash(df, ["a"])


# --- model_runs audit table ---------------------------------------------------

def test_record_read_latest_and_count(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    assert repo.latest() is None
    assert repo.count() == 0

    repo.record_run({
        "trained_at": "t1", "model_version": "1.2", "recipe_hash": "abc",
        "best_model_name": "logistic_regression", "training_data_hash": "hash1",
        "training_rows": 100, "training_fights": 50, "feature_count": 380,
        "git_dirty": True,
    })
    repo.record_run({
        "trained_at": "t2", "model_version": "1.2", "recipe_hash": "abc",
        "best_model_name": "logistic_regression", "training_data_hash": "hash2",
        "training_rows": 110, "git_dirty": False,
    })

    assert repo.count() == 2

    latest = repo.latest()
    assert latest["trained_at"] == "t2"            # newest first
    assert latest["training_data_hash"] == "hash2"
    assert latest["git_dirty"] == 0                # bool coerced to 0/1

    df = repo.read_all_df()
    assert list(df["trained_at"]) == ["t2", "t1"]  # audit log, newest first
    assert int(df.iloc[0]["training_rows"]) == 110


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
