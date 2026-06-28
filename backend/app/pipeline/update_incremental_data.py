from __future__ import annotations

import json
import os
import time
import traceback
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from app.data.restore_fighter_dobs import restore_fighter_dobs_from_backup

from app.data.scrape_fighter_images import (
    FIGHTER_IMAGES_CSV,
    scrape_fighter_images,
)

from app.services.odds_service import refresh_future_fight_odds

from app.services.prediction_service import clear_prediction_cache

from app.services.saved_prediction_service import (
    save_predictions_for_all_future_cards,
    SAVED_CARD_PREDICTIONS_CSV,
    SAVED_MODEL_PREDICTIONS_CSV,
)

from app.repositories import (
    event_fights_repository,
    saved_model_predictions_repository,
    saved_predictions_repository,
)

from app.data.scrape_ufcstats import (
    fetch_completed_events,
    save_completed_events_csv,
)

from app.data.scrape_event_fights import (
    EventFight,
    fetch_fights_for_event,
)

from app.data.scrape_fight_details import (
    build_fighter_stat_rows,
    get_soup,
)

from app.data.scrape_fight_round_stats import (
    scrape_round_stats as scrape_round_stats_incrementally,
)

from app.features.add_cardio_features import (
    add_cardio_features,
    load_round_stats as load_cardio_round_stats,
)

from app.data.scrape_fighter_profiles import (
    scrape_all_fighter_profiles,
    save_profiles_csv,
)

from app.features.build_fighter_snapshots import (
    load_fight_stats,
    build_fighter_snapshots,
    save_fighter_snapshots,
)

from app.features.add_elo_features import (
    load_snapshots,
    add_elo_features,
    save_snapshots_with_elo,
)

from app.features.add_physical_features import (
    load_inputs,
    add_physical_features_to_snapshots,
    save_snapshots,
)
from app.features.add_weight_size_features import add_weight_size_features

from app.features.build_matchups import (
    load_fighter_snapshots,
    build_matchup_training_rows,
    save_training_matchups,
)
from app.features.fight_context_features import FIGHT_CONTEXT_NUMERIC_FEATURES

from app.features.build_current_fighter_features import (
    load_fight_stats as load_current_feature_fight_stats,
    load_fighter_snapshots as load_current_feature_snapshots,
    prepare_fight_history,
    build_current_features,
    save_current_features,
)

from app.models.train_calibrated_models import main as train_calibrated_models
from app.models.train_market_shadow_models import (
    MARKET_SHADOW_METRICS_PATH,
    MARKET_SHADOW_REGISTRY_PATH,
    main as train_market_shadow_models,
)

from app.services.future_card_service import refresh_upcoming_cards

from app.features.add_age_features import add_age_features

from app.analysis.explore_method_labels import build_method_label_exploration
from app.features.build_method_training_data import build_method_training_data
from app.models.train_method_models import (
    BROAD_MODEL_PATH,
    DETAILED_MODEL_PATH,
    FEATURES_PATH as METHOD_FEATURES_PATH,
    METRICS_PATH as METHOD_METRICS_PATH,
    main as train_method_models_main,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"

COMPLETED_EVENTS_CSV = RAW_DATA_DIR / "completed_events.csv"
EVENT_FIGHTS_CSV = RAW_DATA_DIR / "event_fights.csv"
FIGHT_STATS_CSV = RAW_DATA_DIR / "fight_stats.csv"

LATEST_INCREMENTAL_REPORT_PATH = REPORTS_DIR / "latest_incremental_update_report.json"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def restore_fighter_dobs_stage() -> dict[str, Any]:
    return restore_fighter_dobs_from_backup()

def seconds_since(start_time: float) -> float:
    return round(time.perf_counter() - start_time, 2)

def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str) -> int | None:
    value = os.environ.get(name, "").strip()

    if not value:
        return None

    return int(value)


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name, "").strip()

    if not value:
        return default

    return float(value)


def normalize_image_mode(value: str, default: str) -> str:
    allowed_modes = {"priority", "future", "current", "all"}
    mode = value.strip().lower() or default

    if mode not in allowed_modes:
        print(
            f"Invalid FIGHTER_IMAGE_MODE={value!r}. "
            f"Using default mode: {default}"
        )
        return default

    return mode



