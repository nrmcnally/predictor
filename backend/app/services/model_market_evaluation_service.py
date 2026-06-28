from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.services.recent_card_service import (
    build_actual_result_lookup,
    load_actual_results,
    normalize_fight_url,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAVED_CARD_PREDICTIONS_CSV = PROJECT_ROOT / "data" / "processed" / "saved_card_predictions.csv"


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def normalize_name(value: Any) -> str:
    return clean_text(value).lower()


def parse_bool(value: Any) -> bool | None:
    if value is None or pd.isna(value):
        return None

    if isinstance(value, bool):
        return value

    text = clean_text(value).lower()

    if text in {"true", "1", "yes", "y"}:
        return True

    if text in {"false", "0", "no", "n"}:
        return False

    return None


def parse_probability(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None

    text = clean_text(value)

    if not text:
        return None

    try:
        if text.endswith("%"):
            return float(text.replace("%", "")) / 100.0

        number = float(text)

        if number > 1:
            return number / 100.0

        return number
    except ValueError:
        return None


def safe_mean(values: list[float]) -> float | None:
    cleaned = [value for value in values if value is not None and pd.notna(value)]

    if not cleaned:
        return None

    return sum(cleaned) / len(cleaned)


def format_percentage(value: float | None) -> str:
    if value is None:
        return "N/A"

    return f"{value * 100.0:.1f}%"


def load_saved_predictions() -> pd.DataFrame:
    if not SAVED_CARD_PREDICTIONS_CSV.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(SAVED_CARD_PREDICTIONS_CSV)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def add_actual_result_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    event_fights_df = load_actual_results()
    actual_lookup = build_actual_result_lookup(event_fights_df)

    for column in [
        "actual_winner",
        "actual_loser",
        "actual_method",
        "actual_round",
        "actual_time",
        "actual_outcome",
    ]:
        if column not in df.columns:
            df[column] = ""

    if "fight_url" not in df.columns or not actual_lookup:
        return df

    for index, row in df.iterrows():
        fight_url = normalize_fight_url(row.get("fight_url", ""))
        actual = actual_lookup.get(fight_url)

        if actual is None:
            continue

        df.at[index, "actual_winner"] = clean_text(actual.get("winner", ""))
        df.at[index, "actual_loser"] = clean_text(actual.get("loser", ""))
        df.at[index, "actual_method"] = clean_text(actual.get("method", ""))
        df.at[index, "actual_round"] = clean_text(actual.get("round", ""))
        df.at[index, "actual_time"] = clean_text(actual.get("time", ""))
        df.at[index, "actual_outcome"] = clean_text(actual.get("actual_outcome", ""))

    return df


def add_comparison_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    required_columns = [
        "predicted_winner",
        "actual_winner",
        "market_favorite",
    ]

    for column in required_columns:
        if column not in df.columns:
            df[column] = ""

    df["_predicted_winner_norm"] = df["predicted_winner"].apply(normalize_name)
    df["_actual_winner_norm"] = df["actual_winner"].apply(normalize_name)
    df["_market_favorite_norm"] = df["market_favorite"].apply(normalize_name)

    if "prediction_correct" in df.columns:
        df["_model_correct"] = df["prediction_correct"].apply(parse_bool)
    else:
        df["_model_correct"] = (
            df["_predicted_winner_norm"].ne("")
            & df["_actual_winner_norm"].ne("")
            & df["_predicted_winner_norm"].eq(df["_actual_winner_norm"])
        )

    if "market_correct" in df.columns:
        df["_market_correct"] = df["market_correct"].apply(parse_bool)
    else:
        df["_market_correct"] = (
            df["_market_favorite_norm"].ne("")
            & df["_actual_winner_norm"].ne("")
            & df["_market_favorite_norm"].eq(df["_actual_winner_norm"])
        )

    df["_model_market_agree"] = (
        df["_predicted_winner_norm"].ne("")
        & df["_market_favorite_norm"].ne("")
        & df["_predicted_winner_norm"].eq(df["_market_favorite_norm"])
    )

    if "confidence_percentage" in df.columns:
        df["_model_confidence"] = df["confidence_percentage"].apply(parse_probability)
    elif "predicted_winner_probability" in df.columns:
        df["_model_confidence"] = df["predicted_winner_probability"].apply(parse_probability)
    else:
        df["_model_confidence"] = None

    if "market_favorite_percentage" in df.columns:
        df["_market_confidence"] = df["market_favorite_percentage"].apply(parse_probability)
    elif "market_favorite_implied_probability" in df.columns:
        df["_market_confidence"] = df["market_favorite_implied_probability"].apply(parse_probability)
    else:
        df["_market_confidence"] = None

    return df


def build_summary(scored_df: pd.DataFrame) -> dict[str, Any]:
    total = len(scored_df)

    model_correct_count = int(scored_df["_model_correct"].eq(True).sum())
    market_correct_count = int(scored_df["_market_correct"].eq(True).sum())

    agreement_df = scored_df[scored_df["_model_market_agree"]].copy()
    disagreement_df = scored_df[~scored_df["_model_market_agree"]].copy()

    model_only_df = scored_df[
        scored_df["_model_correct"].eq(True) & scored_df["_market_correct"].eq(False)
    ]

    market_only_df = scored_df[
        scored_df["_model_correct"].eq(False) & scored_df["_market_correct"].eq(True)
    ]

    both_correct_df = scored_df[
        scored_df["_model_correct"].eq(True) & scored_df["_market_correct"].eq(True)
    ]

    both_wrong_df = scored_df[
        scored_df["_model_correct"].eq(False) & scored_df["_market_correct"].eq(False)
    ]

    agreement_accuracy = (
        float(agreement_df["_model_correct"].eq(True).mean())
        if len(agreement_df) > 0
        else None
    )

    model_disagreement_accuracy = (
        float(disagreement_df["_model_correct"].eq(True).mean())
        if len(disagreement_df) > 0
        else None
    )

    market_disagreement_accuracy = (
        float(disagreement_df["_market_correct"].eq(True).mean())
        if len(disagreement_df) > 0
        else None
    )

    model_accuracy = model_correct_count / total if total else None
    market_accuracy = market_correct_count / total if total else None

    return {
        "scored_fights": total,
        "model_correct": model_correct_count,
        "market_correct": market_correct_count,
        "model_accuracy": model_accuracy,
        "model_accuracy_percentage": format_percentage(model_accuracy),
        "market_accuracy": market_accuracy,
        "market_accuracy_percentage": format_percentage(market_accuracy),
        "model_edge_count": int(len(model_only_df)),
        "market_edge_count": int(len(market_only_df)),
        "both_correct_count": int(len(both_correct_df)),
        "both_wrong_count": int(len(both_wrong_df)),
        "agreement_count": int(len(agreement_df)),
        "disagreement_count": int(len(disagreement_df)),
        "agreement_accuracy": agreement_accuracy,
        "agreement_accuracy_percentage": format_percentage(agreement_accuracy),
        "model_disagreement_accuracy": model_disagreement_accuracy,
        "model_disagreement_accuracy_percentage": format_percentage(model_disagreement_accuracy),
        "market_disagreement_accuracy": market_disagreement_accuracy,
        "market_disagreement_accuracy_percentage": format_percentage(market_disagreement_accuracy),
        "average_model_confidence": safe_mean(scored_df["_model_confidence"].dropna().tolist()),
        "average_market_confidence": safe_mean(scored_df["_market_confidence"].dropna().tolist()),
    }


def row_to_fight(row: pd.Series) -> dict[str, Any]:
    model_confidence = row.get("_model_confidence")
    market_confidence = row.get("_market_confidence")

    return {
        "event_id": clean_text(row.get("event_id", "")),
        "event_name": clean_text(row.get("event_name", "")),
        "event_date": clean_text(row.get("event_date", "")),
        "fight_url": clean_text(row.get("fight_url", "")),
        "fighter_1": clean_text(row.get("fighter_1", "")),
        "fighter_2": clean_text(row.get("fighter_2", "")),
        "predicted_winner": clean_text(row.get("predicted_winner", "")),
        "actual_winner": clean_text(row.get("actual_winner", "")),
        "market_favorite": clean_text(row.get("market_favorite", "")),
        "model_correct": parse_bool(row.get("_model_correct")),
        "market_correct": parse_bool(row.get("_market_correct")),
        "model_market_agree": bool(row.get("_model_market_agree", False)),
        "confidence_label": clean_text(row.get("confidence_label", "")),
        "confidence_percentage": clean_text(row.get("confidence_percentage", "")),
        "model_confidence": model_confidence if pd.notna(model_confidence) else None,
        "model_confidence_percentage": format_percentage(model_confidence if pd.notna(model_confidence) else None),
        "market_confidence": market_confidence if pd.notna(market_confidence) else None,
        "market_confidence_percentage": format_percentage(market_confidence if pd.notna(market_confidence) else None),
        "market_favorite_percentage": clean_text(row.get("market_favorite_percentage", "")),
        "odds_bookmaker": clean_text(row.get("odds_bookmaker", "")),
        "saved_at": clean_text(row.get("saved_at", "")),
    }


def build_interesting_fights(scored_df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    rows = scored_df.copy()

    rows["_confidence_gap"] = (
        rows["_model_confidence"].fillna(0.0) - rows["_market_confidence"].fillna(0.0)
    ).abs()

    model_only = rows[
        rows["_model_correct"].eq(True) & rows["_market_correct"].eq(False)
    ].sort_values("_confidence_gap", ascending=False)

    market_only = rows[
        rows["_model_correct"].eq(False) & rows["_market_correct"].eq(True)
    ].sort_values("_confidence_gap", ascending=False)

    disagreements = rows[~rows["_model_market_agree"]].sort_values(
        "_confidence_gap",
        ascending=False,
    )

    both_wrong = rows[
        rows["_model_correct"].eq(False) & rows["_market_correct"].eq(False)
    ].sort_values("_confidence_gap", ascending=False)

    return {
        "model_only_wins": [row_to_fight(row) for _, row in model_only.head(10).iterrows()],
        "market_only_wins": [row_to_fight(row) for _, row in market_only.head(10).iterrows()],
        "biggest_disagreements": [row_to_fight(row) for _, row in disagreements.head(10).iterrows()],
        "both_wrong": [row_to_fight(row) for _, row in both_wrong.head(10).iterrows()],
    }


def build_event_breakdown(scored_df: pd.DataFrame) -> list[dict[str, Any]]:
    if scored_df.empty or "event_name" not in scored_df.columns:
        return []

    events = []

    for event_name, event_rows in scored_df.groupby("event_name", dropna=False):
        event_summary = build_summary(event_rows)

        events.append(
            {
                "event_name": clean_text(event_name),
                "event_date": clean_text(event_rows["event_date"].iloc[0]) if "event_date" in event_rows.columns else "",
                "scored_fights": event_summary["scored_fights"],
                "model_accuracy_percentage": event_summary["model_accuracy_percentage"],
                "market_accuracy_percentage": event_summary["market_accuracy_percentage"],
                "model_correct": event_summary["model_correct"],
                "market_correct": event_summary["market_correct"],
                "agreement_count": event_summary["agreement_count"],
                "disagreement_count": event_summary["disagreement_count"],
                "_event_date_parsed": pd.to_datetime(
                    event_rows["event_date"].iloc[0],
                    errors="coerce",
                )
                if "event_date" in event_rows.columns
                else pd.NaT,
            }
        )

    events.sort(
        key=lambda row: (
            pd.Timestamp.min
            if pd.isna(row.get("_event_date_parsed"))
            else row["_event_date_parsed"]
        ),
        reverse=True,
    )

    for event in events:
        event.pop("_event_date_parsed", None)

    return events


def build_model_market_evaluation() -> dict[str, Any]:
    df = load_saved_predictions()

    if df.empty:
        return {
            "available": False,
            "message": "No saved card predictions found.",
            "summary": {},
            "event_breakdown": [],
            "interesting_fights": {},
        }

    df = add_actual_result_columns(df)
    df = add_comparison_columns(df)

    result_prediction_df = df[
        df["_actual_winner_norm"].ne("")
        & df["_predicted_winner_norm"].ne("")
    ].copy()

    scored_df = result_prediction_df[
        result_prediction_df["_market_favorite_norm"].ne("")
    ].copy()

    if "odds_available" in scored_df.columns:
        odds_available = scored_df["odds_available"].apply(parse_bool)
        scored_df = scored_df[odds_available.eq(True)].copy()

    all_scored_prediction_fights = int(len(result_prediction_df))
    scored_with_market_odds = int(len(scored_df))
    excluded_without_market_odds = max(
        0,
        all_scored_prediction_fights - scored_with_market_odds,
    )

    if scored_df.empty:
        return {
            "available": False,
            "message": (
                "Saved predictions exist, but no fights have actual results plus saved market odds yet."
            ),
            "summary": {
                "saved_rows": int(len(df)),
                "all_scored_prediction_fights": all_scored_prediction_fights,
                "scored_with_market_odds": scored_with_market_odds,
                "excluded_without_market_odds": excluded_without_market_odds,
            },
            "event_breakdown": [],
            "interesting_fights": {},
        }

    summary = build_summary(scored_df)
    summary["all_scored_prediction_fights"] = all_scored_prediction_fights
    summary["scored_with_market_odds"] = scored_with_market_odds
    summary["excluded_without_market_odds"] = excluded_without_market_odds

    return {
        "available": True,
        "message": "Model-vs-market evaluation built from saved Recent Cards odds snapshots.",
        "summary": summary,
        "event_breakdown": build_event_breakdown(scored_df),
        "interesting_fights": build_interesting_fights(scored_df),
        "notes": [
            "Market evaluation only includes fights where odds were saved before the event.",
            "Betting odds are comparison-only and are not used as model training features.",
            "Small samples can swing heavily, especially right after adding odds snapshots.",
        ],
    }
