import pandas as pd

from app.models.train_duration_model import (
    build_person_period_dataset,
    hazard_intervals,
    supported_market_lines,
)


def _fight(url, elapsed_seconds, observed_finish):
    return {
        "fight_url": url,
        "event_date_parsed": pd.Timestamp("2025-01-01"),
        "weight_class": "Lightweight",
        "elapsed_seconds": elapsed_seconds,
        "observed_finish": observed_finish,
        "fight_context_scheduled_rounds": 3,
        "fight_context_is_five_round": 0,
        "fight_context_is_main_event": 0,
        "fight_context_card_position_from_top": 4,
        "fight_context_card_position_from_bottom": 8,
        "fight_context_card_size": 11,
    }


def test_internal_hazard_intervals_and_external_market_lines_are_separate():
    assert hazard_intervals(3) == [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    assert supported_market_lines(3) == [0.5, 1.5, 2.5]
    assert supported_market_lines(5) == [0.5, 1.5, 2.5, 3.5, 4.5]


def test_person_period_rows_stop_at_finish_and_censor_decisions():
    fights = pd.DataFrame(
        [
            _fight("finish", elapsed_seconds=450, observed_finish=True),
            _fight("decision", elapsed_seconds=900, observed_finish=False),
        ]
    )

    periods = build_person_period_dataset(fights)
    finish = periods[periods["fight_url"] == "finish"]
    decision = periods[periods["fight_url"] == "decision"]

    assert finish["duration_interval_end_rounds"].tolist() == [0.5, 1.0, 1.5]
    assert finish["target_hazard"].tolist() == [0, 0, 1]
    assert decision["duration_interval_end_rounds"].tolist() == [
        0.5,
        1.0,
        1.5,
        2.0,
        2.5,
        3.0,
    ]
    assert decision["target_hazard"].tolist() == [0, 0, 0, 0, 0, 0]
