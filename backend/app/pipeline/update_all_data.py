from __future__ import annotations

import json
import os
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from app.data.restore_fighter_dobs import restore_fighter_dobs_from_backup

from app.data.scrape_fighter_images import (
    FIGHTER_IMAGES_CSV,
    scrape_fighter_images,
)

from app.data.scrape_ufcstats import (
    fetch_completed_events,
    save_completed_events_csv,
)
from app.data.scrape_event_fights import (
    scrape_event_fights,
    save_event_fights_csv,
)
from app.data.scrape_fight_details import (
    scrape_fight_stats,
    save_fight_stats_csv,
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
from app.features.build_current_fighter_features import (
    load_fight_stats as load_current_feature_fight_stats,
    load_fighter_snapshots as load_current_feature_snapshots,
    prepare_fight_history,
    build_current_features,
    save_current_features,
)
from app.models.train_calibrated_models import main as train_calibrated_models
from app.services.future_card_service import refresh_upcoming_cards
from app.services.prediction_service import clear_prediction_cache
from app.services.saved_prediction_service import (
    SAVED_CARD_PREDICTIONS_CSV,
    SAVED_MODEL_PREDICTIONS_CSV,
    save_predictions_for_all_future_cards,
)

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

LATEST_REPORT_PATH = REPORTS_DIR / "latest_update_report.json"


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

def count_csv_rows(path: Path) -> int | None:
    if not path.exists():
        return None

    try:
        return int(len(pd.read_csv(path)))
    except Exception:
        return None


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

        stage_report = {
            "name": name,
            "status": "success",
            "duration_seconds": seconds_since(start_time),
            "details": details,
            "error": None,
        }

        print()
        print(f"Finished stage: {name}")
        print(f"Duration: {stage_report['duration_seconds']} seconds")

        return stage_report

    except Exception as error:
        stage_report = {
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

        return stage_report


def stage_refresh_completed_events() -> dict[str, Any]:
    events = fetch_completed_events()
    save_completed_events_csv(events)

    return {
        "completed_events": len(events),
        "output_file": str(RAW_DATA_DIR / "completed_events.csv"),
    }


def stage_refresh_completed_fight_list() -> dict[str, Any]:
    fights = scrape_event_fights(limit=None)
    save_event_fights_csv(fights)

    return {
        "event_fights": len(fights),
        "output_file": str(RAW_DATA_DIR / "event_fights.csv"),
    }


def stage_refresh_fight_details() -> dict[str, Any]:
    rows = scrape_fight_stats(limit=None)
    save_fight_stats_csv(rows)

    return {
        "fighter_fight_rows": len(rows),
        "output_file": str(RAW_DATA_DIR / "fight_stats.csv"),
    }


def stage_refresh_fighter_profiles() -> dict[str, Any]:
    profiles = scrape_all_fighter_profiles()
    save_profiles_csv(profiles)

    return {
        "fighter_profiles": len(profiles),
        "output_file": str(RAW_DATA_DIR / "fighter_profiles.csv"),
    }


def stage_build_fighter_snapshots() -> dict[str, Any]:
    fight_stats_df = load_fight_stats()
    snapshots_df = build_fighter_snapshots(fight_stats_df)
    save_fighter_snapshots(snapshots_df)

    return {
        "fighter_snapshots": len(snapshots_df),
        "output_file": str(PROCESSED_DATA_DIR / "fighter_snapshots.csv"),
    }


def stage_add_elo_features() -> dict[str, Any]:
    snapshots_df = load_snapshots()
    snapshots_with_elo_df = add_elo_features(snapshots_df)
    save_snapshots_with_elo(snapshots_with_elo_df)

    elo_columns = [
        "prior_elo",
        "prior_peak_elo",
        "prior_lowest_elo",
        "prior_elo_change_last_3",
        "prior_elo_fights",
    ]

    return {
        "fighter_snapshots": len(snapshots_with_elo_df),
        "elo_columns_present": [
            column for column in elo_columns if column in snapshots_with_elo_df.columns
        ],
        "output_file": str(PROCESSED_DATA_DIR / "fighter_snapshots.csv"),
    }


def stage_add_physical_features() -> dict[str, Any]:
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


def stage_add_weight_size_features() -> dict[str, Any]:
    return add_weight_size_features()


def stage_build_matchups() -> dict[str, Any]:
    snapshots_df = load_fighter_snapshots()
    matchups_df = build_matchup_training_rows(snapshots_df)
    save_training_matchups(matchups_df)

    return {
        "training_matchup_rows": len(matchups_df),
        "unique_fights": int(matchups_df["fight_url"].nunique()),
        "feature_columns": len(
            [
                column
                for column in matchups_df.columns
                if column.startswith("diff_")
            ]
        ),
        "output_file": str(PROCESSED_DATA_DIR / "training_matchups.csv"),
    }


def stage_train_model() -> dict[str, Any]:
    train_calibrated_models()

    metrics_path = PROJECT_ROOT / "models" / "calibrated_model_metrics.json"

    metrics = {}

    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as file:
            metrics = json.load(file)

    return {
        "best_model_name": metrics.get("best_model_name"),
        "best_model_metrics": metrics.get("results", {}).get(metrics.get("best_model_name", ""), {}),
        "metrics_file": str(metrics_path),
        "model_file": str(PROJECT_ROOT / "models" / "best_winner_model.joblib"),
    }


def stage_build_current_fighter_features() -> dict[str, Any]:
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




def stage_refresh_fighter_images() -> dict[str, Any]:
    """
    Best-effort fighter image enrichment.

    Full rebuild defaults to current roster coverage because current_fighter_features.csv
    has just been rebuilt. Override with:
        set FIGHTER_IMAGE_MODE=future
        set FIGHTER_IMAGE_MODE=priority
        set FIGHTER_IMAGE_MODE=all
    """
    mode = normalize_image_mode(
        os.environ.get("FIGHTER_IMAGE_MODE", "current"),
        default="current",
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


def stage_refresh_future_cards() -> dict[str, Any]:
    result = refresh_upcoming_cards()

    return {
        **result,
        "upcoming_events_file": str(RAW_DATA_DIR / "upcoming_events.csv"),
        "upcoming_fights_file": str(RAW_DATA_DIR / "upcoming_fights.csv"),
    }


def stage_save_future_card_predictions() -> dict[str, Any]:
    clear_prediction_cache()

    result = save_predictions_for_all_future_cards()

    return {
        **result,
        "saved_predictions_file": str(SAVED_CARD_PREDICTIONS_CSV),
        "saved_model_predictions_file": str(SAVED_MODEL_PREDICTIONS_CSV),
    }


def build_summary_report(stage_reports: list[dict[str, Any]]) -> dict[str, Any]:
    completed_events_path = RAW_DATA_DIR / "completed_events.csv"
    event_fights_path = RAW_DATA_DIR / "event_fights.csv"
    fight_stats_path = RAW_DATA_DIR / "fight_stats.csv"
    fighter_profiles_path = RAW_DATA_DIR / "fighter_profiles.csv"
    fighter_snapshots_path = PROCESSED_DATA_DIR / "fighter_snapshots.csv"
    training_matchups_path = PROCESSED_DATA_DIR / "training_matchups.csv"
    current_features_path = PROCESSED_DATA_DIR / "current_fighter_features.csv"
    upcoming_events_path = RAW_DATA_DIR / "upcoming_events.csv"
    upcoming_fights_path = RAW_DATA_DIR / "upcoming_fights.csv"

    failed_stages = [
        stage["name"]
        for stage in stage_reports
        if stage["status"] != "success"
    ]

    return {
        "completed_events_rows": count_csv_rows(completed_events_path),
        "event_fights_rows": count_csv_rows(event_fights_path),
        "fight_stats_rows": count_csv_rows(fight_stats_path),
        "fighter_profiles_rows": count_csv_rows(fighter_profiles_path),
        "fighter_snapshots_rows": count_csv_rows(fighter_snapshots_path),
        "training_matchups_rows": count_csv_rows(training_matchups_path),
        "current_fighter_features_rows": count_csv_rows(current_features_path),
        "upcoming_events_rows": count_csv_rows(upcoming_events_path),
        "upcoming_fights_rows": count_csv_rows(upcoming_fights_path),
        "fighter_images_rows": count_csv_rows(RAW_DATA_DIR / "fighter_images.csv"),
        "saved_card_predictions_rows": count_csv_rows(SAVED_CARD_PREDICTIONS_CSV),
        "saved_model_predictions_rows": count_csv_rows(SAVED_MODEL_PREDICTIONS_CSV),
        "failed_stages": failed_stages,
        "success": len(failed_stages) == 0,
    }


def save_report(report: dict[str, Any]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_report_path = REPORTS_DIR / f"update_report_{timestamp}.json"

    with open(timestamped_report_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    with open(LATEST_REPORT_PATH, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    print()
    print(f"Saved report: {timestamped_report_path}")
    print(f"Saved latest report: {LATEST_REPORT_PATH}")


def run_update_all(stop_on_failure: bool = True) -> dict[str, Any]:
    started_at = now_iso()
    pipeline_start = time.perf_counter()

    stages: list[tuple[str, Callable[[], dict[str, Any]]]] = [
        ("Refresh completed events", stage_refresh_completed_events),
        ("Refresh completed fight list", stage_refresh_completed_fight_list),
        ("Refresh detailed fight stats", stage_refresh_fight_details),
        ("Refresh fighter profiles", stage_refresh_fighter_profiles),
        ("Restore fighter DOBs", restore_fighter_dobs_stage),
        ("Build fighter snapshots", stage_build_fighter_snapshots),
        ("Add Elo features", stage_add_elo_features),
        ("Add physical features", stage_add_physical_features),
        ("Add weight/size features", stage_add_weight_size_features),
        ("Build matchup training rows", stage_build_matchups),
        ("Build method labels", build_method_labels_stage),
        ("Build method training data", build_method_training_data_stage),
        ("Train method models", train_method_models_stage),
        ("Train calibrated model", stage_train_model),
        ("Build current fighter features", stage_build_current_fighter_features),
        ("Refresh future cards", stage_refresh_future_cards),
        ("Save future-card predictions", stage_save_future_card_predictions),
        ("Refresh fighter images", stage_refresh_fighter_images),
    ]

    stage_reports = []

    for stage_name, stage_action in stages:
        stage_report = run_stage(stage_name, stage_action)
        stage_reports.append(stage_report)

        if stage_report["status"] != "success" and stop_on_failure:
            print()
            print("Stopping pipeline because a stage failed.")
            break

    summary = build_summary_report(stage_reports)

    report = {
        "started_at": started_at,
        "finished_at": now_iso(),
        "duration_seconds": seconds_since(pipeline_start),
        "summary": summary,
        "stages": stage_reports,
    }

    save_report(report)

    return report


def main() -> None:
    print("Running full UFC predictor data/model update...")
    report = run_update_all(stop_on_failure=True)

    print()
    print("=" * 80)
    print("Update summary")
    print("=" * 80)
    print(json.dumps(report["summary"], indent=2))

    if report["summary"]["success"]:
        print()
        print("Update completed successfully.")
    else:
        print()
        print("Update finished with failures. Check data/reports/latest_update_report.json.")


if __name__ == "__main__":
    main()