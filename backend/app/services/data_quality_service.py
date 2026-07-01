from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.repositories import (
    event_fights_repository,
    future_cards_repository,
    future_fight_odds_repository,
    saved_predictions_repository,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

CURRENT_FIGHTER_FEATURES_CSV = PROCESSED_DATA_DIR / "current_fighter_features.csv"
EVENT_FIGHTS_CSV = RAW_DATA_DIR / "event_fights.csv"
FUTURE_FIGHT_ODDS_CSV = PROCESSED_DATA_DIR / "future_fight_odds.csv"
SAVED_CARD_PREDICTIONS_CSV = PROCESSED_DATA_DIR / "saved_card_predictions.csv"
UPCOMING_FIGHTS_CSV = RAW_DATA_DIR / "upcoming_fights.csv"


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


from app.utils.bool_parsing import count_bool_column, parse_bool  # noqa: E402


def numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype="float64")

    return pd.to_numeric(df[column], errors="coerce")


def missing_count(df: pd.DataFrame, column: str) -> int:
    if df.empty:
        return 0

    if column not in df.columns:
        return int(len(df))

    return int(df[column].apply(lambda value: clean_text(value) == "").sum())


def coverage(available: int, total: int) -> float | None:
    if total <= 0:
        return None

    return available / total


def percentage(value: float | None) -> str:
    if value is None:
        return "N/A"

    return f"{value * 100.0:.1f}%"


def extract_missing_fighter(row: pd.Series) -> str:
    raw_error = clean_text(row.get("error_json", ""))

    if raw_error:
        try:
            error_data = json.loads(raw_error)
            message = clean_text(error_data.get("message", ""))
        except (TypeError, ValueError, json.JSONDecodeError):
            message = raw_error

        match = re.search(r"Could not find fighter:\s*(.+)", message)

        if match:
            return clean_text(match.group(1))

    return ""


def summarize_current_fighters(df: pd.DataFrame) -> dict[str, Any]:
    prior_fights = numeric_column(df, "prior_fights")
    days_since_last_fight = numeric_column(df, "days_since_last_fight")

    total = int(len(df))
    inactive_over_3_years = int((days_since_last_fight > 1095).sum())
    low_sample_under_3 = int((prior_fights < 3).sum())
    low_sample_under_5 = int((prior_fights < 5).sum())

    return {
        "total": total,
        "inactive_over_3_years": inactive_over_3_years,
        "inactive_over_3_years_rate": coverage(inactive_over_3_years, total),
        "inactive_over_3_years_percentage": percentage(
            coverage(inactive_over_3_years, total)
        ),
        "low_sample_under_3_fights": low_sample_under_3,
        "low_sample_under_3_fights_rate": coverage(low_sample_under_3, total),
        "low_sample_under_3_fights_percentage": percentage(
            coverage(low_sample_under_3, total)
        ),
        "low_sample_under_5_fights": low_sample_under_5,
        "low_sample_under_5_fights_rate": coverage(low_sample_under_5, total),
        "low_sample_under_5_fights_percentage": percentage(
            coverage(low_sample_under_5, total)
        ),
        "missing_reach": missing_count(df, "reach_inches"),
        "missing_age": missing_count(df, "age_years"),
        "missing_height": missing_count(df, "height_inches"),
    }


def summarize_future_cards(
    upcoming_fights_df: pd.DataFrame,
    future_odds_df: pd.DataFrame,
) -> dict[str, Any]:
    upcoming_fights = int(len(upcoming_fights_df))
    odds_rows = int(len(future_odds_df))
    odds_available = count_bool_column(future_odds_df, "odds_available", True)

    return {
        "upcoming_fights": upcoming_fights,
        "future_odds_rows": odds_rows,
        "odds_available": odds_available,
        "odds_missing": max(0, odds_rows - odds_available),
        "odds_coverage": coverage(odds_available, odds_rows),
        "odds_coverage_percentage": percentage(coverage(odds_available, odds_rows)),
    }


