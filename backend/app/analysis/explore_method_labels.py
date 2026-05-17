from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"

FIGHT_STATS_CSV = RAW_DATA_DIR / "fight_stats.csv"

OUTPUT_CSV = REPORTS_DIR / "method_label_exploration.csv"
OUTPUT_JSON = REPORTS_DIR / "method_label_summary.json"


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


CHOKE_KEYWORDS = [
    "choke",
    "triangle",
    "d'arce",
    "darce",
    "anaconda",
    "neck crank",
    "bulldog",
    "ezekiel",
    "forearm",
    "north-south",
    "von flue",
    "peruvian",
    "schultz",
    "twister",
]


JOINT_LOCK_KEYWORDS = [
    "armbar",
    "kimura",
    "keylock",
    "kneebar",
    "heel hook",
    "ankle lock",
    "calf slicer",
    "suloev",
    "omoplata",
    "lock",
]


PUNCH_KO_KEYWORDS = [
    "punch",
    "punches",
]


KICK_KNEE_ELBOW_KO_KEYWORDS = [
    "kick",
    "kicks",
    "knee",
    "knees",
    "elbow",
    "elbows",
    "flying knee",
    "spinning back kick",
    "spinning back fist",
    "spinning back elbow",
    "slam",
]


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def load_fight_stats() -> pd.DataFrame:
    if not FIGHT_STATS_CSV.exists():
        raise FileNotFoundError(f"Missing {FIGHT_STATS_CSV}")

    df = pd.read_csv(FIGHT_STATS_CSV)

    required_columns = [
        "fight_url",
        "fighter",
        "opponent",
        "result",
        "is_winner",
        "weight_class",
        "method",
        "round",
        "time",
        "event_name",
        "event_date",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "fight_stats.csv is missing required columns: "
            + ", ".join(missing_columns)
        )

    return df