def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""

    return " ".join(str(value).split())


def count_csv_rows(path: Path) -> int | None:
    if not path.exists():
        return None

    try:
        return int(len(pd.read_csv(path)))
    except Exception:
        return None

def build_method_labels_stage() -> dict[str, Any]:
    summary = build_method_label_exploration()

    return {
        "fight_rows": summary["metadata"]["fight_rows"],
        "major_weight_class_rows": summary["metadata"]["major_weight_class_rows"],
        "output_csv": summary["metadata"]["output_csv"],
        "broad_counts": summary["broad_counts"],
        "detailed_counts": summary["detailed_counts"],
    }


def build_method_training_data_stage() -> dict[str, Any]:
    return build_method_training_data()


def train_method_models_stage() -> dict[str, Any]:
    train_method_models_main()

    return {
        "broad_model": str(BROAD_MODEL_PATH),
        "detailed_model": str(DETAILED_MODEL_PATH),
        "features": str(METHOD_FEATURES_PATH),
        "metrics": str(METHOD_METRICS_PATH),
    }


def read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def find_event_urls_with_incomplete_results(event_fights_df: pd.DataFrame) -> set[str]:
    if event_fights_df.empty or "event_url" not in event_fights_df.columns:
        return set()

    result_columns = ["result_1", "result_2", "winner", "loser", "method"]
    df = event_fights_df.copy()

    for column in result_columns:
        if column not in df.columns:
            df[column] = ""

    result_text = df[result_columns].fillna("").apply(
        lambda column: column.map(clean_text)
    )
    blank_result_rows = result_text.eq("").all(axis=1)

    return set(
        df.loc[blank_result_rows, "event_url"]
        .dropna()
        .astype(str)
        .map(clean_text)
    )
    
def refresh_future_fight_odds_stage() -> dict[str, Any]:
    try:
        return {
            "available": True,
            **refresh_future_fight_odds(),
        }
    except Exception as error:
        return {
            "available": False,
            "message": "Skipped odds refresh. Set ODDS_API_KEY to enable odds.",
            "error": str(error),
        }




def refresh_fighter_images_stage() -> dict[str, Any]:
    """
    Best-effort fighter image enrichment.

    Incremental updates default to future-card coverage so routine updates do not
    attempt the entire current roster every time. Override with:
        set FIGHTER_IMAGE_MODE=current
        set FIGHTER_IMAGE_MODE=priority
        set FIGHTER_IMAGE_MODE=all
    """
    mode = normalize_image_mode(
        os.environ.get("FIGHTER_IMAGE_MODE", "future"),
        default="future",
    )

    try:
        return {
            "available": True,
            **scrape_fighter_images(
                mode=mode,
                limit=env_int("FIGHTER_IMAGE_LIMIT"),
                delay_seconds=env_float("FIGHTER_IMAGE_DELAY_SECONDS", 0.2),
                force=env_bool("FIGHTER_IMAGE_FORCE", False),
            ),
        }

    except Exception as error:
        return {
            "available": False,
            "message": "Skipped fighter image refresh.",
            "error": str(error),
            "output_file": str(FIGHTER_IMAGES_CSV),
        }


