import json

import pandas as pd

from app.services.duration_evaluation_service import build_duration_evaluation


def test_evaluation_does_not_treat_decision_probability_as_over_under(tmp_path):
    saved = pd.DataFrame(
        [
            {
                "fight_url": "fight-1",
                "model_distance_percentage": "72.0%",
                "scheduled_rounds": 3,
            }
        ]
    )

    payload = build_duration_evaluation(
        metrics_path=tmp_path / "missing.json",
        saved_predictions_df=saved,
        event_fights_df=pd.DataFrame(),
    )

    assert payload["historical"]["status"] == "not_trained"
    assert payload["prospective"]["status"] == "not_collecting"
    assert payload["prospective"]["saved_predictions"] == 0
    assert "P(Decision) is never substituted" in payload["semantic_contract"]


def test_evaluation_reads_historical_artifact_and_scores_future_result(tmp_path):
    metrics_path = tmp_path / "duration_model_metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "status": "experimental_backtest",
                "model": {
                    "type": "discrete_time_survival",
                    "version": "duration-survival-0.2.0",
                },
                "split": {
                    "strategy": "chronological_80_20_unique_fights",
                    "training_fights": 80,
                    "test_fights": 20,
                },
                "metrics": {"fight_count": 20, "brier_score": 0.22},
                "by_line": [],
                "recent_results": [],
            }
        ),
        encoding="utf-8",
    )
    saved = pd.DataFrame(
        [
            {
                "saved_at": "2026-01-01T12:00:00Z",
                "event_name": "Test Event",
                "event_date": "2026-01-02",
                "fight_url": "fight-1",
                "fighter_1": "One",
                "fighter_2": "Two",
                "scheduled_rounds": 3,
                "duration_line": 2.5,
                "duration_over_probability": 0.6,
                "duration_under_probability": 0.4,
                "duration_model_version": "duration-1",
                "duration_model_type": "discrete_time_survival",
                "rounds_line": 2.5,
            }
        ]
    )
    results = pd.DataFrame(
        [
            {
                "fight_url": "fight-1",
                "event_name": "Test Event",
                "event_date": "2026-01-02",
                "fighter_1": "One",
                "fighter_2": "Two",
                "result_1": "win",
                "result_2": "loss",
                "winner": "One",
                "method": "KO/TKO",
                "round": 3,
                "time": "3:00",
            }
        ]
    )

    payload = build_duration_evaluation(
        metrics_path=metrics_path,
        saved_predictions_df=saved,
        event_fights_df=results,
    )

    assert payload["historical"]["available"] is True
    assert payload["prospective"]["status"] == "ready"
    assert payload["prospective"]["scored_predictions"] == 1
    assert payload["prospective"]["metrics"]["accuracy"] == 1.0
    assert payload["prospective"]["future_card_results"][0]["actual_side"] == "over"
    assert payload["readiness"]["saved_totals_snapshots"] == 1


def test_historical_standard_line_artifact_is_rejected_as_stale(tmp_path):
    metrics_path = tmp_path / "duration_model_metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "model": {"type": "line_aware_classifier"},
                "split": {},
                "metrics": {},
                "by_line": [],
                "recent_results": [],
            }
        ),
        encoding="utf-8",
    )

    payload = build_duration_evaluation(
        metrics_path=metrics_path,
        saved_predictions_df=pd.DataFrame(),
        event_fights_df=pd.DataFrame(),
    )

    assert payload["historical"]["available"] is False
    assert payload["historical"]["status"] == "stale_artifact"
    assert "retired standard-line classifier" in payload["historical"]["message"]


def test_invalid_duration_probabilities_are_counted_but_not_scored(tmp_path):
    saved = pd.DataFrame(
        [
            {
                "fight_url": "fight-1",
                "scheduled_rounds": 3,
                "duration_line": 2.5,
                "duration_over_probability": 0.8,
                "duration_under_probability": 0.8,
            }
        ]
    )

    payload = build_duration_evaluation(
        metrics_path=tmp_path / "missing.json",
        saved_predictions_df=saved,
        event_fights_df=pd.DataFrame(),
    )

    assert payload["prospective"]["saved_predictions"] == 0
    assert payload["prospective"]["invalid_predictions"] == 1
    assert payload["prospective"]["scored_predictions"] == 0