def build_fight_level_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    fight_stats.csv has two rows per fight.
    For method labels, use one row per fight.

    Prefer the winner row when available. If not, use the first row for that fight.
    """
    rows = []

    for fight_url, group_df in df.groupby("fight_url", dropna=False):
        winner_rows = group_df[group_df["result"].astype(str).str.lower() == "win"].copy()

        if not winner_rows.empty:
            row = winner_rows.iloc[0]
        else:
            row = group_df.iloc[0]

        loser_rows = group_df[group_df.index != row.name]

        if not loser_rows.empty:
            loser_name = clean_text(loser_rows.iloc[0].get("fighter", ""))
        else:
            loser_name = clean_text(row.get("opponent", ""))

        rows.append(
            {
                "fight_url": clean_text(fight_url),
                "event_name": clean_text(row.get("event_name", "")),
                "event_date": clean_text(row.get("event_date", "")),
                "weight_class": clean_text(row.get("weight_class", "")),
                "winner": clean_text(row.get("fighter", "")),
                "loser": loser_name,
                "method": clean_text(row.get("method", "")),
                "round": row.get("round"),
                "time": clean_text(row.get("time", "")),
            }
        )

    fight_df = pd.DataFrame(rows)
    fight_df["event_date_parsed"] = pd.to_datetime(
        fight_df["event_date"],
        errors="coerce",
    )

    return fight_df.sort_values("event_date_parsed").reset_index(drop=True)


def contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify_broad_method(method: str) -> str:
    method_clean = clean_text(method).upper()

    if not method_clean:
        return "Unknown"

    if method_clean in {"U-DEC", "S-DEC", "M-DEC"} or "DEC" in method_clean:
        return "Decision"

    if method_clean.startswith("KO/TKO") or method_clean.startswith("TKO") or method_clean.startswith("KO"):
        return "KO/TKO"

    if method_clean.startswith("SUB"):
        return "Submission"

    if method_clean.startswith("DQ"):
        return "Other"

    if "OVERTURNED" in method_clean or "NC" in method_clean:
        return "Other"

    return "Other"


def classify_detailed_method(method: str) -> str:
    method_clean = clean_text(method)
    method_lower = method_clean.lower()
    method_upper = method_clean.upper()

    if not method_clean:
        return "Unknown"

    if method_upper == "U-DEC":
        return "Unanimous decision"

    if method_upper in {"S-DEC", "M-DEC"}:
        return "Split/majority decision"

    if "DEC" in method_upper:
        return "Other decision"

    if method_upper.startswith("KO/TKO") or method_upper.startswith("TKO") or method_upper.startswith("KO"):
        if contains_any(method_lower, PUNCH_KO_KEYWORDS):
            return "Punch-based KO/TKO"

        if contains_any(method_lower, KICK_KNEE_ELBOW_KO_KEYWORDS):
            return "Kick/knee/elbow/slam KO/TKO"

        return "General/other KO/TKO"

    if method_upper.startswith("SUB"):
        if "injury" in method_lower:
            return "Submission - injury/other"

        if contains_any(method_lower, CHOKE_KEYWORDS):
            return "Choke submission"

        if contains_any(method_lower, JOINT_LOCK_KEYWORDS):
            return "Joint/lock submission"

        return "Other submission"

    if method_upper.startswith("DQ"):
        return "DQ/other"

    return "Other/unknown"


def build_summary(fight_df: pd.DataFrame) -> dict[str, Any]:
    broad_counts = fight_df["broad_method"].value_counts(dropna=False)
    detailed_counts = fight_df["detailed_method"].value_counts(dropna=False)
    raw_method_counts = fight_df["method"].value_counts(dropna=False)

    major_weight_df = fight_df[fight_df["weight_class"].isin(MAJOR_WEIGHT_CLASSES)].copy()

    by_weight_and_broad = (
        major_weight_df
        .pivot_table(
            index="weight_class",
            columns="broad_method",
            values="fight_url",
            aggfunc="count",
            fill_value=0,
        )
        .reset_index()
    )

    by_weight_and_detailed = (
        major_weight_df
        .pivot_table(
            index="weight_class",
            columns="detailed_method",
            values="fight_url",
            aggfunc="count",
            fill_value=0,
        )
        .reset_index()
    )

    return {
        "metadata": {
            "source_file": str(FIGHT_STATS_CSV),
            "fight_rows": int(len(fight_df)),
            "major_weight_class_rows": int(len(major_weight_df)),
            "output_csv": str(OUTPUT_CSV),
        },
        "broad_counts": broad_counts.to_dict(),
        "detailed_counts": detailed_counts.to_dict(),
        "raw_method_counts_top_50": raw_method_counts.head(50).to_dict(),
        "by_weight_class_broad": by_weight_and_broad.to_dict(orient="records"),
        "by_weight_class_detailed": by_weight_and_detailed.to_dict(orient="records"),
    }


def print_counts(title: str, series: pd.Series) -> None:
    print()
    print(title)
    print("=" * 80)
    print(series.to_string())


def build_method_label_exploration() -> dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    df = load_fight_stats()
    fight_df = build_fight_level_df(df)

    fight_df["broad_method"] = fight_df["method"].apply(classify_broad_method)
    fight_df["detailed_method"] = fight_df["method"].apply(classify_detailed_method)

    fight_df.to_csv(OUTPUT_CSV, index=False)

    summary = build_summary(fight_df)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    return summary

def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    df = load_fight_stats()
    fight_df = build_fight_level_df(df)

    fight_df["broad_method"] = fight_df["method"].apply(classify_broad_method)
    fight_df["detailed_method"] = fight_df["method"].apply(classify_detailed_method)

    fight_df.to_csv(OUTPUT_CSV, index=False)

    summary = build_summary(fight_df)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    print()
    print("Method label exploration")
    print("=" * 80)
    print(f"Fight-level rows: {len(fight_df)}")
    print(f"Saved CSV: {OUTPUT_CSV}")
    print(f"Saved JSON: {OUTPUT_JSON}")

    print_counts(
        "Broad method counts",
        fight_df["broad_method"].value_counts(dropna=False),
    )

    print_counts(
        "Detailed method counts",
        fight_df["detailed_method"].value_counts(dropna=False),
    )

    print_counts(
        "Raw method counts, fight-level top 50",
        fight_df["method"].value_counts(dropna=False).head(50),
    )

    print()
    print("Sample labeled rows")
    print("=" * 80)
    print(
        fight_df[
            [
                "event_date",
                "winner",
                "loser",
                "weight_class",
                "method",
                "broad_method",
                "detailed_method",
            ]
        ]
        .tail(25)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()