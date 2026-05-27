from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

FIGHTER_PROFILES_CSV = RAW_DATA_DIR / "fighter_profiles.csv"
FIGHT_STATS_CSV = RAW_DATA_DIR / "fight_stats.csv"
FIGHTER_SNAPSHOTS_CSV = PROCESSED_DATA_DIR / "fighter_snapshots.csv"


# UFCStats labels are used as-is where possible. Values are official/common class
# limits in pounds. Catchweight/open-weight rows intentionally stay unknown.
WEIGHT_CLASS_LIMITS_LBS: dict[str, float] = {
    "Women's Strawweight": 115.0,
    "Women's Flyweight": 125.0,
    "Women's Bantamweight": 135.0,
    "Women's Featherweight": 145.0,
    "Strawweight": 115.0,
    "Flyweight": 125.0,
    "Bantamweight": 135.0,
    "Featherweight": 145.0,
    "Lightweight": 155.0,
    "Welterweight": 170.0,
    "Middleweight": 185.0,
    "Light Heavyweight": 205.0,
    "Heavyweight": 265.0,
}

WEIGHT_SIZE_FEATURE_COLUMNS = [
    "listed_weight_lbs",
    "listed_weight_known",
    "weight_class_lbs",
    "weight_class_known",
    "listed_weight_minus_class_lbs",
    "prior_recent_weight_class_lbs",
    "prior_common_weight_class_lbs",
    "prior_weight_class_known",
    "prior_division_count",
    "prior_fights_at_weight_class",
    "prior_pct_fights_at_weight_class",
    "current_vs_recent_weight_class_lbs_delta",
    "current_vs_common_weight_class_lbs_delta",
    "moved_up_from_recent_class",
    "moved_down_from_recent_class",
    "moved_up_from_common_class",
    "moved_down_from_common_class",
    "height_vs_weight_class_avg_inches",
    "reach_vs_weight_class_avg_inches",
    "listed_weight_vs_weight_class_avg_lbs",
]


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def normalize_name(value: Any) -> str:
    return clean_text(value).lower()


def safe_number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if pd.isna(number):
        return None

    return number


def get_weight_class_lbs(weight_class: Any) -> float | None:
    cleaned = clean_text(weight_class)

    if not cleaned:
        return None

    if cleaned in WEIGHT_CLASS_LIMITS_LBS:
        return WEIGHT_CLASS_LIMITS_LBS[cleaned]

    # Handle minor label variations without trying to guess catchweights.
    lowered = cleaned.lower()
    for known_class, pounds in WEIGHT_CLASS_LIMITS_LBS.items():
        if lowered == known_class.lower():
            return pounds

    return None


def is_heavyweight_class(weight_class: Any) -> bool:
    return clean_text(weight_class).lower() == "heavyweight"


def get_effective_listed_weight_lbs(
    listed_weight_lbs: float | None,
    current_class_lbs: float | None,
    current_weight_class: Any,
) -> float | None:
    """
    Returns the modeling weight used for weight/size features.

    For non-heavyweight divisions, UFC profile weights often behave like division
    labels rather than true walk-around weights. When predicting or backfilling
    historical rows, treating a fighter who moved up as literally still one full
    division lighter can create a misleading size penalty.

    So for non-heavyweight fights with a known class limit, we use the fight's
    class limit as the effective listed/contest weight. Heavyweight is different
    because it has a wide allowed range, so we keep the fighter's listed weight
    when available.
    """
    if current_class_lbs is None:
        return listed_weight_lbs

    if is_heavyweight_class(current_weight_class):
        return listed_weight_lbs if listed_weight_lbs is not None else current_class_lbs

    return current_class_lbs


def load_fighter_profiles() -> pd.DataFrame:
    if not FIGHTER_PROFILES_CSV.exists():
        raise FileNotFoundError(f"Missing {FIGHTER_PROFILES_CSV}")

    return pd.read_csv(FIGHTER_PROFILES_CSV)


def load_fight_stats() -> pd.DataFrame:
    if not FIGHT_STATS_CSV.exists():
        raise FileNotFoundError(f"Missing {FIGHT_STATS_CSV}")

    return pd.read_csv(FIGHT_STATS_CSV)


def load_fighter_snapshots() -> pd.DataFrame:
    if not FIGHTER_SNAPSHOTS_CSV.exists():
        raise FileNotFoundError(f"Missing {FIGHTER_SNAPSHOTS_CSV}")

    return pd.read_csv(FIGHTER_SNAPSHOTS_CSV)