def write_dataframe_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def run_stage(
    name: str,
    action: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    print()
    print("=" * 80)
    print(f"Starting stage: {name}")
    print("=" * 80)

    start_time = time.perf_counter()

    try:
        details = action()

        report = {
            "name": name,
            "status": "success",
            "duration_seconds": seconds_since(start_time),
            "details": details,
            "error": None,
        }

        print()
        print(f"Finished stage: {name}")
        print(f"Duration: {report['duration_seconds']} seconds")

        return report

    except Exception as error:
        report = {
            "name": name,
            "status": "failed",
            "duration_seconds": seconds_since(start_time),
            "details": {},
            "error": {
                "message": str(error),
                "traceback": traceback.format_exc(),
            },
        }

        print()
        print(f"FAILED stage: {name}")
        print(str(error))

        return report


def refresh_completed_events_stage() -> dict[str, Any]:
    events = fetch_completed_events()
    save_completed_events_csv(events)

    return {
        "completed_events": len(events),
        "output_file": str(COMPLETED_EVENTS_CSV),
    }

def add_age_features_stage() -> dict[str, Any]:
    return add_age_features()

def update_event_fights_incrementally_stage() -> dict[str, Any]:
    if not COMPLETED_EVENTS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {COMPLETED_EVENTS_CSV}. Refresh completed events first."
        )

    completed_events_df = pd.read_csv(COMPLETED_EVENTS_CSV)
    existing_fights_df = event_fights_repository.read_all_df()

    if existing_fights_df.empty or "event_url" not in existing_fights_df.columns:
        existing_event_urls = set()
    else:
        existing_event_urls = set(
            existing_fights_df["event_url"]
            .dropna()
            .astype(str)
            .map(clean_text)
        )

    incomplete_event_urls = find_event_urls_with_incomplete_results(existing_fights_df)

    new_fight_rows: list[dict[str, Any]] = []

    completed_events_df["url_clean"] = completed_events_df["url"].astype(str).map(clean_text)

    missing_events_df = completed_events_df[
        ~completed_events_df["url_clean"].isin(existing_event_urls)
    ].copy()
    incomplete_events_df = completed_events_df[
        completed_events_df["url_clean"].isin(incomplete_event_urls)
    ].copy()
    events_to_scrape_df = pd.concat(
        [missing_events_df, incomplete_events_df],
        ignore_index=True,
    ).drop_duplicates(subset=["url_clean"], keep="last")

    print(f"Completed events found: {len(completed_events_df)}")
    print(f"Events already in event_fights.csv: {len(existing_event_urls)}")
    print(f"Events missing from event_fights.csv: {len(missing_events_df)}")
    print(f"Events with incomplete fight results: {len(incomplete_events_df)}")
    print(f"Events needing fight-list scrape: {len(events_to_scrape_df)}")

    refreshed_event_urls: set[str] = set()

    for index, event in events_to_scrape_df.iterrows():
        event_name = clean_text(event["name"])
        event_date = clean_text(event["date"])
        event_location = clean_text(event["location"])
        event_url = clean_text(event["url"])
        refreshed_event_urls.add(event_url)

        print(f"Scraping new event fights: {event_name}")

        fights: list[EventFight] = fetch_fights_for_event(
            event_name=event_name,
            event_date=event_date,
            event_location=event_location,
            event_url=event_url,
        )

        print(f"    Found {len(fights)} fights.")

        for fight in fights:
            new_fight_rows.append(asdict(fight))

        time.sleep(0.25)

    new_fights_df = pd.DataFrame(new_fight_rows)

    if (
        not existing_fights_df.empty
        and refreshed_event_urls
        and "event_url" in existing_fights_df.columns
    ):
        existing_fights_df = existing_fights_df[
            ~existing_fights_df["event_url"]
            .astype(str)
            .map(clean_text)
            .isin(refreshed_event_urls)
        ].copy()

    if existing_fights_df.empty:
        combined_fights_df = new_fights_df
    elif new_fights_df.empty:
        combined_fights_df = existing_fights_df
    else:
        combined_fights_df = pd.concat(
            [existing_fights_df, new_fights_df],
            ignore_index=True,
        )

    if not combined_fights_df.empty and "fight_url" in combined_fights_df.columns:
        combined_fights_df = combined_fights_df.drop_duplicates(
            subset=["fight_url"],
            keep="last",
        )

    event_fights_repository.replace_all(combined_fights_df.to_dict(orient="records"))

    return {
        "events_missing_from_event_fights": int(len(missing_events_df)),
        "events_with_incomplete_results": int(len(incomplete_events_df)),
        "events_needing_scrape": int(len(events_to_scrape_df)),
        "new_event_fights": int(len(new_fights_df)),
        "total_event_fights": int(len(combined_fights_df)),
        "output_file": str(EVENT_FIGHTS_CSV),
    }


