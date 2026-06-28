from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CURRENT_FEATURES_CSV = PROJECT_ROOT / "data" / "processed" / "current_fighter_features.csv"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"

OUTPUT_JSON = REPORTS_DIR / "category_leaders_by_weight_class.json"
OUTPUT_CSV = REPORTS_DIR / "category_leaders_by_weight_class.csv"


MAJOR_WEIGHT_CLASSES = [
    "Women's Strawweight",
    "Women's Flyweight",
    "Women's Bantamweight",
    "Women's Featherweight",
    "Flyweight",
    "Bantamweight",
    "Featherweight",
    "Lightweight",
    "Welterweight",
    "Middleweight",
    "Light Heavyweight",
    "Heavyweight",
]


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def load_current_features() -> pd.DataFrame:
    if not CURRENT_FEATURES_CSV.exists():
        raise FileNotFoundError(
            f"Missing {CURRENT_FEATURES_CSV}. "
            "Run build_current_fighter_features.py or the update pipeline first."
        )

    return pd.read_csv(CURRENT_FEATURES_CSV)


def numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([pd.NA] * len(df), index=df.index)

    return pd.to_numeric(df[column], errors="coerce")


def z_score(df: pd.DataFrame, column: str, invert: bool = False) -> pd.Series:
    values = numeric_series(df, column)

    if values.notna().sum() == 0:
        return pd.Series([0.0] * len(df), index=df.index)

    values = values.fillna(values.median())

    if invert:
        values = -values

    std = values.std()

    if pd.isna(std) or std == 0:
        return pd.Series([0.0] * len(df), index=df.index)

    return (values - values.mean()) / std


def build_composite_score(
    df: pd.DataFrame,
    components: list[tuple[str, float, bool]],
) -> pd.Series:
    score = pd.Series([0.0] * len(df), index=df.index)

    for column, weight, invert in components:
        score += weight * z_score(df, column, invert=invert)

    return score


def filter_fighters(
    df: pd.DataFrame,
    min_fights: int,
    max_inactive_days: int | None,
) -> pd.DataFrame:
    filtered = df.copy()

    if "weight_class" not in filtered.columns:
        raise ValueError("current_fighter_features.csv must contain a weight_class column.")

    filtered["weight_class"] = filtered["weight_class"].apply(clean_text)
    filtered = filtered[filtered["weight_class"].isin(MAJOR_WEIGHT_CLASSES)].copy()

    filtered["prior_fights_numeric"] = numeric_series(filtered, "prior_fights")
    filtered = filtered[filtered["prior_fights_numeric"] >= min_fights].copy()

    if max_inactive_days is not None and "days_since_last_fight" in filtered.columns:
        filtered["days_since_last_fight_numeric"] = numeric_series(
            filtered,
            "days_since_last_fight",
        )

        filtered = filtered[
            filtered["days_since_last_fight_numeric"].isna()
            | (filtered["days_since_last_fight_numeric"] <= max_inactive_days)
        ].copy()

    return filtered.reset_index(drop=True)


def get_supporting_stats(row: pd.Series, columns: list[str]) -> dict[str, Any]:
    stats = {}

    for column in columns:
        if column not in row.index:
            continue

        value = row[column]

        if pd.isna(value):
            stats[column] = None
        elif isinstance(value, float):
            stats[column] = round(float(value), 3)
        else:
            stats[column] = value

    return stats


def rows_from_ranked_df(
    ranked_df: pd.DataFrame,
    weight_class: str,
    category: str,
    direction: str,
    score_column: str,
    supporting_columns: list[str],
) -> list[dict[str, Any]]:
    rows = []

    for rank, (_, row) in enumerate(ranked_df.iterrows(), start=1):
        days_since_last_fight = row.get("days_since_last_fight", pd.NA)

        rows.append(
            {
                "weight_class": weight_class,
                "category": category,
                "direction": direction,
                "rank": rank,
                "fighter": clean_text(row.get("fighter", "")),
                "score": round(float(row[score_column]), 3),
                "prior_fights": int(row.get("prior_fights", 0)),
                "days_since_last_fight": (
                    None
                    if pd.isna(days_since_last_fight)
                    else int(days_since_last_fight)
                ),
                "supporting_stats": get_supporting_stats(row, supporting_columns),
            }
        )

    return rows


