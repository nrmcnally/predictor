"""
Tests for cardio/fade features: per-fight metric math and leakage-safe averaging.

Runs under pytest, or standalone:  python tests/test_cardio_features.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.cardio_features import compute_fight_cardio_metrics  # noqa: E402
from app.features.add_cardio_features import add_cardio_features  # noqa: E402


def _round_row(fight_url, fighter, rnd, sig):
    return {"fight_url": fight_url, "fighter": fighter, "round": rnd, "sig_str_landed": sig}


def test_per_fight_metrics_slope_and_share():
    rounds = pd.DataFrame(
        [
            # Climber: output rises 10 -> 15 -> 20 across 3 rounds.
            _round_row("f1", "Climber", 1, 10),
            _round_row("f1", "Climber", 2, 15),
            _round_row("f1", "Climber", 3, 20),
            # Fader: output drops 20 -> 12 -> 4.
            _round_row("f1", "Fader", 1, 20),
            _round_row("f1", "Fader", 2, 12),
            _round_row("f1", "Fader", 3, 4),
            # One-round finish: no slope/share, just one round logged.
            _round_row("f2", "Finisher", 1, 5),
        ]
    )

    out = compute_fight_cardio_metrics(rounds).set_index("fighter")

    assert out.loc["Climber", "cardio_sig_output_slope"] == 5.0
    assert out.loc["Fader", "cardio_sig_output_slope"] == -8.0

    assert math.isclose(out.loc["Climber", "cardio_late_round_share"], 20 / 45, rel_tol=1e-9)
    assert math.isclose(out.loc["Fader", "cardio_late_round_share"], 4 / 36, rel_tol=1e-9)

    assert out.loc["Climber", "cardio_rounds_logged"] == 3.0

    finisher = out.loc["Finisher"]
    assert pd.isna(finisher["cardio_sig_output_slope"])
    assert pd.isna(finisher["cardio_late_round_share"])
    assert finisher["cardio_rounds_logged"] == 1.0


def test_prior_averaging_is_leakage_safe():
    # Fighter X across three chronological fights with known per-fight slopes:
    #   fA slope=+5, fB slope=-8, fC slope=+2
    snapshots = pd.DataFrame(
        [
            {"fight_url": "fA", "fighter": "X", "event_name": "A", "event_date": "January 01, 2020"},
            {"fight_url": "fB", "fighter": "X", "event_name": "B", "event_date": "January 01, 2021"},
            {"fight_url": "fC", "fighter": "X", "event_name": "C", "event_date": "January 01, 2022"},
        ]
    )
    rounds = pd.DataFrame(
        [
            _round_row("fA", "X", 1, 10), _round_row("fA", "X", 2, 15), _round_row("fA", "X", 3, 20),  # +5
            _round_row("fB", "X", 1, 20), _round_row("fB", "X", 2, 12), _round_row("fB", "X", 3, 4),   # -8
            _round_row("fC", "X", 1, 1), _round_row("fC", "X", 2, 3), _round_row("fC", "X", 3, 5),      # +2
        ]
    )

    out = add_cardio_features(snapshots, rounds).set_index("fight_url")

    # Raw per-fight (post-fight) columns must NOT survive into the snapshot.
    assert "cardio_sig_output_slope" not in out.columns
    assert "prior_avg_cardio_sig_output_slope" in out.columns

    # Earliest fight has no prior history.
    assert pd.isna(out.loc["fA", "prior_avg_cardio_sig_output_slope"])
    assert out.loc["fA", "prior_cardio_fights"] == 0

    # fB prior average uses only fA (+5).
    assert math.isclose(out.loc["fB", "prior_avg_cardio_sig_output_slope"], 5.0, rel_tol=1e-9)
    assert out.loc["fB", "prior_cardio_fights"] == 1

    # fC prior average uses fA and fB: mean(+5, -8) = -1.5.
    assert math.isclose(out.loc["fC", "prior_avg_cardio_sig_output_slope"], -1.5, rel_tol=1e-9)
    assert out.loc["fC", "prior_cardio_fights"] == 2


def test_handles_missing_round_data():
    snapshots = pd.DataFrame(
        [{"fight_url": "fA", "fighter": "X", "event_name": "A", "event_date": "January 01, 2020"}]
    )
    out = add_cardio_features(snapshots, pd.DataFrame())

    assert "prior_avg_cardio_sig_output_slope" in out.columns
    assert pd.isna(out.loc[0, "prior_avg_cardio_sig_output_slope"])
    assert out.loc[0, "prior_cardio_fights"] == 0


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
