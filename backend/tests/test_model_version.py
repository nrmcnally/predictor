"""
Tests for the recipe-hash logic that drives "same vs older generation".

Runs under pytest, or standalone:  python tests/test_model_version.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.model_version import (  # noqa: E402
    MODEL_VERSION,
    compute_recipe_hash,
    estimate_version_for_date,
)


def test_recipe_hash_is_order_stable():
    a = compute_recipe_hash(["a", "b", "c"], ["weight_class"], "logistic_regression", "none")
    b = compute_recipe_hash(["c", "a", "b"], ["weight_class"], "logistic_regression", "none")
    assert a == b  # feature order must not change the hash (it's sorted)


def test_recipe_hash_changes_on_meaningful_change():
    base = compute_recipe_hash(["a", "b"], ["weight_class"], "logistic_regression", "none")

    assert compute_recipe_hash(["a", "b", "c"], ["weight_class"], "logistic_regression", "none") != base  # new feature
    assert compute_recipe_hash(["a", "b"], ["weight_class"], "xgboost", "none") != base                   # model type
    assert compute_recipe_hash(["a", "b"], ["weight_class"], "logistic_regression", "sigmoid") != base     # calibration


def test_model_version_is_major_minor():
    major, _, minor = MODEL_VERSION.partition(".")
    assert major.isdigit() and minor.isdigit()  # e.g. "1.2"


def test_estimate_version_from_save_date():
    assert estimate_version_for_date("2026-05-10") == "1.0"        # at/before the start
    assert estimate_version_for_date("2026-06-15T10:51:29") == "1.1"  # pre-SoS era
    assert estimate_version_for_date("2026-06-27") == "1.2"        # current era
    assert estimate_version_for_date("") == ""                    # no date -> unknown


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
