from __future__ import annotations

"""
Adds leakage-safe prior cardio features to fighter_snapshots.csv.

Mirrors add_elo_features.py: each snapshot row gets the fighter's AVERAGE cardio
metrics over their PRIOR fights only (never the current fight, which is post-fight
information). The raw per-fight cardio metrics are dropped so they can't leak into
training.

Safe to re-run: existing cardio columns are removed and recomputed.

    python -m app.features.add_cardio_features
"""

from pathlib import Path

import pandas as pd

from app.features.cardio_features import (
    CARDIO_PER_FIGHT_COLUMNS,
    CARDIO_SNAPSHOT_COLUMNS,
    compute_fight_cardio_metrics,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

FIGHTER_SNAPSHOTS_CSV = PROCESSED_DATA_DIR / "fighter_snapshots.csv"
FIGHT_ROUND_STATS_CSV = RAW_DATA_DIR / "fight_round_stats.csv"


def clean_text(value) -> str:
    if pd.isna(value):
        return ""

    return " ".join(str(value).split())


def load_round_stats() -> pd.DataFrame:
    if not FIGHT_ROUND_STATS_CSV.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(FIGHT_ROUND_STATS_CSV)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def add_cardio_features(
    snapshots_df: pd.DataFrame,
    round_stats_df: pd.DataFrame,
) -> pd.DataFrame:
    df = snapshots_df.copy()

    # Make the function safe to re-run.
    drop_columns = [
        column
        for column in CARDIO_SNAPSHOT_COLUMNS + CARDIO_PER_FIGHT_COLUMNS
        if column in df.columns
    ]
    if drop_columns:
        df = df.drop(columns=drop_columns)

    df["_fight_url_key"] = df["fight_url"].map(clean_text)
    df["_fighter_key"] = df["fighter"].map(clean_text)
    df["_event_date_parsed"] = pd.to_datetime(df["event_date"], errors="coerce")

    per_fight = compute_fight_cardio_metrics(round_stats_df)

    if per_fight.empty:
        # No round data yet: add empty leakage-safe columns so downstream steps
        # (build_matchups, training) see a stable schema.
        for column in CARDIO_PER_FIGHT_COLUMNS:
            df[column] = pd.NA
    else:
        per_fight = per_fight.rename(
            columns={"fight_url": "_fight_url_key", "fighter": "_fighter_key"}
        )
        df = df.merge(per_fight, on=["_fight_url_key", "_fighter_key"], how="left")

    # Ensure numeric dtype so expanding().mean() can aggregate (merged/empty
    # columns can otherwise arrive as object dtype).
    for column in CARDIO_PER_FIGHT_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    # Chronological order so "prior" means strictly earlier fights.
    df = df.sort_values(
        by=["_event_date_parsed", "event_name", "fight_url", "fighter"],
        ascending=[True, True, True, True],
    ).reset_index(drop=True)

    for column in CARDIO_PER_FIGHT_COLUMNS:
        prior_column = f"prior_avg_{column}"
        df[prior_column] = (
            df.groupby("_fighter_key")[column]
            .transform(lambda series: series.expanding().mean().shift(1))
        )

    has_cardio = df["cardio_rounds_logged"].notna().astype(int)
    df["prior_cardio_fights"] = (
        has_cardio.groupby(df["_fighter_key"])
        .transform(lambda series: series.shift(1, fill_value=0).cumsum())
    )

    # Drop the per-fight (post-fight) values and helper keys.
    df = df.drop(
        columns=CARDIO_PER_FIGHT_COLUMNS
        + ["_fight_url_key", "_fighter_key", "_event_date_parsed"]
    )

    return df


def main() -> None:
    if not FIGHTER_SNAPSHOTS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {FIGHTER_SNAPSHOTS_CSV}. Run build_fighter_snapshots.py first."
        )

    print("Loading fighter snapshots...")
    snapshots_df = pd.read_csv(FIGHTER_SNAPSHOTS_CSV)

    round_stats_df = load_round_stats()
    print(f"Loaded {len(round_stats_df)} per-round rows from fight_round_stats.csv.")

    print("Adding prior cardio features...")
    updated_df = add_cardio_features(snapshots_df, round_stats_df)

    updated_df.to_csv(FIGHTER_SNAPSHOTS_CSV, index=False)

    coverage = int(updated_df["prior_avg_cardio_sig_output_slope"].notna().sum())
    print(f"Saved cardio features to: {FIGHTER_SNAPSHOTS_CSV}")
    print(f"Rows with a prior cardio average: {coverage} / {len(updated_df)}")


if __name__ == "__main__":
    main()
