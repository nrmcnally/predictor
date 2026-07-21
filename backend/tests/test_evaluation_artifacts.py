from __future__ import annotations

import json

import pandas as pd

from app.models.train_calibrated_models import fit_production_model
from app.services import model_evaluation_service, walk_forward_evaluation_service


def test_winner_evaluation_prefers_portable_artifact(monkeypatch, tmp_path):
    artifact = tmp_path / "winner_model_evaluation.json"
    artifact.write_text(
        json.dumps(
            {
                "available": True,
                "overall": {"fight_count": 2},
                "recent_predictions": [{"id": 1}, {"id": 2}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(model_evaluation_service, "EVALUATION_ARTIFACT_PATH", artifact)
    monkeypatch.setattr(
        model_evaluation_service,
        "TRAINING_MATCHUPS_CSV",
        tmp_path / "missing-training.csv",
    )

    result = model_evaluation_service.get_model_evaluation(recent_prediction_limit=1)

    assert result["available"] is True
    assert result["overall"]["fight_count"] == 2
    assert result["recent_predictions"] == [{"id": 1}]


def test_walk_forward_prefers_portable_artifact(monkeypatch, tmp_path):
    artifact = tmp_path / "walk_forward_evaluation.json"
    artifact.write_text(
        json.dumps({"available": True, "folds": [{"test_year": 2026}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        walk_forward_evaluation_service,
        "WALK_FORWARD_ARTIFACT_PATH",
        artifact,
    )
    monkeypatch.setattr(
        walk_forward_evaluation_service,
        "TRAINING_MATCHUPS_CSV",
        tmp_path / "missing-training.csv",
    )

    result = walk_forward_evaluation_service.get_walk_forward_evaluation()

    assert result["folds"][0]["test_year"] == 2026


def test_production_refit_uses_all_rows_for_uncalibrated_recipe():
    frame = pd.DataFrame(
        {
            "fight_url": [f"fight-{index // 2}" for index in range(20)],
            "event_date_parsed": pd.date_range("2025-01-01", periods=20),
            "diff_test": [-1.0, 1.0] * 10,
            "weight_class": ["Lightweight"] * 20,
            "target": [0, 1] * 10,
        }
    )

    model, details = fit_production_model(
        best_model_name="logistic_regression",
        full_df=frame,
        numeric_features=["diff_test"],
        categorical_features=["weight_class"],
    )

    probabilities = model.predict_proba(frame[["diff_test", "weight_class"]])[:, 1]
    assert len(probabilities) == len(frame)
    assert details["role"] == "production_full_history_refit"
    assert details["eligible_rows"] == len(frame)
    assert details["base_fit_rows"] == len(frame)
    assert details["uses_holdout_for_metric_reporting"] is False


def test_wilson_interval_is_wide_for_tiny_samples():
    lower, upper = model_evaluation_service.wilson_interval(6, 7)
    assert lower is not None and upper is not None
    assert lower < 0.5
    assert upper > 0.95
