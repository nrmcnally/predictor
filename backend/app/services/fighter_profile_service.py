from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.fighter_image_service import get_fighter_image_data, load_fighter_image_lookup


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

FIGHT_STATS_CSV = RAW_DATA_DIR / "fight_stats.csv"
CURRENT_FIGHTER_FEATURES_CSV = PROCESSED_DATA_DIR / "current_fighter_features.csv"
FIGHTER_SNAPSHOTS_CSV = PROCESSED_DATA_DIR / "fighter_snapshots.csv"


WEIGHT_CLASS_COLUMNS = [
    "weight_class",
    "current_weight_class",
    "recent_weight_class",
    "common_weight_class",
    "most_common_weight_class",
    "last_weight_class",
]


RANKING_METRICS = [
    {
        "key": "prior_elo",
        "label": "Elo rating",
        "category": "Overall",
        "direction": "high",
    },
    {
        "key": "prior_win_rate",
        "label": "UFC win rate",
        "category": "Overall",
        "direction": "high",
    },
    {
        "key": "recent_5_win_rate",
        "label": "Recent 5 fight win rate",
        "category": "Overall",
        "direction": "high",
    },
    {
        "key": "prior_finish_win_rate",
        "label": "Finish win rate",
        "category": "Overall",
        "direction": "high",
    },
    {
        "key": "avg_sig_str_differential_per_15",
        "label": "Striking differential per 15",
        "category": "Striking",
        "direction": "high",
    },
    {
        "key": "avg_sig_str_landed_per_15",
        "label": "Significant strikes landed per 15",
        "category": "Striking",
        "direction": "high",
    },
    {
        "key": "avg_sig_str_absorbed_per_15",
        "label": "Fewest significant strikes absorbed per 15",
        "category": "Striking defense",
        "direction": "low",
    },
    {
        "key": "avg_sig_str_accuracy",
        "label": "Significant strike accuracy",
        "category": "Striking",
        "direction": "high",
    },
    {
        "key": "avg_sig_str_defense",
        "label": "Significant strike defense",
        "category": "Striking defense",
        "direction": "high",
    },
    {
        "key": "avg_kd_for",
        "label": "Knockdowns scored",
        "category": "Striking",
        "direction": "high",
    },
    {
        "key": "avg_td_landed_per_15",
        "label": "Takedowns landed per 15",
        "category": "Grappling",
        "direction": "high",
    },
    {
        "key": "avg_td_accuracy",
        "label": "Takedown accuracy",
        "category": "Grappling",
        "direction": "high",
    },
    {
        "key": "avg_td_defense",
        "label": "Takedown defense",
        "category": "Grappling defense",
        "direction": "high",
    },
    {
        "key": "avg_ctrl_seconds_per_15",
        "label": "Control time per 15",
        "category": "Grappling",
        "direction": "high",
    },
    {
        "key": "avg_sub_att_per_15",
        "label": "Submission attempts per 15",
        "category": "Grappling",
        "direction": "high",
    },
]