def load_weight_size_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return load_fighter_profiles(), load_fighter_snapshots(), load_fight_stats()


def build_profile_lookup(profiles_df: pd.DataFrame) -> dict[str, dict[str, float | None]]:
    if profiles_df.empty or "fighter" not in profiles_df.columns:
        return {}

    lookup: dict[str, dict[str, float | None]] = {}

    for _, row in profiles_df.iterrows():
        fighter = clean_text(row.get("fighter", ""))

        if not fighter:
            continue

        lookup[normalize_name(fighter)] = {
            "listed_weight_lbs": safe_number(row.get("weight_lbs")),
            "height_inches": safe_number(row.get("height_inches")),
            "reach_inches": safe_number(row.get("reach_inches")),
        }

    return lookup


def build_division_average_lookup(
    profiles_df: pd.DataFrame,
    fight_stats_df: pd.DataFrame,
) -> dict[str, dict[str, float | None]]:
    if profiles_df.empty or fight_stats_df.empty:
        return {}

    if "fighter" not in profiles_df.columns or "fighter" not in fight_stats_df.columns:
        return {}

    if "weight_class" not in fight_stats_df.columns:
        return {}

    profile_columns = [
        column
        for column in ["fighter", "height_inches", "reach_inches", "weight_lbs"]
        if column in profiles_df.columns
    ]

    fighter_weight_classes = (
        fight_stats_df[["fighter", "weight_class"]]
        .dropna(subset=["fighter", "weight_class"])
        .drop_duplicates()
        .copy()
    )

    merged = fighter_weight_classes.merge(
        profiles_df[profile_columns],
        on="fighter",
        how="left",
    )

    lookup: dict[str, dict[str, float | None]] = {}

    for weight_class, rows in merged.groupby("weight_class", dropna=False):
        cleaned_weight_class = clean_text(weight_class)

        if not cleaned_weight_class:
            continue

        current_class_lbs = get_weight_class_lbs(cleaned_weight_class)

        if "weight_lbs" in rows.columns:
            effective_weights = rows["weight_lbs"].apply(
                lambda value: get_effective_listed_weight_lbs(
                    listed_weight_lbs=safe_number(value),
                    current_class_lbs=current_class_lbs,
                    current_weight_class=cleaned_weight_class,
                )
            )
        else:
            effective_weights = pd.Series(dtype="float64")

        lookup[cleaned_weight_class] = {
            "avg_height_inches": safe_number(pd.to_numeric(rows.get("height_inches"), errors="coerce").mean())
            if "height_inches" in rows.columns else None,
            "avg_reach_inches": safe_number(pd.to_numeric(rows.get("reach_inches"), errors="coerce").mean())
            if "reach_inches" in rows.columns else None,
            "avg_listed_weight_lbs": safe_number(pd.to_numeric(effective_weights, errors="coerce").mean()),
        }

    return lookup


def most_common_weight_class(weight_classes: list[str]) -> str:
    cleaned_classes = [clean_text(value) for value in weight_classes if clean_text(value)]

    if not cleaned_classes:
        return ""

    return Counter(cleaned_classes).most_common(1)[0][0]


