"""
Regression test for the single most important correctness property: fighter
snapshots must be built from PRIOR fights only (no leakage of the current/future).

Runs under pytest, or standalone:  python tests/test_snapshot_leakage.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.build_fighter_snapshots import build_fighter_snapshots  # noqa: E402


def _fight(fight_url, date, fighter, opponent, result):
    return {
        "fight_url": fight_url,
        "event_name": "Event",
        "event_date": date,
        "weight_class": "Lightweight",
        "method": "Decision",
        "round": 3,
        "time": "5:00",
        "fighter": fighter,
        "opponent": opponent,
        "result": result,
        "kd": 0,
        "sig_str_landed": 10,
        "sig_str_attempted": 20,
        "total_str_landed": 12,
        "total_str_attempted": 25,
        "td_landed": 0,
        "td_attempted": 0,
        "sub_att": 0,
        "ctrl_seconds": 0,
        "head_landed": 5,
        "head_attempted": 10,
        "body_landed": 3,
        "body_attempted": 5,
        "leg_landed": 2,
        "leg_attempted": 3,
        "distance_landed": 8,
        "distance_attempted": 15,
        "clinch_landed": 1,
        "clinch_attempted": 2,
        "ground_landed": 1,
        "ground_attempted": 3,
    }


def test_snapshots_use_only_prior_fights():
    # Fighter A: beats B (2020), loses to C (2021), beats D (2022).
    rows = [
        _fight("f1", "January 01, 2020", "A", "B", "win"),
        _fight("f1", "January 01, 2020", "B", "A", "loss"),
        _fight("f2", "January 01, 2021", "A", "C", "loss"),
        _fight("f2", "January 01, 2021", "C", "A", "win"),
        _fight("f3", "January 01, 2022", "A", "D", "win"),
        _fight("f3", "January 01, 2022", "D", "A", "loss"),
    ]

    snapshots = build_fighter_snapshots(pd.DataFrame(rows))
    a = snapshots[snapshots["fighter"] == "A"].sort_values("event_date").reset_index(drop=True)

    # Fight 1: no prior history at all.
    assert a.loc[0, "prior_fights"] == 0
    assert pd.isna(a.loc[0, "prior_win_rate"])

    # Fight 2: exactly one prior fight (the win over B), nothing from this fight.
    assert a.loc[1, "prior_fights"] == 1
    assert a.loc[1, "prior_wins"] == 1
    assert a.loc[1, "prior_win_rate"] == 1.0  # 1/1, the loss to C is NOT counted

    # Fight 3: two prior fights (1 win, 1 loss); this fight's win is excluded.
    assert a.loc[2, "prior_fights"] == 2
    assert a.loc[2, "prior_wins"] == 1
    assert a.loc[2, "prior_losses"] == 1
    assert a.loc[2, "prior_win_rate"] == 0.5


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