def update_fight_stats_incrementally_stage() -> dict[str, Any]:
    event_fights_df = event_fights_repository.read_all_df()

    if event_fights_df.empty:
        raise FileNotFoundError(
            "No event_fights in the database. Update the event fight list first."
        )
    existing_stats_df = read_csv_or_empty(FIGHT_STATS_CSV)

    event_fights_df = event_fights_df[
    event_fights_df["fight_url"].notna()
    & (event_fights_df["fight_url"].astype(str).str.strip() != "")
    ].copy()

    if existing_stats_df.empty or "fight_url" not in existing_stats_df.columns:
        existing_fight_urls = set()
    else:
        existing_fight_urls = set(existing_stats_df["fight_url"].dropna().astype(str))

    missing_fights_df = event_fights_df[
        ~event_fights_df["fight_url"].astype(str).isin(existing_fight_urls)
    ].copy()

    print(f"Completed fights in event_fights.csv: {len(event_fights_df)}")
    print(f"Fights already in fight_stats.csv: {len(existing_fight_urls)}")
    print(f"Fight-detail pages needing scrape: {len(missing_fights_df)}")

    new_stat_rows: list[dict[str, Any]] = []
    skipped_fights: list[dict[str, Any]] = []

    total_missing = len(missing_fights_df)

    for scrape_number, (_, fight_row) in enumerate(missing_fights_df.iterrows(), start=1):
        fighter_1 = clean_text(fight_row["fighter_1"])
        fighter_2 = clean_text(fight_row["fighter_2"])
        fight_url = clean_text(fight_row["fight_url"])

        print(f"[{scrape_number}/{total_missing}] Scraping new fight: {fighter_1} vs {fighter_2}")

        try:
            soup = get_soup(fight_url)
            fighter_stat_rows = build_fighter_stat_rows(fight_row, soup)

            if len(fighter_stat_rows) != 2:
                raise ValueError(
                    f"Expected 2 fighter stat rows, got {len(fighter_stat_rows)}"
                )

            for fighter_stats in fighter_stat_rows:
                new_stat_rows.append(asdict(fighter_stats))

        except Exception as error:
            print(f"    SKIPPING fight because stats are unavailable: {error}")

            skipped_fights.append(
                {
                    "fighter_1": fighter_1,
                    "fighter_2": fighter_2,
                    "fight_url": fight_url,
                    "reason": str(error),
                }
            )

        time.sleep(0.25)

    new_stats_df = pd.DataFrame(new_stat_rows)

    if existing_stats_df.empty:
        combined_stats_df = new_stats_df
    elif new_stats_df.empty:
        combined_stats_df = existing_stats_df
    else:
        combined_stats_df = pd.concat(
            [existing_stats_df, new_stats_df],
            ignore_index=True,
        )

    if not combined_stats_df.empty and {"fight_url", "fighter"}.issubset(combined_stats_df.columns):
        combined_stats_df = combined_stats_df.drop_duplicates(
            subset=["fight_url", "fighter"],
            keep="last",
        )

    write_dataframe_csv(combined_stats_df, FIGHT_STATS_CSV)

    return {
        "missing_fights_checked": int(len(missing_fights_df)),
        "missing_fights_scraped": int(len(new_stats_df) / 2) if not new_stats_df.empty else 0,
        "skipped_fights": skipped_fights,
        "skipped_fight_count": int(len(skipped_fights)),
        "new_fighter_stat_rows": int(len(new_stats_df)),
        "total_fighter_stat_rows": int(len(combined_stats_df)),
        "output_file": str(FIGHT_STATS_CSV),
    }


def update_round_stats_incrementally_stage() -> dict[str, Any]:
    # Scrapes per-round stats only for fights not already in fight_round_stats.csv.
    return scrape_round_stats_incrementally(only_missing=True)


def refresh_fighter_profiles_stage() -> dict[str, Any]:
    profiles = scrape_all_fighter_profiles()
    save_profiles_csv(profiles)

    return {
        "fighter_profiles": len(profiles),
        "output_file": str(RAW_DATA_DIR / "fighter_profiles.csv"),
    }