def best_and_worst_from_score(
    df: pd.DataFrame,
    weight_class: str,
    category: str,
    score: pd.Series,
    top_n: int,
    supporting_columns: list[str],
) -> dict[str, list[dict[str, Any]]]:
    ranked_df = df.copy()
    ranked_df["category_score"] = score

    best_df = ranked_df.sort_values("category_score", ascending=False).head(top_n)
    worst_df = ranked_df.sort_values("category_score", ascending=True).head(top_n)

    return {
        "best": rows_from_ranked_df(
            ranked_df=best_df,
            weight_class=weight_class,
            category=category,
            direction="best",
            score_column="category_score",
            supporting_columns=supporting_columns,
        ),
        "worst": rows_from_ranked_df(
            ranked_df=worst_df,
            weight_class=weight_class,
            category=category,
            direction="worst",
            score_column="category_score",
            supporting_columns=supporting_columns,
        ),
    }


def best_and_worst_from_column(
    df: pd.DataFrame,
    weight_class: str,
    category: str,
    column: str,
    top_n: int,
    supporting_columns: list[str],
) -> dict[str, list[dict[str, Any]]]:
    if column not in df.columns:
        return {
            "best": [],
            "worst": [],
        }

    ranked_df = df.copy()
    ranked_df[column] = numeric_series(ranked_df, column)
    ranked_df = ranked_df[ranked_df[column].notna()].copy()

    best_df = ranked_df.sort_values(column, ascending=False).head(top_n)
    worst_df = ranked_df.sort_values(column, ascending=True).head(top_n)

    return {
        "best": rows_from_ranked_df(
            ranked_df=best_df,
            weight_class=weight_class,
            category=category,
            direction="best",
            score_column=column,
            supporting_columns=supporting_columns,
        ),
        "worst": rows_from_ranked_df(
            ranked_df=worst_df,
            weight_class=weight_class,
            category=category,
            direction="worst",
            score_column=column,
            supporting_columns=supporting_columns,
        ),
    }


