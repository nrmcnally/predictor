from __future__ import annotations

from typing import Any

from app.analysis.category_leaders import (
    CURRENT_FEATURES_CSV,
    MAJOR_WEIGHT_CLASSES,
    build_categories_for_weight_class,
    filter_fighters,
    load_current_features,
)


CATEGORY_LABELS = {
    "overall": "Overall",
    "striking": "Striking",
    "grappling": "Grappling",
    "wrestling": "Wrestling",
    "finishing": "Finishing",
    "defense": "Defense",
    "elo": "Elo",
    "experience": "Experience",
    "reach": "Reach",
    "reach_for_size": "Reach for Size",
}


def normalize_max_inactive_days(max_inactive_days: int | None) -> int | None:
    if max_inactive_days is None:
        return 1095

    if max_inactive_days <= 0:
        return None

    return max_inactive_days


def get_leaderboard_options() -> dict[str, Any]:
    return {
        "scopes": [
            {
                "value": "overall",
                "label": "Overall",
            },
            {
                "value": "weight_class",
                "label": "By Weight Class",
            },
        ],
        "weight_classes": MAJOR_WEIGHT_CLASSES,
        "categories": [
            {
                "value": key,
                "label": label,
            }
            for key, label in CATEGORY_LABELS.items()
        ],
        "directions": [
            {
                "value": "best",
                "label": "Best",
            },
            {
                "value": "worst",
                "label": "Worst",
            },
        ],
        "default_filters": {
            "top": 5,
            "min_fights": 5,
            "max_inactive_days": 1095,
        },
    }


def get_leaderboards(
    top: int = 5,
    min_fights: int = 5,
    max_inactive_days: int | None = 1095,
) -> dict[str, Any]:
    top = max(1, min(int(top), 25))
    min_fights = max(0, int(min_fights))
    max_inactive_days = normalize_max_inactive_days(max_inactive_days)

    df = load_current_features()

    filtered_df = filter_fighters(
        df=df,
        min_fights=min_fights,
        max_inactive_days=max_inactive_days,
    )

    overall_categories = build_categories_for_weight_class(
        weight_df=filtered_df,
        weight_class="Overall",
        top_n=top,
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
                top_n=top,
            ),
        }

    return {
        "metadata": {
            "source_file": str(CURRENT_FEATURES_CSV),
            "fighter_rows_total": int(len(df)),
            "fighter_rows_after_filters": int(len(filtered_df)),
            "top": top,
            "min_fights": min_fights,
            "max_inactive_days": max_inactive_days,
            "excluded_weight_classes": [
                "Open Weight",
                "Catch Weight",
            ],
            "note": (
                "Composite categories are for analysis/fun and depend on the chosen "
                "feature weights. Worst means lowest score among fighters passing the filters."
            ),
        },
        "options": get_leaderboard_options(),
        "overall": {
            "fighter_count": int(len(filtered_df)),
            "categories": overall_categories,
        },
        "weight_classes": weight_class_results,
    }