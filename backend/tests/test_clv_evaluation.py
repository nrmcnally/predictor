"""
Tests for closing-line-value (CLV) computation.

Runs under pytest, or standalone:  python tests/test_clv_evaluation.py
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.services.clv_evaluation_service as clv  # noqa: E402


def _write(tmp, name, rows):
    path = Path(tmp) / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_clv_beat_close_and_average(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()

    # Fight 1: picked A (fighter_1). Opening 0.40 -> closing 0.55 = line moved TO us (+0.15).
    # Fight 2: picked D (fighter_2). Opening 0.60 -> closing 0.50 = line moved AWAY (-0.10).
    track = _write(tmp, "track.csv", [
        {"fight_url": "f1", "fighter_1": "A", "fighter_2": "B",
         "opening_fighter_1_probability": 0.40, "opening_fighter_2_probability": 0.60,
         "closing_fighter_1_probability": 0.55, "closing_fighter_2_probability": 0.45,
         "capture_count": 2},
        {"fight_url": "f2", "fighter_1": "C", "fighter_2": "D",
         "opening_fighter_1_probability": 0.40, "opening_fighter_2_probability": 0.60,
         "closing_fighter_1_probability": 0.50, "closing_fighter_2_probability": 0.50,
         "capture_count": 2},
    ])
    saved = _write(tmp, "saved.csv", [
        {"fight_url": "f1", "predicted_winner": "A", "prediction_available": True},
        {"fight_url": "f2", "predicted_winner": "D", "prediction_available": True},
    ])
    results = _write(tmp, "results.csv", [
        {"fight_url": "f1", "winner": "A"},
        {"fight_url": "f2", "winner": "C"},
    ])

    clv.FIGHT_ODDS_TRACK_CSV = track
    clv.SAVED_CARD_PREDICTIONS_CSV = saved
    clv.EVENT_FIGHTS_CSV = results

    out = clv.build_clv_evaluation()

    assert out["available"] is True
    assert out["scored_clv_fights"] == 2
    assert out["beat_close_count"] == 1                       # only fight 1 beat the close
    assert math.isclose(out["beat_close_rate"], 0.5, rel_tol=1e-9)
    assert math.isclose(out["avg_clv_points"], (0.15 - 0.10) / 2, rel_tol=1e-9)  # +0.025


def test_single_capture_has_no_clv_signal(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    track = _write(tmp, "track1.csv", [
        {"fight_url": "f1", "fighter_1": "A", "fighter_2": "B",
         "opening_fighter_1_probability": 0.50, "opening_fighter_2_probability": 0.50,
         "closing_fighter_1_probability": 0.50, "closing_fighter_2_probability": 0.50,
         "capture_count": 1},
    ])
    saved = _write(tmp, "saved1.csv", [
        {"fight_url": "f1", "predicted_winner": "A", "prediction_available": True},
    ])
    results = _write(tmp, "results1.csv", [{"fight_url": "f1", "winner": "A"}])

    clv.FIGHT_ODDS_TRACK_CSV = track
    clv.SAVED_CARD_PREDICTIONS_CSV = saved
    clv.EVENT_FIGHTS_CSV = results

    out = clv.build_clv_evaluation()
    assert out["available"] is False  # one capture -> opening == closing -> no CLV yet


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