def build_categories_for_weight_class(
    weight_df: pd.DataFrame,
    weight_class: str,
    top_n: int,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    categories: dict[str, dict[str, list[dict[str, Any]]]] = {}

    categories["overall"] = best_and_worst_from_score(
        df=weight_df,
        weight_class=weight_class,
        category="overall",
        score=build_composite_score(
            weight_df,
            [
                ("prior_elo", 0.45, False),
                ("prior_win_rate", 0.20, False),
                ("recent_5_win_rate", 0.15, False),
                ("avg_sig_str_differential_per_15", 0.10, False),
                ("prior_finish_win_rate", 0.10, False),
            ],
        ),
        top_n=top_n,
        supporting_columns=[
            "prior_elo",
            "prior_win_rate",
            "recent_5_win_rate",
            "avg_sig_str_differential_per_15",
            "prior_finish_win_rate",
        ],
    )

    categories["striking"] = best_and_worst_from_score(
        df=weight_df,
        weight_class=weight_class,
        category="striking",
        score=build_composite_score(
            weight_df,
            [
                ("avg_sig_str_differential_per_15", 0.45, False),
                ("avg_sig_str_landed_per_15", 0.20, False),
                ("avg_sig_str_accuracy", 0.10, False),
                ("avg_sig_str_defense", 0.10, False),
                ("avg_kd_for", 0.10, False),
                ("avg_sig_str_absorbed_per_15", 0.15, True),
                ("avg_kd_against", 0.10, True),
            ],
        ),
        top_n=top_n,
        supporting_columns=[
            "avg_sig_str_differential_per_15",
            "avg_sig_str_landed_per_15",
            "avg_sig_str_absorbed_per_15",
            "avg_sig_str_accuracy",
            "avg_sig_str_defense",
            "avg_kd_for",
            "avg_kd_against",
        ],
    )

    categories["grappling"] = best_and_worst_from_score(
        df=weight_df,
        weight_class=weight_class,
        category="grappling",
        score=build_composite_score(
            weight_df,
            [
                ("avg_td_landed_per_15", 0.25, False),
                ("avg_td_accuracy", 0.15, False),
                ("avg_td_defense", 0.20, False),
                ("avg_ctrl_seconds_per_15", 0.25, False),
                ("avg_sub_att_per_15", 0.20, False),
                ("avg_td_absorbed_per_15", 0.15, True),
                ("avg_ctrl_absorbed_seconds_per_15", 0.15, True),
            ],
        ),
        top_n=top_n,
        supporting_columns=[
            "avg_td_landed_per_15",
            "avg_td_accuracy",
            "avg_td_defense",
            "avg_ctrl_seconds_per_15",
            "avg_sub_att_per_15",
            "avg_td_absorbed_per_15",
            "avg_ctrl_absorbed_seconds_per_15",
        ],
    )

    categories["wrestling"] = best_and_worst_from_score(
        df=weight_df,
        weight_class=weight_class,
        category="wrestling",
        score=build_composite_score(
            weight_df,
            [
                ("avg_td_landed_per_15", 0.35, False),
                ("avg_td_attempted_per_15", 0.10, False),
                ("avg_td_accuracy", 0.15, False),
                ("avg_td_defense", 0.20, False),
                ("avg_ctrl_seconds_per_15", 0.25, False),
                ("avg_td_absorbed_per_15", 0.15, True),
            ],
        ),
        top_n=top_n,
        supporting_columns=[
            "avg_td_landed_per_15",
            "avg_td_attempted_per_15",
            "avg_td_accuracy",
            "avg_td_defense",
            "avg_ctrl_seconds_per_15",
            "avg_td_absorbed_per_15",
        ],
    )

    categories["finishing"] = best_and_worst_from_score(
        df=weight_df,
        weight_class=weight_class,
        category="finishing",
        score=build_composite_score(
            weight_df,
            [
                ("prior_finish_win_rate", 0.50, False),
                ("avg_kd_for", 0.20, False),
                ("avg_sub_att_per_15", 0.20, False),
                ("prior_win_rate", 0.10, False),
            ],
        ),
        top_n=top_n,
        supporting_columns=[
            "prior_finish_win_rate",
            "avg_kd_for",
            "avg_sub_att_per_15",
            "prior_win_rate",
        ],
    )

    categories["defense"] = best_and_worst_from_score(
        df=weight_df,
        weight_class=weight_class,
        category="defense",
        score=build_composite_score(
            weight_df,
            [
                ("avg_sig_str_defense", 0.25, False),
                ("avg_td_defense", 0.25, False),
                ("avg_sig_str_absorbed_per_15", 0.20, True),
                ("avg_td_absorbed_per_15", 0.15, True),
                ("avg_ctrl_absorbed_seconds_per_15", 0.15, True),
                ("avg_kd_against", 0.10, True),
                ("prior_finish_loss_rate", 0.10, True),
            ],
        ),
        top_n=top_n,
        supporting_columns=[
            "avg_sig_str_defense",
            "avg_td_defense",
            "avg_sig_str_absorbed_per_15",
            "avg_td_absorbed_per_15",
            "avg_ctrl_absorbed_seconds_per_15",
            "avg_kd_against",
            "prior_finish_loss_rate",
        ],
    )

    categories["elo"] = best_and_worst_from_column(
        df=weight_df,
        weight_class=weight_class,
        category="elo",
        column="prior_elo",
        top_n=top_n,
        supporting_columns=[
            "prior_elo",
            "prior_peak_elo",
            "prior_win_rate",
            "prior_fights",
        ],
    )

    categories["experience"] = best_and_worst_from_column(
        df=weight_df,
        weight_class=weight_class,
        category="experience",
        column="prior_fights",
        top_n=top_n,
        supporting_columns=[
            "prior_fights",
            "prior_wins",
            "prior_losses",
            "prior_unscored_results",
            "prior_win_rate",
        ],
    )

    categories["reach"] = best_and_worst_from_column(
        df=weight_df,
        weight_class=weight_class,
        category="reach",
        column="reach_inches",
        top_n=top_n,
        supporting_columns=[
            "height_inches",
            "reach_inches",
            "reach_minus_height_inches",
        ],
    )

    categories["reach_for_size"] = best_and_worst_from_column(
        df=weight_df,
        weight_class=weight_class,
        category="reach_for_size",
        column="reach_minus_height_inches",
        top_n=top_n,
        supporting_columns=[
            "height_inches",
            "reach_inches",
            "reach_minus_height_inches",
        ],
    )

    return categories


def build_category_leaders_by_weight_class(
    df: pd.DataFrame,
    top_n: int,
    min_fights: int,
    max_inactive_days: int | None,
) -> dict[str, Any]:
    filtered_df = filter_fighters(
        df=df,
        min_fights=min_fights,
        max_inactive_days=max_inactive_days,
    )

    weight_class_results: dict[str, Any] = {}

    for weight_class in MAJOR_WEIGHT_CLASSES:
        weight_df = filtered_df[filtered_df["weight_class"] == weight_class].copy()

        if weight_df.empty:
            weight_class_results[weight_class] = {
                "fighter_count": 0,
                "categories": {},
            }
            continue

        weight_class_results[weight_class] = {
            "fighter_count": int(len(weight_df)),
            "categories": build_categories_for_weight_class(
                weight_df=weight_df,
                weight_class=weight_class,
                top_n=top_n,
            ),
        }

    return {
        "metadata": {
            "source_file": str(CURRENT_FEATURES_CSV),
            "fighter_rows_total": int(len(df)),
            "fighter_rows_after_filters": int(len(filtered_df)),
            "top_n": top_n,
            "min_fights": min_fights,
            "max_inactive_days": max_inactive_days,
            "weight_classes": MAJOR_WEIGHT_CLASSES,
            "excluded_weight_classes": ["Open Weight", "Catch Weight"],
            "note": (
                "Composite scores are for fun and depend on chosen feature weights. "
                "Worst means lowest score within the filtered fighters for that category and weight class."
            ),
        },
        "weight_classes": weight_class_results,
    }


def save_outputs(payload: dict[str, Any]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    rows = []

    for weight_class, weight_payload in payload["weight_classes"].items():
        categories = weight_payload.get("categories", {})

        for category, category_payload in categories.items():
            for direction in ["best", "worst"]:
                for fighter_row in category_payload.get(direction, []):
                    rows.append(
                        {
                            "weight_class": weight_class,
                            "category": category,
                            "direction": direction,
                            "rank": fighter_row["rank"],
                            "fighter": fighter_row["fighter"],
                            "score": fighter_row["score"],
                            "prior_fights": fighter_row["prior_fights"],
                            "days_since_last_fight": fighter_row["days_since_last_fight"],
                            "supporting_stats_json": json.dumps(
                                fighter_row["supporting_stats"]
                            ),
                        }
                    )

    pd.DataFrame(rows).to_csv(OUTPUT_CSV, index=False)


def print_direction_rows(rows: list[dict[str, Any]], label: str) -> None:
    print(f"  {label}")

    if not rows:
        print("    No fighters found.")
        return

    for leader in rows:
        print(
            f"    {leader['rank']:>2}. "
            f"{leader['fighter']:<28} "
            f"score={leader['score']:<8} "
            f"fights={leader['prior_fights']}"
        )


def print_leaderboards(payload: dict[str, Any]) -> None:
    metadata = payload["metadata"]

    print()
    print("UFC Category Leaders by Weight Class")
    print("=" * 90)
    print(f"Total fighters:       {metadata['fighter_rows_total']}")
    print(f"After filters:        {metadata['fighter_rows_after_filters']}")
    print(f"Top per direction:    {metadata['top_n']}")
    print(f"Min fights:           {metadata['min_fights']}")
    print(f"Max inactive days:    {metadata['max_inactive_days']}")
    print("Excluded classes:     Open Weight, Catch Weight")
    print()

    for weight_class, weight_payload in payload["weight_classes"].items():
        print()
        print("=" * 90)
        print(f"{weight_class.upper()}  |  fighters after filters: {weight_payload['fighter_count']}")
        print("=" * 90)

        if weight_payload["fighter_count"] == 0:
            print("No fighters found for this weight class with current filters.")
            continue

        for category, category_payload in weight_payload["categories"].items():
            print()
            print(category.upper().replace("_", " "))
            print("-" * 90)

            print_direction_rows(category_payload["best"], "BEST")
            print_direction_rows(category_payload["worst"], "WORST")

    print()
    print(f"Saved JSON: {OUTPUT_JSON}")
    print(f"Saved CSV:  {OUTPUT_CSV}")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="How many fighters to show for best and worst per category.",
    )

    parser.add_argument(
        "--min-fights",
        type=int,
        default=5,
        help="Minimum UFC fights required.",
    )

    parser.add_argument(
        "--max-inactive-days",
        type=int,
        default=1095,
        help=(
            "Maximum days since last fight. "
            "Default is 1095 days, about 3 years. "
            "Use 0 or negative to disable."
        ),
    )

    args = parser.parse_args()

    max_inactive_days = (
        args.max_inactive_days
        if args.max_inactive_days and args.max_inactive_days > 0
        else None
    )

    df = load_current_features()

    payload = build_category_leaders_by_weight_class(
        df=df,
        top_n=args.top,
        min_fights=args.min_fights,
        max_inactive_days=max_inactive_days,
    )

    save_outputs(payload)
    print_leaderboards(payload)


if __name__ == "__main__":
    main()