def build_fighter_snapshots_stage() -> dict[str, Any]:
    fight_stats_df = load_fight_stats()
    snapshots_df = build_fighter_snapshots(fight_stats_df)
    save_fighter_snapshots(snapshots_df)

    generated_columns = [
        column
        for column in snapshots_df.columns
        if column.startswith(("bayes_", "decayed_", "path_", "style_", "vulnerability_"))
        or column.startswith("avg_opponent_adjusted_")
        or column.startswith("recent_3_opponent_adjusted_")
        or column.startswith("volatility_")
        or column in {"sample_reliability", "durability_risk_score"}
    ]

    return {
        "fighter_snapshots": len(snapshots_df),
        "generated_analytics_columns": len(generated_columns),
        "output_file": str(PROCESSED_DATA_DIR / "fighter_snapshots.csv"),
    }


def add_elo_features_stage() -> dict[str, Any]:
    snapshots_df = load_snapshots()
    snapshots_with_elo_df = add_elo_features(snapshots_df)
    save_snapshots_with_elo(snapshots_with_elo_df)

    return {
        "fighter_snapshots": len(snapshots_with_elo_df),
        "output_file": str(PROCESSED_DATA_DIR / "fighter_snapshots.csv"),
    }


def add_cardio_features_stage() -> dict[str, Any]:
    snapshots_df = load_snapshots()
    round_stats_df = load_cardio_round_stats()

    updated_snapshots_df = add_cardio_features(snapshots_df, round_stats_df)
    save_snapshots(updated_snapshots_df)

    coverage = 0
    if "prior_avg_cardio_sig_output_slope" in updated_snapshots_df.columns:
        coverage = int(updated_snapshots_df["prior_avg_cardio_sig_output_slope"].notna().sum())

    return {
        "fighter_snapshots": len(updated_snapshots_df),
        "round_rows_available": int(len(round_stats_df)),
        "rows_with_prior_cardio": coverage,
        "output_file": str(PROCESSED_DATA_DIR / "fighter_snapshots.csv"),
    }


def add_physical_features_stage() -> dict[str, Any]:
    profiles_df, snapshots_df = load_inputs()

    updated_snapshots_df = add_physical_features_to_snapshots(
        profiles_df=profiles_df,
        snapshots_df=snapshots_df,
    )

    save_snapshots(updated_snapshots_df)

    physical_columns = [
        "height_inches",
        "reach_inches",
        "reach_minus_height_inches",
        "is_orthodox",
        "is_southpaw",
        "is_switch_stance",
        "is_open_stance",
        "is_sideways_stance",
        "is_stance_unknown",
    ]

    missing_rates = {}

    for column in physical_columns:
        if column in updated_snapshots_df.columns:
            missing_rates[column] = float(updated_snapshots_df[column].isna().mean())

    return {
        "fighter_snapshots": len(updated_snapshots_df),
        "physical_missing_rates": missing_rates,
        "output_file": str(PROCESSED_DATA_DIR / "fighter_snapshots.csv"),
    }


def add_weight_size_features_stage() -> dict[str, Any]:
    return add_weight_size_features()


def build_matchups_stage() -> dict[str, Any]:
    snapshots_df = load_fighter_snapshots()
    matchups_df = build_matchup_training_rows(snapshots_df)
    save_training_matchups(matchups_df)

    return {
        "training_matchup_rows": len(matchups_df),
        "unique_fights": int(matchups_df["fight_url"].nunique()),
        "diff_feature_columns": len(
            [
                column
                for column in matchups_df.columns
                if column.startswith("diff_")
            ]
        ),
        "direct_fight_context_columns": [
            column for column in FIGHT_CONTEXT_NUMERIC_FEATURES if column in matchups_df.columns
        ],
        "output_file": str(PROCESSED_DATA_DIR / "training_matchups.csv"),
    }


def train_model_stage() -> dict[str, Any]:
    train_calibrated_models()

    metrics_path = PROJECT_ROOT / "models" / "calibrated_model_metrics.json"

    metrics = {}

    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as file:
            metrics = json.load(file)

    best_model_name = metrics.get("best_model_name")

    return {
        "best_model_name": best_model_name,
        "best_model_metrics": metrics.get("results", {}).get(best_model_name, {}),
        "metrics_file": str(metrics_path),
        "model_file": str(PROJECT_ROOT / "models" / "best_winner_model.joblib"),
    }


