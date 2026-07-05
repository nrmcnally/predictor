"""
Tests for the data-freshness summary: the latest completed event we hold, plus
last_refreshed_at (max saved_at from prediction snapshots) — the signal that an
update actually ran, since the latest-event date never moves between fight nights.

Runs under pytest, or standalone:  python tests/test_data_quality.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from app.services.data_quality_service import summarize_data_freshness  # noqa: E402


def test_freshness_reports_latest_event_and_refresh_time():
    events = pd.DataFrame(
        [
            {"event_name": "UFC Old", "event_date": "January 1, 2026"},
            {"event_name": "UFC Newest", "event_date": "June 27, 2026"},
        ]
    )
    saved = pd.DataFrame(
        [
            {"saved_at": "2026-07-01T08:00:00"},
            {"saved_at": "2026-07-04T10:02:45"},  # the most recent pipeline run
        ]
    )

    out = summarize_data_freshness(events, saved)

    assert out["latest_event_date"] == "2026-06-27"
    assert out["latest_event_name"] == "UFC Newest"
    assert out["last_refreshed_at"] == "2026-07-04T10:02:45"
    assert isinstance(out["days_since_latest_event"], int)


def test_freshness_survives_missing_or_bad_inputs():
    # Nothing at all.
    out = summarize_data_freshness(pd.DataFrame(), None)
    assert out["latest_event_date"] is None
    assert out["last_refreshed_at"] is None

    # Unparseable saved_at values are ignored, not crashed on.
    bad = pd.DataFrame([{"saved_at": "not-a-date"}])
    assert summarize_data_freshness(pd.DataFrame(), bad)["last_refreshed_at"] is None

    # Refresh time still reported even when no events exist yet.
    saved = pd.DataFrame([{"saved_at": "2026-07-04T10:02:45"}])
    out = summarize_data_freshness(pd.DataFrame(), saved)
    assert out["last_refreshed_at"] == "2026-07-04T10:02:45"


if __name__ == "__main__":
    test_freshness_reports_latest_event_and_refresh_time()
    test_freshness_survives_missing_or_bad_inputs()
    print("OK")