PROFILE_STAT_KEYS = [
    "prior_elo",
    "prior_peak_elo",
    "prior_fights",
    "prior_wins",
    "prior_losses",
    "prior_unscored_results",
    "prior_win_rate",
    "recent_5_win_rate",
    "prior_finish_win_rate",
    "height_inches",
    "reach_inches",
    "reach_minus_height_inches",
    "age_years",
    "avg_sig_str_differential_per_15",
    "avg_sig_str_landed_per_15",
    "avg_sig_str_absorbed_per_15",
    "avg_sig_str_accuracy",
    "avg_sig_str_defense",
    "avg_td_landed_per_15",
    "avg_td_accuracy",
    "avg_td_defense",
    "avg_ctrl_seconds_per_15",
    "avg_sub_att_per_15",
]


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def normalize_name(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def safe_number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if math.isnan(number) or math.isinf(number):
        return None

    return number


def safe_int(value: Any) -> int | None:
    number = safe_number(value)

    if number is None:
        return None

    return int(round(number))


def format_stat_value(key: str, value: Any) -> str:
    number = safe_number(value)

    if number is None:
        return "N/A"

    if key in {"prior_elo", "prior_peak_elo"}:
        return f"{number:.0f}"

    if key in {"prior_fights", "prior_wins", "prior_losses", "prior_unscored_results"}:
        return f"{number:.0f}"

    if "rate" in key or "accuracy" in key or "defense" in key:
        if abs(number) <= 1.0:
            return f"{number * 100.0:.1f}%"

        return f"{number:.1f}%"

    if key in {"height_inches", "reach_inches", "reach_minus_height_inches"}:
        return f"{number:.1f} in"

    if key == "age_years":
        return f"{number:.1f}"

    if "seconds" in key:
        return f"{number:.1f} sec"

    return f"{number:.2f}"


def load_current_fighter_features() -> pd.DataFrame:
    if not CURRENT_FIGHTER_FEATURES_CSV.exists():
        raise FileNotFoundError(f"Missing {CURRENT_FIGHTER_FEATURES_CSV}")

    df = pd.read_csv(CURRENT_FIGHTER_FEATURES_CSV)

    if "fighter" not in df.columns:
        raise ValueError("current_fighter_features.csv is missing fighter column.")

    df = df.copy()
    df["_fighter_normalized"] = df["fighter"].apply(normalize_name)

    return df


def load_fight_stats() -> pd.DataFrame:
    if not FIGHT_STATS_CSV.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(FIGHT_STATS_CSV)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()

    if "fighter" in df.columns:
        df = df.copy()
        df["_fighter_normalized"] = df["fighter"].apply(normalize_name)

    return df


def get_weight_class_from_row(row: pd.Series) -> str:
    for column in WEIGHT_CLASS_COLUMNS:
        if column in row.index:
            value = clean_text(row.get(column, ""))

            if value:
                return value

    return ""


def derive_weight_class_lookup(fight_stats_df: pd.DataFrame) -> dict[str, str]:
    if fight_stats_df.empty:
        return {}

    if "fighter" not in fight_stats_df.columns or "weight_class" not in fight_stats_df.columns:
        return {}

    lookup = {}

    for fighter_name, fighter_rows in fight_stats_df.groupby("_fighter_normalized"):
        weight_classes = [
            clean_text(value)
            for value in fighter_rows["weight_class"].dropna().astype(str)
            if clean_text(value)
        ]

        if not weight_classes:
            continue

        lookup[fighter_name] = Counter(weight_classes).most_common(1)[0][0]

    return lookup


def add_profile_weight_classes(
    features_df: pd.DataFrame,
    fight_stats_df: pd.DataFrame,
) -> pd.DataFrame:
    weight_lookup = derive_weight_class_lookup(fight_stats_df)

    features_df = features_df.copy()

    profile_weight_classes = []

    for _, row in features_df.iterrows():
        weight_class = get_weight_class_from_row(row)

        if not weight_class:
            weight_class = weight_lookup.get(row["_fighter_normalized"], "")

        profile_weight_classes.append(weight_class)

    features_df["_profile_weight_class"] = profile_weight_classes

    return features_df


def find_fighter_row(features_df: pd.DataFrame, fighter_name: str) -> pd.Series:
    normalized = normalize_name(fighter_name)

    exact_match = features_df[features_df["_fighter_normalized"].eq(normalized)]

    if exact_match.empty:
        suggestions = features_df[
            features_df["fighter"].astype(str).str.contains(
                clean_text(fighter_name),
                case=False,
                na=False,
                regex=False,
            )
        ]["fighter"].head(8).tolist()

        suggestion_text = f" Suggestions: {', '.join(suggestions)}" if suggestions else ""

        raise ValueError(f"Fighter not found: {fighter_name}.{suggestion_text}")

    return exact_match.iloc[0]


def rank_metric(
    features_df: pd.DataFrame,
    fighter_normalized: str,
    metric_key: str,
    direction: str,
    scope: str,
    weight_class: str = "",
    min_fights: int = 5,
) -> dict[str, Any] | None:
    if metric_key not in features_df.columns:
        return None

    ranking_df = features_df.copy()
    ranking_df[metric_key] = pd.to_numeric(ranking_df[metric_key], errors="coerce")
    ranking_df = ranking_df[ranking_df[metric_key].notna()].copy()

    if "prior_fights" in ranking_df.columns:
        prior_fights = pd.to_numeric(ranking_df["prior_fights"], errors="coerce")
        ranking_df = ranking_df[prior_fights.fillna(0) >= min_fights].copy()

    if scope == "weight_class" and weight_class:
        ranking_df = ranking_df[
            ranking_df["_profile_weight_class"].astype(str).eq(weight_class)
        ].copy()

    if ranking_df.empty:
        return None

    ranking_df = ranking_df.drop_duplicates(subset=["_fighter_normalized"]).copy()

    ascending = direction == "low"

    ranking_df["_rank"] = ranking_df[metric_key].rank(
        method="min",
        ascending=ascending,
    )

    fighter_rows = ranking_df[
        ranking_df["_fighter_normalized"].eq(fighter_normalized)
    ]

    if fighter_rows.empty:
        return None

    fighter_rank_row = fighter_rows.iloc[0]

    return {
        "rank": int(fighter_rank_row["_rank"]),
        "total": int(len(ranking_df)),
        "value": safe_number(fighter_rank_row[metric_key]),
        "formatted_value": format_stat_value(metric_key, fighter_rank_row[metric_key]),
        "scope": scope,
        "weight_class": weight_class if scope == "weight_class" else "",
    }


def build_notable_rankings(
    features_df: pd.DataFrame,
    fighter_row: pd.Series,
    max_rank: int = 10,
) -> list[dict[str, Any]]:
    fighter_normalized = clean_text(fighter_row["_fighter_normalized"])
    weight_class = clean_text(fighter_row.get("_profile_weight_class", ""))

    notables = []

    for metric in RANKING_METRICS:
        overall_rank = rank_metric(
            features_df=features_df,
            fighter_normalized=fighter_normalized,
            metric_key=metric["key"],
            direction=metric["direction"],
            scope="overall",
        )

        if overall_rank and overall_rank["rank"] <= max_rank:
            notables.append(
                {
                    "metric": metric["key"],
                    "label": metric["label"],
                    "category": metric["category"],
                    "rank": overall_rank["rank"],
                    "total": overall_rank["total"],
                    "scope": "overall",
                    "scope_label": "overall",
                    "value": overall_rank["value"],
                    "formatted_value": overall_rank["formatted_value"],
                    "description": (
                        f"#{overall_rank['rank']} overall in {metric['label'].lower()} "
                        f"among qualified fighters."
                    ),
                }
            )

        weight_rank = rank_metric(
            features_df=features_df,
            fighter_normalized=fighter_normalized,
            metric_key=metric["key"],
            direction=metric["direction"],
            scope="weight_class",
            weight_class=weight_class,
        )

        if weight_rank and weight_rank["rank"] <= max_rank:
            notables.append(
                {
                    "metric": metric["key"],
                    "label": metric["label"],
                    "category": metric["category"],
                    "rank": weight_rank["rank"],
                    "total": weight_rank["total"],
                    "scope": "weight_class",
                    "scope_label": weight_class,
                    "value": weight_rank["value"],
                    "formatted_value": weight_rank["formatted_value"],
                    "description": (
                        f"#{weight_rank['rank']} in {weight_class} for "
                        f"{metric['label'].lower()} among qualified fighters."
                    ),
                }
            )

    notables.sort(key=lambda item: (item["rank"], item["scope"] != "overall", item["label"]))

    return notables[:12]


def percentile_score(
    features_df: pd.DataFrame,
    fighter_normalized: str,
    metric_key: str,
    direction: str = "high",
    min_fights: int = 5,
) -> float | None:
    if metric_key not in features_df.columns:
        return None

    ranking_df = features_df.copy()
    ranking_df[metric_key] = pd.to_numeric(ranking_df[metric_key], errors="coerce")
    ranking_df = ranking_df[ranking_df[metric_key].notna()].copy()

    if "prior_fights" in ranking_df.columns:
        prior_fights = pd.to_numeric(ranking_df["prior_fights"], errors="coerce")
        ranking_df = ranking_df[prior_fights.fillna(0) >= min_fights].copy()

    if ranking_df.empty:
        return None

    fighter_rows = ranking_df[ranking_df["_fighter_normalized"].eq(fighter_normalized)]

    if fighter_rows.empty:
        return None

    value = safe_number(fighter_rows.iloc[0][metric_key])

    if value is None:
        return None

    percentile = float((ranking_df[metric_key] <= value).mean())

    if direction == "low":
        percentile = 1.0 - percentile

    return max(0.0, min(1.0, percentile))


def average_available(values: list[float | None]) -> float | None:
    valid_values = [value for value in values if value is not None]

    if not valid_values:
        return None

    return sum(valid_values) / len(valid_values)


def build_style_profile(
    features_df: pd.DataFrame,
    fighter_row: pd.Series,
) -> dict[str, Any]:
    fighter_normalized = clean_text(fighter_row["_fighter_normalized"])

    striking_score = average_available(
        [
            percentile_score(features_df, fighter_normalized, "avg_sig_str_differential_per_15"),
            percentile_score(features_df, fighter_normalized, "avg_sig_str_landed_per_15"),
            percentile_score(features_df, fighter_normalized, "avg_sig_str_accuracy"),
            percentile_score(features_df, fighter_normalized, "avg_kd_for"),
        ]
    )

    grappling_score = average_available(
        [
            percentile_score(features_df, fighter_normalized, "avg_td_landed_per_15"),
            percentile_score(features_df, fighter_normalized, "avg_td_accuracy"),
            percentile_score(features_df, fighter_normalized, "avg_ctrl_seconds_per_15"),
            percentile_score(features_df, fighter_normalized, "avg_sub_att_per_15"),
        ]
    )

    defense_score = average_available(
        [
            percentile_score(features_df, fighter_normalized, "avg_sig_str_defense"),
            percentile_score(features_df, fighter_normalized, "avg_td_defense"),
            percentile_score(features_df, fighter_normalized, "avg_sig_str_absorbed_per_15", direction="low"),
        ]
    )

    tags = []

    if striking_score is not None and striking_score >= 0.75:
        tags.append("Striking-oriented")

    if grappling_score is not None and grappling_score >= 0.75:
        tags.append("Grappling-oriented")

    if defense_score is not None and defense_score >= 0.75:
        tags.append("Strong defensive profile")

    if percentile_score(features_df, fighter_normalized, "avg_sig_str_landed_per_15") is not None:
        if percentile_score(features_df, fighter_normalized, "avg_sig_str_landed_per_15") >= 0.85:
            tags.append("High-volume striker")

    if percentile_score(features_df, fighter_normalized, "avg_sig_str_differential_per_15") is not None:
        if percentile_score(features_df, fighter_normalized, "avg_sig_str_differential_per_15") >= 0.85:
            tags.append("Positive striking differential")

    if percentile_score(features_df, fighter_normalized, "avg_kd_for") is not None:
        if percentile_score(features_df, fighter_normalized, "avg_kd_for") >= 0.85:
            tags.append("Knockdown threat")

    if percentile_score(features_df, fighter_normalized, "avg_td_landed_per_15") is not None:
        if percentile_score(features_df, fighter_normalized, "avg_td_landed_per_15") >= 0.85:
            tags.append("Wrestling-heavy")

    if percentile_score(features_df, fighter_normalized, "avg_ctrl_seconds_per_15") is not None:
        if percentile_score(features_df, fighter_normalized, "avg_ctrl_seconds_per_15") >= 0.85:
            tags.append("Control grappler")

    if percentile_score(features_df, fighter_normalized, "avg_sub_att_per_15") is not None:
        if percentile_score(features_df, fighter_normalized, "avg_sub_att_per_15") >= 0.85:
            tags.append("Submission threat")

    if percentile_score(features_df, fighter_normalized, "avg_td_defense") is not None:
        if percentile_score(features_df, fighter_normalized, "avg_td_defense") >= 0.85:
            tags.append("Hard to take down")

    if striking_score is not None and grappling_score is not None:
        if striking_score >= 0.70 and grappling_score >= 0.70:
            style_label = "Well-rounded"
        elif striking_score >= 0.70 and striking_score > grappling_score:
            style_label = "Striker"
        elif grappling_score >= 0.70 and grappling_score > striking_score:
            style_label = "Grappler"
        else:
            style_label = "Balanced / developing"
    elif striking_score is not None and striking_score >= 0.70:
        style_label = "Striker"
    elif grappling_score is not None and grappling_score >= 0.70:
        style_label = "Grappler"
    else:
        style_label = "Balanced / developing"

    if not tags:
        tags.append("No extreme statistical style flags")

    return {
        "style_label": style_label,
        "tags": tags[:8],
        "scores": {
            "striking": striking_score,
            "grappling": grappling_score,
            "defense": defense_score,
        },
        "score_percentages": {
            "striking": f"{striking_score * 100.0:.1f}%" if striking_score is not None else "N/A",
            "grappling": f"{grappling_score * 100.0:.1f}%" if grappling_score is not None else "N/A",
            "defense": f"{defense_score * 100.0:.1f}%" if defense_score is not None else "N/A",
        },
        "note": (
            "Style labels are heuristic assumptions based on available UFCStats-derived "
            "features, not official scouting labels."
        ),
    }


def categorize_method(method: Any) -> str:
    method_text = clean_text(method).upper()

    if not method_text:
        return "Other"

    if "KO" in method_text or "TKO" in method_text:
        return "KO/TKO"

    if "SUB" in method_text:
        return "Submission"

    if "DEC" in method_text:
        return "Decision"

    return "Other"


def build_method_summary(fighter_rows: pd.DataFrame) -> dict[str, Any]:
    if fighter_rows.empty:
        return {
            "wins": {},
            "losses": {},
            "all": {},
        }

    wins = fighter_rows[fighter_rows["result"].astype(str).str.lower().eq("win")]
    losses = fighter_rows[fighter_rows["result"].astype(str).str.lower().eq("loss")]

    return {
        "wins": dict(Counter(wins["method"].apply(categorize_method))),
        "losses": dict(Counter(losses["method"].apply(categorize_method))),
        "all": dict(Counter(fighter_rows["method"].apply(categorize_method))),
    }


def build_recent_fights(fighter_rows: pd.DataFrame, limit: int = 8) -> list[dict[str, Any]]:
    if fighter_rows.empty:
        return []

    rows = fighter_rows.copy()

    if "event_date" in rows.columns:
        rows["_event_date_parsed"] = pd.to_datetime(rows["event_date"], errors="coerce")
        rows = rows.sort_values("_event_date_parsed", ascending=False)

    if "fight_url" in rows.columns:
        rows = rows.drop_duplicates(subset=["fight_url"], keep="first")

    recent_fights = []

    for _, row in rows.head(limit).iterrows():
        recent_fights.append(
            {
                "event_name": clean_text(row.get("event_name", "")),
                "event_date": clean_text(row.get("event_date", "")),
                "event_location": clean_text(row.get("event_location", "")),
                "fight_url": clean_text(row.get("fight_url", "")),
                "opponent": clean_text(row.get("opponent", "")),
                "result": clean_text(row.get("result", "")),
                "is_winner": safe_int(row.get("is_winner")),
                "weight_class": clean_text(row.get("weight_class", "")),
                "method": clean_text(row.get("method", "")),
                "method_category": categorize_method(row.get("method", "")),
                "round": clean_text(row.get("round", "")),
                "time": clean_text(row.get("time", "")),
            }
        )

    return recent_fights


def build_profile_stats(fighter_row: pd.Series) -> list[dict[str, Any]]:
    stats = []

    for key in PROFILE_STAT_KEYS:
        if key not in fighter_row.index:
            continue

        value = safe_number(fighter_row.get(key))

        if value is None:
            continue

        stats.append(
            {
                "key": key,
                "label": key.replace("_", " ").title(),
                "value": value,
                "formatted_value": format_stat_value(key, value),
            }
        )

    return stats


def build_fighter_profile(fighter_name: str) -> dict[str, Any]:
    features_df = load_current_fighter_features()
    fight_stats_df = load_fight_stats()
    snapshots_df = load_fighter_snapshots()

    features_df = add_profile_weight_classes(features_df, fight_stats_df)

    fighter_row = find_fighter_row(features_df, fighter_name)
    fighter = clean_text(fighter_row.get("fighter", fighter_name))
    fighter_normalized = clean_text(fighter_row["_fighter_normalized"])

    if not fight_stats_df.empty and "_fighter_normalized" in fight_stats_df.columns:
        fighter_fight_rows = fight_stats_df[
            fight_stats_df["_fighter_normalized"].eq(fighter_normalized)
        ].copy()
    else:
        fighter_fight_rows = pd.DataFrame()

    image_lookup = load_fighter_image_lookup()
    image_data = get_fighter_image_data(fighter, image_lookup)

    weight_class = clean_text(fighter_row.get("_profile_weight_class", ""))
    recent_fights = build_recent_fights(fighter_fight_rows)

    elo_history = build_elo_history(
        fighter_normalized=fighter_normalized,
        snapshots_df=snapshots_df,
        fight_stats_df=fight_stats_df,
    )

    form_summary = build_form_summary(recent_fights)

    profile = {
        "fighter": fighter,
        "weight_class": weight_class,
        "image": image_data,
        "headline_stats": {
            "elo": safe_number(fighter_row.get("prior_elo")),
            "elo_formatted": format_stat_value("prior_elo", fighter_row.get("prior_elo")),
            "peak_elo": safe_number(fighter_row.get("prior_peak_elo")),
            "peak_elo_formatted": format_stat_value("prior_peak_elo", fighter_row.get("prior_peak_elo")),
            "ufc_fights": safe_int(fighter_row.get("prior_fights")),
            "ufc_wins": safe_int(fighter_row.get("prior_wins")),
            "ufc_losses": safe_int(fighter_row.get("prior_losses")),
            "ufc_unscored_results": safe_int(fighter_row.get("prior_unscored_results")),
            "win_rate": safe_number(fighter_row.get("prior_win_rate")),
            "win_rate_formatted": format_stat_value("prior_win_rate", fighter_row.get("prior_win_rate")),
            "age_years": safe_number(fighter_row.get("age_years")),
            "age_formatted": format_stat_value("age_years", fighter_row.get("age_years")),
            "height": format_stat_value("height_inches", fighter_row.get("height_inches")),
            "reach": format_stat_value("reach_inches", fighter_row.get("reach_inches")),
        },
        "style_profile": build_style_profile(features_df, fighter_row),
        "notable_rankings": build_notable_rankings(features_df, fighter_row),
        "profile_stats": build_profile_stats(fighter_row),
        "method_summary": build_method_summary(fighter_fight_rows),

        # New profile trend/form fields
        "current_elo": safe_number(fighter_row.get("prior_elo")),
        "current_elo_formatted": format_stat_value("prior_elo", fighter_row.get("prior_elo")),
        "form_summary": form_summary,
        "elo_history": elo_history,
        "recent_fights": recent_fights,
    }

    return profile

def load_fighter_snapshots() -> pd.DataFrame:
    if not FIGHTER_SNAPSHOTS_CSV.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(FIGHTER_SNAPSHOTS_CSV)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()

    if "fighter" in df.columns:
        df = df.copy()
        df["_fighter_normalized"] = df["fighter"].apply(normalize_name)

    return df


def build_elo_history(
    fighter_normalized: str,
    snapshots_df: pd.DataFrame,
    fight_stats_df: pd.DataFrame,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if snapshots_df.empty or "_fighter_normalized" not in snapshots_df.columns:
        return []

    fighter_rows = snapshots_df[
        snapshots_df["_fighter_normalized"].eq(fighter_normalized)
    ].copy()

    if fighter_rows.empty:
        return []

    if "event_date" in fighter_rows.columns:
        fighter_rows["_event_date_parsed"] = pd.to_datetime(
            fighter_rows["event_date"],
            errors="coerce",
        )
        fighter_rows = fighter_rows.sort_values("_event_date_parsed")

    fight_lookup = {}

    if (
        not fight_stats_df.empty
        and {"fight_url", "fighter", "opponent", "result", "method"}.issubset(fight_stats_df.columns)
    ):
        for _, row in fight_stats_df.iterrows():
            key = (
                clean_text(row.get("fight_url", "")),
                normalize_name(row.get("fighter", "")),
            )

            fight_lookup[key] = {
                "opponent": clean_text(row.get("opponent", "")),
                "result": clean_text(row.get("result", "")),
                "method": clean_text(row.get("method", "")),
                "round": clean_text(row.get("round", "")),
                "time": clean_text(row.get("time", "")),
            }

    fighter_rows = fighter_rows.reset_index(drop=True)

    current_elo = None

    if not fighter_rows.empty:
        latest_prior_elo = safe_number(fighter_rows.iloc[-1].get("prior_elo"))
        current_elo = latest_prior_elo


    limited_rows = fighter_rows.tail(limit).reset_index(drop=True)

    history = []

    for index, row in limited_rows.iterrows():
        fight_url = clean_text(row.get("fight_url", ""))
        lookup_key = (fight_url, fighter_normalized)
        fight_details = fight_lookup.get(lookup_key, {})

        prior_elo = safe_number(row.get("prior_elo"))

        next_prior_elo = None

        if index + 1 < len(limited_rows):
            next_prior_elo = safe_number(limited_rows.iloc[index + 1].get("prior_elo"))

        plotted_elo = next_prior_elo if next_prior_elo is not None else current_elo

        history.append(
            {
                "event_name": clean_text(row.get("event_name", "")),
                "event_date": clean_text(row.get("event_date", "")),
                "fight_url": fight_url,
                "opponent": fight_details.get("opponent", clean_text(row.get("opponent", ""))),
                "result": fight_details.get("result", clean_text(row.get("result", ""))),
                "method": fight_details.get("method", clean_text(row.get("method", ""))),
                "round": fight_details.get("round", clean_text(row.get("round", ""))),
                "time": fight_details.get("time", clean_text(row.get("time", ""))),

                # Existing values
                "prior_elo": prior_elo,
                "prior_peak_elo": safe_number(row.get("prior_peak_elo")),
                "prior_elo_change_last_3": safe_number(row.get("prior_elo_change_last_3")),
                "prior_elo_fights": safe_number(row.get("prior_elo_fights")),

                # New chart-friendly values
                "plotted_elo": plotted_elo,
                "plotted_elo_label": "Post-fight/current Elo",
            }
        )

    return history



def build_form_summary(recent_fights: list[dict[str, Any]]) -> dict[str, Any]:
    if not recent_fights:
        return {
            "last_5_record": "N/A",
            "current_streak": "N/A",
            "recent_results": [],
        }

    recent_results = [
        clean_text(fight.get("result", "")).lower()
        for fight in recent_fights[:5]
    ]

    wins = recent_results.count("win")
    losses = recent_results.count("loss")

    first_result = recent_results[0] if recent_results else ""
    streak_count = 0

    for result in recent_results:
        if result and result == first_result:
            streak_count += 1
        else:
            break

    if first_result == "win":
        streak = f"{streak_count}-fight win streak"
    elif first_result == "loss":
        streak = f"{streak_count}-fight losing streak"
    else:
        streak = "No active win/loss streak"

    return {
        "last_5_record": f"{wins}-{losses}",
        "current_streak": streak,
        "recent_results": recent_results,
    }
