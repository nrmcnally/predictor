import math

import numpy as np
import pandas as pd

from app.features.duration_features import (
    duration_categorical_feature_names,
    duration_numeric_feature_names,
)
from app.services import duration_prediction_service as service


class FakeHazardPipeline:
    def __init__(self, hazard=0.1):
        self.hazard = hazard
        self.frames = []

    def predict_proba(self, frame):
        self.frames.append(frame.copy())
        hazards = np.full(len(frame), self.hazard, dtype=float)
        return np.column_stack([1.0 - hazards, hazards])


def _artifact(pipeline):
    return {
        "artifact_type": "fightiq_duration_survival",
        "model_type": "discrete_time_survival",
        "pipeline": pipeline,
        "numeric_features": duration_numeric_feature_names(),
        "categorical_features": duration_categorical_feature_names(),
        "model_version": "duration-survival-test",
        "feature_schema_version": "duration-test-features",
        "trained_at": "2026-01-01T00:00:00Z",
        "interval_rounds": 0.5,
        "supported_scheduled_rounds": [3, 5],
        "market_inputs_used": False,
        "market_line_role": "query_only",
        "promotion_status": "experimental",
    }


def _patch_fighters(monkeypatch):
    rows = {
        "One": pd.Series({"fighter": "One", "prior_fights": 10, "avg_fight_duration_seconds": 600}),
        "Two": pd.Series({"fighter": "Two", "prior_fights": 5, "avg_fight_duration_seconds": 450}),
    }
    monkeypatch.setattr(service, "load_current_features", lambda: pd.DataFrame())
    monkeypatch.setattr(service, "get_fighter_row", lambda _frame, name: rows[name])
    monkeypatch.setattr(service, "apply_prediction_weight_class_context", lambda row, _weight: row)


def test_survival_curve_is_monotonic_by_construction():
    curve = service.survival_curve_from_hazards(
        [0.5, 1.0, 1.5, 2.0],
        [0.1, 0.2, 0.3, 0.4],
    )

    values = list(curve.values())
    assert all(current <= previous for previous, current in zip(values, values[1:]))
    assert math.isclose(curve[1.5], 0.9 * 0.8 * 0.7)


def test_market_line_queries_same_independent_curve(monkeypatch):
    pipeline = FakeHazardPipeline(0.1)
    monkeypatch.setattr(service, "load_duration_artifact", lambda: _artifact(pipeline))
    _patch_fighters(monkeypatch)
    context = {"fight_context_scheduled_rounds": 3}

    at_one_and_half = service.predict_duration_data(
        fighter_a="One",
        fighter_b="Two",
        weight_class="Lightweight",
        fight_context=context,
        market_line=1.5,
    )
    at_two_and_half = service.predict_duration_data(
        fighter_a="One",
        fighter_b="Two",
        weight_class="Lightweight",
        fight_context=context,
        market_line=2.5,
    )

    assert at_one_and_half["available"] is True
    assert at_two_and_half["available"] is True
    assert math.isclose(at_one_and_half["over_probability"], 0.9 ** 3)
    assert math.isclose(at_two_and_half["over_probability"], 0.9 ** 5)
    assert [row["line"] for row in at_one_and_half["curve"]] == [0.5, 1.5, 2.5]
    assert at_one_and_half["market_inputs_used"] is False
    assert at_one_and_half["market_line_role"] == "query_only"
    pd.testing.assert_frame_equal(pipeline.frames[0], pipeline.frames[1])


def test_curve_is_available_without_a_market_line(monkeypatch):
    pipeline = FakeHazardPipeline(0.05)
    monkeypatch.setattr(service, "load_duration_artifact", lambda: _artifact(pipeline))
    _patch_fighters(monkeypatch)

    payload = service.predict_duration_data(
        fighter_a="One",
        fighter_b="Two",
        weight_class="Lightweight",
        fight_context={"fight_context_scheduled_rounds": 5},
    )

    assert payload["available"] is False
    assert payload["status"] == "curve_only"
    assert [row["line"] for row in payload["curve"]] == [0.5, 1.5, 2.5, 3.5, 4.5]
    assert payload["line"] is None
