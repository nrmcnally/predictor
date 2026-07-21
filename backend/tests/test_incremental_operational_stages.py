from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline import update_incremental_data as pipeline  # noqa: E402


def test_odds_failure_is_visible_without_erasing_last_good_data(monkeypatch):
    def fail():
        raise RuntimeError('Odds API request failed: 401 {"error_code":"INVALID_KEY"}')

    monkeypatch.setattr(pipeline, "refresh_future_fight_odds", fail)
    result = pipeline.refresh_future_fight_odds_stage()

    assert result["available"] is False
    assert result["error_code"] == "provider_auth_failed"
    assert result["validation_warnings"]
    assert "INVALID_KEY" not in result["message"]


def test_duration_settlement_runs_after_results_before_future_snapshots():
    names = [name for name, _ in pipeline.INCREMENTAL_STAGES]
    assert names.index("Update completed fight list incrementally") < names.index(
        "Settle duration predictions"
    )
    assert names.index("Settle duration predictions") < names.index(
        "Save future-card predictions"
    )
