from __future__ import annotations

"""
Cardio / late-fade features derived from per-round fight stats.

The fight-totals data can't tell whether a fighter's output held up or collapsed in
later rounds. The per-round table (fight_round_stats.csv) can. For each fighter-fight
we compute a small set of pace/fade metrics:

    cardio_sig_output_slope   slope of significant strikes landed across rounds.
                              > 0 means output rose late (good cardio / strong
                              finisher); < 0 means it dropped off (faded).
    cardio_late_round_share   share of total significant strikes landed in rounds 3+
                              (only defined for fights that reached round 3).
    cardio_rounds_logged      number of rounds the fighter has data for (deep-water
                              experience proxy).

These are PER-FIGHT values that describe what happened in that fight, so they are
post-fight information. They must never be used directly as model features — only
their leakage-safe prior averages (see add_cardio_features.py) may be.
"""

from typing import Any

import numpy as np
import pandas as pd


CARDIO_PER_FIGHT_COLUMNS = [
    "cardio_sig_output_slope",
    "cardio_late_round_share",
    "cardio_rounds_logged",
]

# Leakage-safe snapshot features (prior averages + reliability count).
CARDIO_SNAPSHOT_COLUMNS = [
    "prior_avg_cardio_sig_output_slope",
    "prior_avg_cardio_late_round_share",
    "prior_avg_cardio_rounds_logged",
    "prior_cardio_fights",
]


def clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""

    return " ".join(str(value).split())


def _cardio_for_one_fight(rounds: np.ndarray, sig: np.ndarray) -> dict[str, float | None]:
    """rounds and sig are aligned arrays for a single fighter in a single fight."""
    order = np.argsort(rounds)
    rounds = rounds[order].astype(float)
    sig = sig[order].astype(float)

    rounds_logged = float(len(sig))

    slope: float | None = None
    if len(sig) >= 2:
        round_mean = rounds.mean()
        variance = ((rounds - round_mean) ** 2).sum()
        if variance > 0:
            slope = float(((rounds - round_mean) * (sig - sig.mean())).sum() / variance)

    late_share: float | None = None
    total = sig.sum()
    if rounds.max() >= 3 and total > 0:
        late_share = float(sig[rounds >= 3].sum() / total)

    return {
        "cardio_sig_output_slope": slope,
        "cardio_late_round_share": late_share,
        "cardio_rounds_logged": rounds_logged,
    }


def compute_fight_cardio_metrics(round_stats_df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns one row per (fight_url, fighter) with the per-fight cardio metrics.
    """
    empty = pd.DataFrame(columns=["fight_url", "fighter", *CARDIO_PER_FIGHT_COLUMNS])

    if round_stats_df is None or round_stats_df.empty:
        return empty

    df = round_stats_df.copy()

    required = {"fight_url", "fighter", "round", "sig_str_landed"}
    if not required.issubset(df.columns):
        return empty

    df["fight_url"] = df["fight_url"].map(clean_text)
    df["fighter"] = df["fighter"].map(clean_text)
    df["round"] = pd.to_numeric(df["round"], errors="coerce")
    df["sig_str_landed"] = pd.to_numeric(df["sig_str_landed"], errors="coerce")

    df = df[df["round"].notna() & df["sig_str_landed"].notna()]

    if df.empty:
        return empty

    records: list[dict[str, Any]] = []

    for (fight_url, fighter), group in df.groupby(["fight_url", "fighter"], sort=False):
        metrics = _cardio_for_one_fight(
            group["round"].to_numpy(),
            group["sig_str_landed"].to_numpy(),
        )
        records.append({"fight_url": fight_url, "fighter": fighter, **metrics})

    return pd.DataFrame(records)


def build_current_cardio_lookup(round_stats_df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-fighter "as of now" cardio averages over ALL their fights, for the current
    fighter features used at prediction time. One row per fighter.
    """
    per_fight = compute_fight_cardio_metrics(round_stats_df)

    if per_fight.empty:
        return pd.DataFrame(columns=["fighter", *CARDIO_SNAPSHOT_COLUMNS])

    grouped = per_fight.groupby("fighter")

    lookup = grouped[CARDIO_PER_FIGHT_COLUMNS].mean().reset_index()
    lookup = lookup.rename(
        columns={column: f"prior_avg_{column}" for column in CARDIO_PER_FIGHT_COLUMNS}
    )

    lookup["prior_cardio_fights"] = (
        grouped["cardio_rounds_logged"].count().reset_index(drop=True)
    )

    return lookup
