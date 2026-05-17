from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from app.pipeline.update_incremental_data import (
    LATEST_INCREMENTAL_REPORT_PATH,
    run_incremental_update,
)
from app.services.prediction_service import clear_prediction_cache

from app.services.method_prediction_service import clear_method_prediction_cache


PROJECT_ROOT = Path(__file__).resolve().parents[2]

_status_lock = threading.Lock()
_update_thread: threading.Thread | None = None


_update_status: dict[str, Any] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "current_stage": None,
    "current_stage_index": 0,
    "total_stages": 18,
    "progress_percent": 0,
    "message": "No update has been started.",
    "success": None,
    "error": None,
    "report": None,
}


def _set_status(updates: dict[str, Any]) -> None:
    with _status_lock:
        _update_status.update(updates)


def get_update_status() -> dict[str, Any]:
    with _status_lock:
        return deepcopy(_update_status)


def get_latest_update_report() -> dict[str, Any]:
    if not LATEST_INCREMENTAL_REPORT_PATH.exists():
        return {
            "available": False,
            "message": "No incremental update report exists yet.",
            "report": None,
        }

    with open(LATEST_INCREMENTAL_REPORT_PATH, "r", encoding="utf-8") as file:
        report = json.load(file)

    return {
        "available": True,
        "message": "Latest incremental update report loaded.",
        "report": report,
    }


def _progress_callback(update: dict[str, Any]) -> None:
    _set_status(update)


def _run_incremental_update_job() -> None:
    try:
        report = run_incremental_update(
            stop_on_failure=True,
            status_callback=_progress_callback,
        )

        clear_prediction_cache()
        clear_method_prediction_cache()

        _set_status(
            {
                "running": False,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "progress_percent": 100,
                "message": "Incremental update completed successfully."
                if report["summary"]["success"]
                else "Incremental update finished with failures.",
                "success": report["summary"]["success"],
                "error": None,
                "report": report,
            }
        )

    except Exception as error:
        _set_status(
            {
                "running": False,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "message": "Incremental update failed.",
                "success": False,
                "error": str(error),
            }
        )


def start_incremental_update_job() -> dict[str, Any]:
    global _update_thread

    with _status_lock:
        if _update_status["running"]:
            return {
                "started": False,
                "message": "An update is already running.",
                "status": deepcopy(_update_status),
            }

        _update_status.update(
            {
                "running": True,
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "finished_at": None,
                "current_stage": None,
                "current_stage_index": 0,
                "total_stages": 18,
                "progress_percent": 0,
                "message": "Incremental update is starting.",
                "success": None,
                "error": None,
                "report": None,
            }
        )

    _update_thread = threading.Thread(
        target=_run_incremental_update_job,
        daemon=True,
    )
    _update_thread.start()

    return {
        "started": True,
        "message": "Incremental update started.",
        "status": get_update_status(),
    }