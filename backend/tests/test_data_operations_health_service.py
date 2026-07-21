from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.data_operations_health_service import build_data_operations_health  # noqa: E402


def _duration(scored=0, pending=1):
    return {
        "prospective": {
            "status": "ready" if scored else "collecting",
            "saved_predictions": scored + pending,
            "scored_predictions": scored,
            "pending_predictions": pending,
            "invalid_predictions": 0,
        }
    }


def test_health_summarizes_refresh_totals_and_prospective_grading():
    payload = build_data_operations_health(
        now=datetime(2026, 7, 13, 12, 0, 0),
        latest_refresh={
            "finished_at": "2026-07-13T10:00:00",
            "success": 1,
            "degraded_stages": [],
            "failed_stages": [],
            "odds_available": 1,
            "provider_requests_remaining": 496,
        },
        upcoming_fights_df=pd.DataFrame([{"fight_url": "a"}, {"fight_url": "b"}]),
        current_odds_df=pd.DataFrame(
            [
                {
                    "odds_available": 1,
                    "rounds_line": 2.5,
                    "odds_match_low_confidence": 0,
                },
                {
                    "odds_available": 1,
                    "rounds_line": None,
                    "odds_match_low_confidence": 0,
                },
            ]
        ),
        totals_snapshots_df=pd.DataFrame(
            [
                {
                    "captured_at": "2026-07-13T11:00:00",
                    "fight_url": "a",
                    "bookmaker_key": "draftkings",
                    "rounds_line": 2.5,
                },
                {
                    "captured_at": "2026-07-13T11:00:00",
                    "fight_url": "a",
                    "bookmaker_key": "fanduel",
                    "rounds_line": 1.5,
                },
            ]
        ),
        saved_predictions_df=pd.DataFrame(),
        duration_evaluation=_duration(scored=1, pending=1),
    )

    assert payload["status"] == "healthy"
    assert payload["refresh"]["age_hours"] == 2.0
    assert payload["odds"]["h2h_coverage"]["percentage"] == "100.0%"
    assert payload["odds"]["totals_coverage"]["percentage"] == "50.0%"
    assert payload["totals_history"]["snapshot_rows"] == 2
    assert payload["duration_evaluation"]["scored_predictions"] == 1


def test_health_escalates_stale_refresh_and_degraded_odds():
    payload = build_data_operations_health(
        now=datetime(2026, 7, 13, 12, 0, 0),
        latest_refresh={
            "finished_at": "2026-07-10T10:00:00",
            "success": 1,
            "degraded_stages": ["Refresh future fight odds"],
            "failed_stages": [],
            "odds_available": 0,
            "odds_error_code": "provider_auth_failed",
            "odds_message": "Odds refresh did not complete.",
        },
        upcoming_fights_df=pd.DataFrame([{"fight_url": "a"}]),
        current_odds_df=pd.DataFrame(),
        totals_snapshots_df=pd.DataFrame(),
        saved_predictions_df=pd.DataFrame(),
        duration_evaluation=_duration(),
    )

    assert payload["status"] == "stale"
    codes = {alert["code"] for alert in payload["alerts"]}
    assert {"refresh_stale", "degraded_stages", "provider_auth_failed"} <= codes


def test_health_orders_mixed_naive_and_timezone_aware_snapshot_times():
    payload = build_data_operations_health(
        now=datetime(2026, 7, 13, 12, 0, 0),
        latest_refresh={
            "finished_at": "2026-07-13T11:30:00",
            "success": 1,
            "degraded_stages": [],
            "failed_stages": [],
            "odds_available": 1,
        },
        upcoming_fights_df=pd.DataFrame([{"fight_url": "a"}]),
        current_odds_df=pd.DataFrame(),
        totals_snapshots_df=pd.DataFrame(
            [
                {"captured_at": "2026-07-13T10:00:00", "fight_url": "a"},
                {"captured_at": "2026-07-13T11:00:00+00:00", "fight_url": "a"},
            ]
        ),
        saved_predictions_df=pd.DataFrame(),
        duration_evaluation=_duration(),
    )

    assert payload["totals_history"]["latest_captured_at"] == (
        "2026-07-13T11:00:00+00:00"
    )
