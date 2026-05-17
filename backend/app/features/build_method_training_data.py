from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"

TRAINING_MATCHUPS_CSV = PROCESSED_DATA_DIR / "training_matchups.csv"
METHOD_LABELS_CSV = REPORTS_DIR / "method_label_exploration.csv"
OUTPUT_CSV = PROCESSED_DATA_DIR / "method_training_data.csv"


RARE_DETAIL_LABELS = {
    "DQ/other",
    "Other submission",
    "Submission - injury/other",
    "Other/unknown",
    "Unknown",
}


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not TRAINING_MATCHUPS_CSV.exists():
        raise FileNotFoundError(f"Missing {TRAINING_MATCHUPS_CSV}")

    if not METHOD_LABELS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {METHOD_LABELS_CSV}. Run app.analysis.explore_method_labels first."
        )

    matchups_df = pd.read_csv(TRAINING_MATCHUPS_CSV)
    labels_df = pd.read_csv(METHOD_LABELS_CSV)

    if "fight_url" not in matchups_df.columns:
        raise ValueError("training_matchups.csv must contain fight_url.")

    required_label_columns = ["fight_url", "broad_method", "detailed_method"]

    missing_label_columns = [
        column for column in required_label_columns
        if column not in labels_df.columns
    ]

    if missing_label_columns:
        raise ValueError(
            "method_label_exploration.csv is missing columns: "
            + ", ".join(missing_label_columns)
        )

    return matchups_df, labels_df


def collapse_rare_detail_label(label: Any) -> str:
    label = clean_text(label)

    if label in RARE_DETAIL_LABELS:
        return "Other/rare ending"

    return label or "Other/rare ending"


def build_fight_level_base(matchups_df: pd.DataFrame) -> pd.DataFrame:
    """
    training_matchups.csv has two rows per fight.

    For method prediction, we want one row per fight and orientation-invariant
    features so the model does not care which fighter is listed first.
    """
    df = matchups_df.copy()

    if "event_date" in df.columns:
        df["event_date_parsed"] = pd.to_datetime(df["event_date"], errors="coerce")
    else:
        df["event_date_parsed"] = pd.NaT

    # Prefer target == 1 as the representative row because that row has
    # fighter_a as the actual winner. We are not using target as a feature.
    if "target" in df.columns:
        representative_df = df[df["target"] == 1].copy()
    else:
        representative_df = df.copy()

    representative_df = representative_df.drop_duplicates(subset=["fight_url"]).copy()

    return representative_df.reset_index(drop=True)


def build_method_features(fight_df: pd.DataFrame) -> pd.DataFrame:
    output_df = pd.DataFrame(index=fight_df.index)

    keep_direct_columns = [
        "fight_url",
        "event_name",
        "event_date",
        "event_date_parsed",
        "weight_class",
        "fighter_a",
        "fighter_b",
    ]

    for column in keep_direct_columns:
        if column in fight_df.columns:
            output_df[column] = fight_df[column]

    # Categorical feature
    if "weight_class" not in output_df.columns:
        output_df["weight_class"] = ""

    # Orientation-invariant numeric features:
    # 1. Absolute differences from diff_* columns.
    # 2. Mean/min/max from matching a_* and b_* columns.
    for column in fight_df.columns:
        if not column.startswith("diff_"):
            continue

        values = pd.to_numeric(fight_df[column], errors="coerce")
        output_df[f"abs_{column}"] = values.abs()

    a_columns = [column for column in fight_df.columns if column.startswith("a_")]

    for a_column in a_columns:
        suffix = a_column[2:]
        b_column = f"b_{suffix}"

        if b_column not in fight_df.columns:
            continue

        a_values = pd.to_numeric(fight_df[a_column], errors="coerce")
        b_values = pd.to_numeric(fight_df[b_column], errors="coerce")

        output_df[f"mean_{suffix}"] = pd.concat([a_values, b_values], axis=1).mean(axis=1)
        output_df[f"max_{suffix}"] = pd.concat([a_values, b_values], axis=1).max(axis=1)
        output_df[f"min_{suffix}"] = pd.concat([a_values, b_values], axis=1).min(axis=1)

    return output_df


def build_method_training_data() -> dict[str, Any]:
    matchups_df, labels_df = load_inputs()

    labels_df = labels_df[
        [
            "fight_url",
            "broad_method",
            "detailed_method",
            "method",
            "winner",
            "loser",
        ]
    ].copy()

    labels_df["fight_url"] = labels_df["fight_url"].apply(clean_text)
    labels_df["broad_method"] = labels_df["broad_method"].apply(clean_text)
    labels_df["detailed_method"] = labels_df["detailed_method"].apply(
        collapse_rare_detail_label
    )

    fight_df = build_fight_level_base(matchups_df)
    feature_df = build_method_features(fight_df)

    feature_df["fight_url"] = feature_df["fight_url"].apply(clean_text)

    method_training_df = feature_df.merge(
        labels_df,
        on="fight_url",
        how="inner",
    )

    # Drop true unknown/empty labels.
    method_training_df = method_training_df[
        method_training_df["broad_method"].ne("")
        & method_training_df["detailed_method"].ne("")
    ].copy()

    method_training_df.to_csv(OUTPUT_CSV, index=False)

    return {
        "output_file": str(OUTPUT_CSV),
        "rows": int(len(method_training_df)),
        "broad_counts": method_training_df["broad_method"].value_counts().to_dict(),
        "detailed_counts": method_training_df["detailed_method"].value_counts().to_dict(),
        "columns": int(len(method_training_df.columns)),
    }


def main() -> None:
    result = build_method_training_data()

    print()
    print("Method training data built")
    print("=" * 80)

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()