def train_market_shadow_models_stage() -> dict[str, Any]:
    train_market_shadow_models()

    metrics = {}

    if MARKET_SHADOW_METRICS_PATH.exists():
        with open(MARKET_SHADOW_METRICS_PATH, "r", encoding="utf-8") as file:
            metrics = json.load(file)

    return {
        "available": bool(metrics.get("available", False)),
        "training_rows": metrics.get("training_rows", 0),
        "model_names": metrics.get("model_names", []),
        "metrics_file": str(MARKET_SHADOW_METRICS_PATH),
        "registry_file": str(MARKET_SHADOW_REGISTRY_PATH),
    }


def build_current_fighter_features_stage() -> dict[str, Any]:
    fight_stats_df = load_current_feature_fight_stats()
    snapshots_df = load_current_feature_snapshots()

    engineered_df = prepare_fight_history(fight_stats_df)

    current_features_df = build_current_features(
        engineered_df=engineered_df,
        snapshots_df=snapshots_df,
    )

    save_current_features(current_features_df)

    return {
        "current_fighter_rows": len(current_features_df),
        "output_file": str(PROCESSED_DATA_DIR / "current_fighter_features.csv"),
    }


def refresh_future_cards_stage() -> dict[str, Any]:
    result = refresh_upcoming_cards()

    return {
        **result,
        "upcoming_events_file": str(RAW_DATA_DIR / "upcoming_events.csv"),
        "upcoming_fights_file": str(RAW_DATA_DIR / "upcoming_fights.csv"),
    }


def build_summary(stage_reports: list[dict[str, Any]]) -> dict[str, Any]:
    failed_stages = [
        stage["name"]
        for stage in stage_reports
        if stage["status"] != "success"
    ]

    return {
        "completed_events_rows": count_csv_rows(COMPLETED_EVENTS_CSV),
        "event_fights_rows": event_fights_repository.count(),
        "fight_stats_rows": count_csv_rows(FIGHT_STATS_CSV),
        "fighter_profiles_rows": count_csv_rows(RAW_DATA_DIR / "fighter_profiles.csv"),
        "fighter_snapshots_rows": count_csv_rows(PROCESSED_DATA_DIR / "fighter_snapshots.csv"),
        "training_matchups_rows": count_csv_rows(PROCESSED_DATA_DIR / "training_matchups.csv"),
        "current_fighter_features_rows": count_csv_rows(PROCESSED_DATA_DIR / "current_fighter_features.csv"),
        "upcoming_events_rows": count_csv_rows(RAW_DATA_DIR / "upcoming_events.csv"),
        "upcoming_fights_rows": count_csv_rows(RAW_DATA_DIR / "upcoming_fights.csv"),
        "fighter_images_rows": count_csv_rows(RAW_DATA_DIR / "fighter_images.csv"),
        "failed_stages": failed_stages,
        "success": len(failed_stages) == 0,
        "saved_card_predictions_rows": saved_predictions_repository.count(),
        "saved_model_predictions_rows": saved_model_predictions_repository.count(),
    }