def summarize_saved_predictions(df: pd.DataFrame) -> dict[str, Any]:
    total = int(len(df))
    prediction_available = count_bool_column(df, "prediction_available", True)
    odds_available = count_bool_column(df, "odds_available", True)

    missing_fighter_counts = Counter(
        fighter
        for _, row in df.iterrows()
        if not parse_bool(row.get("prediction_available", False))
        for fighter in [extract_missing_fighter(row)]
        if fighter
    )

    return {
        "saved_card_rows": total,
        "prediction_available": prediction_available,
        "prediction_unavailable": max(0, total - prediction_available),
        "prediction_coverage": coverage(prediction_available, total),
        "prediction_coverage_percentage": percentage(
            coverage(prediction_available, total)
        ),
        "odds_available": odds_available,
        "odds_missing": max(0, total - odds_available),
        "odds_coverage": coverage(odds_available, total),
        "odds_coverage_percentage": percentage(coverage(odds_available, total)),
        "top_unavailable_fighters": [
            {"fighter": fighter, "count": int(count)}
            for fighter, count in missing_fighter_counts.most_common(8)
        ],
    }


def summarize_historical_results(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "event_fights": 0,
            "clear_win_loss": 0,
            "draws": 0,
            "no_contests": 0,
            "dq_or_overturned": 0,
        }

    result_1 = df["result_1"].apply(clean_text).str.lower() if "result_1" in df else ""
    result_2 = df["result_2"].apply(clean_text).str.lower() if "result_2" in df else ""
    method = df["method"].apply(clean_text).str.lower() if "method" in df else ""

    clear_win_loss = int(
        (((result_1 == "win") & (result_2 == "loss")) |
         ((result_1 == "loss") & (result_2 == "win"))).sum()
    )
    draws = int(((result_1 == "draw") | (result_2 == "draw")).sum())
    no_contests = int(
        (
            result_1.eq("nc")
            | result_2.eq("nc")
            | method.str.contains("no contest|overturned", regex=True, na=False)
        ).sum()
    )
    dq_or_overturned = int(
        method.str.contains("dq|overturned", regex=True, na=False).sum()
    )

    return {
        "event_fights": int(len(df)),
        "clear_win_loss": clear_win_loss,
        "draws": draws,
        "no_contests": no_contests,
        "dq_or_overturned": dq_or_overturned,
    }


def summarize_data_freshness(event_fights_df: pd.DataFrame) -> dict[str, Any]:
    """How current is the underlying data: the most recent completed event we hold."""
    empty = {
        "latest_event_date": None,
        "latest_event_name": None,
        "days_since_latest_event": None,
    }

    if event_fights_df.empty or "event_date" not in event_fights_df.columns:
        return empty

    dates = pd.to_datetime(event_fights_df["event_date"], errors="coerce")

    if dates.notna().sum() == 0:
        return empty

    latest_idx = dates.idxmax()
    latest = dates.max()
    days_since = int((pd.Timestamp.now().normalize() - latest.normalize()).days)

    latest_name = ""
    if "event_name" in event_fights_df.columns:
        latest_name = clean_text(event_fights_df.loc[latest_idx, "event_name"])

    return {
        "latest_event_date": latest.date().isoformat(),
        "latest_event_name": latest_name or None,
        "days_since_latest_event": days_since,
    }


def build_data_quality_summary() -> dict[str, Any]:
    current_fighters_df = read_csv_or_empty(CURRENT_FIGHTER_FEATURES_CSV)
    event_fights_df = event_fights_repository.read_all_df()
    future_odds_df = future_fight_odds_repository.read_all_df()
    saved_predictions_df = saved_predictions_repository.read_all_df()
    upcoming_fights_df = future_cards_repository.read_upcoming_fights_df()

    return {
        "available": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_freshness": summarize_data_freshness(event_fights_df),
        "fighters": summarize_current_fighters(current_fighters_df),
        "future_cards": summarize_future_cards(upcoming_fights_df, future_odds_df),
        "saved_predictions": summarize_saved_predictions(saved_predictions_df),
        "historical_results": summarize_historical_results(event_fights_df),
    }
