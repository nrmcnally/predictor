from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import connection as db_connection  # noqa: E402
from app.repositories import data_refresh_runs_repository as repository  # noqa: E402


def _report():
    return {
        "update_type": "incremental",
        "started_at": "2026-07-13T09:00:00",
        "finished_at": "2026-07-13T09:30:00",
        "duration_seconds": 1800,
        "summary": {
            "success": True,
            "failed_stages": [],
            "degraded_stages": [],
            "completed_events_rows": 800,
            "event_fights_rows": 8700,
            "upcoming_events_rows": 8,
            "upcoming_fights_rows": 56,
            "saved_card_predictions_rows": 56,
            "saved_duration_predictions_rows": 8,
        },
        "stages": [
            {
                "name": "Settle duration predictions",
                "status": "success",
                "details": {"scored_predictions": 3, "pending_predictions": 5},
            },
            {
                "name": "Refresh future fight odds",
                "status": "success",
                "details": {
                    "available": True,
                    "message": "refreshed",
                    "provider_requests_remaining": "496",
                    "matched_fights": 8,
                    "unmatched_fights": 48,
                    "totals_quotes_received": 32,
                    "totals_snapshots_added": 32,
                    "totals_snapshots_total": 32,
                    "totals_fights_matched": 8,
                    "totals_lines_received": [1.5, 2.5, 3.5],
                },
            },
        ],
    }


def test_refresh_heartbeat_is_secret_free_and_idempotent(tmp_path=None):
    root = Path(tmp_path or tempfile.mkdtemp())
    db_connection.set_db_path(root / "app.db")

    report = _report()
    repository.record_report(report)
    repository.record_report(report)

    assert repository.count() == 1
    latest = repository.latest()
    assert latest["success"] == 1
    assert latest["provider_requests_remaining"] == 496
    assert latest["totals_lines"] == [1.5, 2.5, 3.5]
    assert latest["settled_duration_predictions"] == 3
    assert "api_key" not in latest
    assert "password" not in latest