def save_report(report: dict[str, Any]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_path = REPORTS_DIR / f"incremental_update_report_{timestamp}.json"

    with open(timestamped_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    with open(LATEST_INCREMENTAL_REPORT_PATH, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print()
    print(f"Saved report: {timestamped_path}")
    print(f"Saved latest incremental report: {LATEST_INCREMENTAL_REPORT_PATH}")


def run_incremental_update(
    stop_on_failure: bool = True,
    status_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    pipeline_start = time.perf_counter()
    started_at = datetime.now().isoformat(timespec="seconds")

    stages: list[tuple[str, Callable[[], dict[str, Any]]]] = [
        ("Refresh completed events", refresh_completed_events_stage),
        ("Update completed fight list incrementally", update_event_fights_incrementally_stage),
        ("Update fight stats incrementally", update_fight_stats_incrementally_stage),
        ("Update fight round stats incrementally", update_round_stats_incrementally_stage),
        ("Refresh fighter profiles", refresh_fighter_profiles_stage),
        ("Restore fighter DOBs", restore_fighter_dobs_stage),
        ("Build fighter snapshots", build_fighter_snapshots_stage),
        ("Add Elo features", add_elo_features_stage),
        ("Add physical features", add_physical_features_stage),
        ("Add weight/size features", add_weight_size_features_stage),
        ("Add age features", add_age_features_stage),
        ("Add cardio features", add_cardio_features_stage),
        ("Build matchup training rows", build_matchups_stage),
        ("Build method labels", build_method_labels_stage),
        ("Build method training data", build_method_training_data_stage),
        ("Train method models", train_method_models_stage),
        ("Train calibrated model", train_model_stage),
        ("Build current fighter features", build_current_fighter_features_stage),
        ("Add current age features", add_age_features_stage),
        ("Refresh future cards", refresh_future_cards_stage),
        ("Refresh fighter images", refresh_fighter_images_stage),
        ("Refresh future fight odds", refresh_future_fight_odds_stage),
        ("Train market shadow models", train_market_shadow_models_stage),
        ("Save future-card predictions", save_future_card_predictions_stage),
]

    total_stages = len(stages)
    stage_reports = []

    for stage_index, (stage_name, stage_action) in enumerate(stages, start=1):
        if status_callback is not None:
            status_callback(
                {
                    "running": True,
                    "current_stage": stage_name,
                    "current_stage_index": stage_index,
                    "total_stages": total_stages,
                    "progress_percent": int(((stage_index - 1) / total_stages) * 100),
                    "message": f"Starting stage {stage_index}/{total_stages}: {stage_name}",
                }
            )

        stage_report = run_stage(stage_name, stage_action)
        stage_reports.append(stage_report)

        if status_callback is not None:
            status_callback(
                {
                    "running": True,
                    "current_stage": stage_name,
                    "current_stage_index": stage_index,
                    "total_stages": total_stages,
                    "progress_percent": int((stage_index / total_stages) * 100),
                    "message": f"Finished stage {stage_index}/{total_stages}: {stage_name}",
                    "last_stage_status": stage_report["status"],
                }
            )

        if stage_report["status"] != "success" and stop_on_failure:
            print()
            print("Stopping incremental update because a stage failed.")
            break

    report = {
        "update_type": "incremental",
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "duration_seconds": seconds_since(pipeline_start),
        "summary": build_summary(stage_reports),
        "stages": stage_reports,
    }

    save_report(report)

    if status_callback is not None:
        status_callback(
            {
                "running": False,
                "current_stage": None,
                "current_stage_index": total_stages,
                "total_stages": total_stages,
                "progress_percent": 100,
                "message": "Incremental update finished.",
                "success": report["summary"]["success"],
                "report": report,
            }
        )

    return report


def main() -> None:
    print("Running incremental UFC predictor update...")
    report = run_incremental_update(stop_on_failure=True)

    print()
    print("=" * 80)
    print("Incremental update summary")
    print("=" * 80)
    print(json.dumps(report["summary"], indent=2))

    if report["summary"]["success"]:
        print()
        print("Incremental update completed successfully.")
    else:
        print()
        print("Incremental update finished with failures.")
        print("Check data/reports/latest_incremental_update_report.json.")

def save_future_card_predictions_stage() -> dict[str, Any]:
    """
    Saves prediction snapshots for all currently listed future cards.

    This should run after:
        - model retraining
        - current fighter feature rebuild
        - future-card refresh

    We clear prediction cache first so the service uses the newly saved model
    and current_fighter_features.csv.
    """
    clear_prediction_cache()

    result = save_predictions_for_all_future_cards()

    return {
        **result,
        "saved_predictions_file": str(SAVED_CARD_PREDICTIONS_CSV),
        "saved_model_predictions_file": str(SAVED_MODEL_PREDICTIONS_CSV),
    }


if __name__ == "__main__":
    main()