def safe_difference(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None

    return left - right


def flag_positive(value: float | None) -> int:
    return int(value is not None and value > 0)


def flag_negative(value: float | None) -> int:
    return int(value is not None and value < 0)


def build_weight_size_feature_row(
    fighter: Any,
    current_weight_class: Any,
    historical_weight_classes: list[str],
    profile_lookup: dict[str, dict[str, float | None]],
    division_average_lookup: dict[str, dict[str, float | None]],
) -> dict[str, float | int | None]:
    fighter_key = normalize_name(fighter)
    current_weight_class_clean = clean_text(current_weight_class)

    profile = profile_lookup.get(fighter_key, {})
    raw_listed_weight_lbs = safe_number(profile.get("listed_weight_lbs"))
    height_inches = safe_number(profile.get("height_inches"))
    reach_inches = safe_number(profile.get("reach_inches"))

    current_class_lbs = get_weight_class_lbs(current_weight_class_clean)
    listed_weight_lbs = get_effective_listed_weight_lbs(
        listed_weight_lbs=raw_listed_weight_lbs,
        current_class_lbs=current_class_lbs,
        current_weight_class=current_weight_class_clean,
    )

    clean_history = [clean_text(value) for value in historical_weight_classes if clean_text(value)]
    recent_weight_class = clean_history[-1] if clean_history else ""
    common_weight_class = most_common_weight_class(clean_history)

    recent_class_lbs = get_weight_class_lbs(recent_weight_class)
    common_class_lbs = get_weight_class_lbs(common_weight_class)

    # Debuts have no prior division history. Treat movement as neutral instead of
    # turning every debut into a missing-value row.
    current_vs_recent_delta = safe_difference(current_class_lbs, recent_class_lbs)
    current_vs_common_delta = safe_difference(current_class_lbs, common_class_lbs)

    if not clean_history:
        current_vs_recent_delta = 0.0
        current_vs_common_delta = 0.0

    prior_fights = len(clean_history)
    prior_fights_at_weight_class = clean_history.count(current_weight_class_clean)
    prior_pct_fights_at_weight_class = (
        prior_fights_at_weight_class / prior_fights
        if prior_fights > 0
        else 0.0
    )

    division_averages = division_average_lookup.get(current_weight_class_clean, {})
    avg_height_inches = safe_number(division_averages.get("avg_height_inches"))
    avg_reach_inches = safe_number(division_averages.get("avg_reach_inches"))
    avg_listed_weight_lbs = safe_number(division_averages.get("avg_listed_weight_lbs"))

    return {
        "listed_weight_lbs": listed_weight_lbs,
        "listed_weight_known": int(listed_weight_lbs is not None),
        "weight_class_lbs": current_class_lbs,
        "weight_class_known": int(current_class_lbs is not None),
        "listed_weight_minus_class_lbs": safe_difference(listed_weight_lbs, current_class_lbs),
        "prior_recent_weight_class_lbs": recent_class_lbs if recent_class_lbs is not None else current_class_lbs,
        "prior_common_weight_class_lbs": common_class_lbs if common_class_lbs is not None else current_class_lbs,
        "prior_weight_class_known": int(bool(clean_history)),
        "prior_division_count": len(set(clean_history)),
        "prior_fights_at_weight_class": prior_fights_at_weight_class,
        "prior_pct_fights_at_weight_class": prior_pct_fights_at_weight_class,
        "current_vs_recent_weight_class_lbs_delta": current_vs_recent_delta,
        "current_vs_common_weight_class_lbs_delta": current_vs_common_delta,
        "moved_up_from_recent_class": flag_positive(current_vs_recent_delta),
        "moved_down_from_recent_class": flag_negative(current_vs_recent_delta),
        "moved_up_from_common_class": flag_positive(current_vs_common_delta),
        "moved_down_from_common_class": flag_negative(current_vs_common_delta),
        "height_vs_weight_class_avg_inches": safe_difference(height_inches, avg_height_inches),
        "reach_vs_weight_class_avg_inches": safe_difference(reach_inches, avg_reach_inches),
        "listed_weight_vs_weight_class_avg_lbs": safe_difference(listed_weight_lbs, avg_listed_weight_lbs),
    }


def sorted_fight_stats(fight_stats_df: pd.DataFrame) -> pd.DataFrame:
    df = fight_stats_df.copy()

    if "event_date" in df.columns:
        df["event_date_parsed"] = pd.to_datetime(df["event_date"], errors="coerce")
    else:
        df["event_date_parsed"] = pd.NaT

    sort_columns = [
        column
        for column in ["event_date_parsed", "event_name", "fight_url", "fighter"]
        if column in df.columns
    ]

    if sort_columns:
        df = df.sort_values(sort_columns).reset_index(drop=True)

    return df


def add_weight_size_features_to_snapshots(
    profiles_df: pd.DataFrame,
    snapshots_df: pd.DataFrame,
    fight_stats_df: pd.DataFrame,
) -> pd.DataFrame:
    if snapshots_df.empty:
        return snapshots_df.copy()

    if not {"fight_url", "fighter", "weight_class"}.issubset(snapshots_df.columns):
        raise ValueError("fighter_snapshots.csv must include fight_url, fighter, and weight_class.")

    if not {"fight_url", "fighter", "weight_class"}.issubset(fight_stats_df.columns):
        raise ValueError("fight_stats.csv must include fight_url, fighter, and weight_class.")

    profile_lookup = build_profile_lookup(profiles_df)
    division_average_lookup = build_division_average_lookup(profiles_df, fight_stats_df)

    historical_classes_by_fighter: dict[str, list[str]] = defaultdict(list)
    feature_rows: list[dict[str, Any]] = []

    for _, fight_row in sorted_fight_stats(fight_stats_df).iterrows():
        fighter = clean_text(fight_row.get("fighter", ""))
        fight_url = clean_text(fight_row.get("fight_url", ""))
        weight_class = clean_text(fight_row.get("weight_class", ""))

        if not fighter or not fight_url:
            continue

        fighter_key = normalize_name(fighter)
        history = historical_classes_by_fighter[fighter_key]

        feature_rows.append(
            {
                "fight_url": fight_url,
                "fighter": fighter,
                **build_weight_size_feature_row(
                    fighter=fighter,
                    current_weight_class=weight_class,
                    historical_weight_classes=history,
                    profile_lookup=profile_lookup,
                    division_average_lookup=division_average_lookup,
                ),
            }
        )

        if weight_class:
            history.append(weight_class)

    features_df = pd.DataFrame(feature_rows)

    if features_df.empty:
        updated_df = snapshots_df.copy()

        for column in WEIGHT_SIZE_FEATURE_COLUMNS:
            if column not in updated_df.columns:
                updated_df[column] = pd.NA

        return updated_df

    updated_df = snapshots_df.drop(
        columns=[column for column in WEIGHT_SIZE_FEATURE_COLUMNS if column in snapshots_df.columns],
        errors="ignore",
    ).merge(
        features_df,
        on=["fight_url", "fighter"],
        how="left",
    )

    return updated_df


def add_weight_size_features_to_current_features(
    profiles_df: pd.DataFrame,
    current_features_df: pd.DataFrame,
    fight_stats_df: pd.DataFrame,
) -> pd.DataFrame:
    if current_features_df.empty:
        return current_features_df.copy()

    if "fighter" not in current_features_df.columns:
        raise ValueError("current_fighter_features.csv must include fighter.")

    profile_lookup = build_profile_lookup(profiles_df)
    division_average_lookup = build_division_average_lookup(profiles_df, fight_stats_df)

    historical_classes_by_fighter: dict[str, list[str]] = defaultdict(list)

    for _, fight_row in sorted_fight_stats(fight_stats_df).iterrows():
        fighter = clean_text(fight_row.get("fighter", ""))
        weight_class = clean_text(fight_row.get("weight_class", ""))

        if not fighter or not weight_class:
            continue

        historical_classes_by_fighter[normalize_name(fighter)].append(weight_class)

    feature_rows: list[dict[str, Any]] = []

    for _, row in current_features_df.iterrows():
        fighter = clean_text(row.get("fighter", ""))
        fighter_key = normalize_name(fighter)
        history = historical_classes_by_fighter.get(fighter_key, [])

        current_weight_class = clean_text(row.get("weight_class", ""))

        if not current_weight_class and history:
            current_weight_class = history[-1]

        feature_rows.append(
            {
                "fighter": fighter,
                **build_weight_size_feature_row(
                    fighter=fighter,
                    current_weight_class=current_weight_class,
                    historical_weight_classes=history,
                    profile_lookup=profile_lookup,
                    division_average_lookup=division_average_lookup,
                ),
            }
        )

    features_df = pd.DataFrame(feature_rows)

    return current_features_df.drop(
        columns=[column for column in WEIGHT_SIZE_FEATURE_COLUMNS if column in current_features_df.columns],
        errors="ignore",
    ).merge(
        features_df,
        on="fighter",
        how="left",
    )


def save_snapshots_with_weight_size_features(df: pd.DataFrame) -> None:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(FIGHTER_SNAPSHOTS_CSV, index=False)


def add_weight_size_features() -> dict[str, Any]:
    profiles_df, snapshots_df, fight_stats_df = load_weight_size_inputs()

    updated_snapshots_df = add_weight_size_features_to_snapshots(
        profiles_df=profiles_df,
        snapshots_df=snapshots_df,
        fight_stats_df=fight_stats_df,
    )

    save_snapshots_with_weight_size_features(updated_snapshots_df)

    missing_rates = {
        column: float(updated_snapshots_df[column].isna().mean())
        for column in WEIGHT_SIZE_FEATURE_COLUMNS
        if column in updated_snapshots_df.columns
    }

    return {
        "fighter_snapshots": len(updated_snapshots_df),
        "weight_size_columns_present": [
            column for column in WEIGHT_SIZE_FEATURE_COLUMNS if column in updated_snapshots_df.columns
        ],
        "weight_size_missing_rates": missing_rates,
        "output_file": str(FIGHTER_SNAPSHOTS_CSV),
    }


def main() -> None:
    summary = add_weight_size_features()

    print("Added weight/size features.")
    print(summary)


if __name__ == "__main__":
    main()
