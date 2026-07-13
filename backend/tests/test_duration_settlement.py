from app.services.duration_settlement import (
    parse_round_time,
    resolve_fight_duration,
    settle_duration_result,
)


def _result(**overrides):
    row = {
        "result_1": "win",
        "result_2": "loss",
        "winner": "Fighter One",
        "method": "KO/TKO",
        "round": 3,
        "time": "3:00",
    }
    row.update(overrides)
    return row


def test_parse_round_time_rejects_invalid_clock_values():
    assert parse_round_time("4:37") == 277
    assert parse_round_time("5:00") == 300
    assert parse_round_time("5:01") is None
    assert parse_round_time("bad") is None


def test_late_third_round_finish_settles_over_two_and_a_half():
    settled = settle_duration_result(_result(), line=2.5, scheduled_rounds=3)

    assert settled["status"] == "settled"
    assert settled["actual_side"] == "over"
    assert settled["target_over"] == 1


def test_decision_uses_full_scheduled_duration():
    settled = settle_duration_result(
        _result(method="U-DEC", round=3, time="5:00"),
        line=2.5,
        scheduled_rounds=3,
    )

    assert settled["status"] == "settled"
    assert settled["actual_side"] == "over"
    assert settled["elapsed_seconds"] == 900


def test_exact_boundary_is_not_guessed():
    settled = settle_duration_result(
        _result(round=3, time="2:30"),
        line=2.5,
        scheduled_rounds=3,
    )

    assert settled["status"] == "push"
    assert settled["reason"] == "exact_boundary"


def test_exact_boundary_duration_remains_available_for_survival_training():
    duration = resolve_fight_duration(
        _result(round=3, time="2:30"),
        scheduled_rounds=3,
    )

    assert duration["status"] == "resolved"
    assert duration["elapsed_seconds"] == 750
    assert duration["observed_finish"] is True


def test_ambiguous_and_unsupported_results_are_excluded():
    no_contest = settle_duration_result(
        _result(result_1="nc", result_2="nc", winner="", method="NC"),
        line=2.5,
        scheduled_rounds=3,
    )
    unsupported_rounds = settle_duration_result(
        _result(),
        line=2.5,
        scheduled_rounds=1,
    )

    assert no_contest == {"status": "excluded", "reason": "unsettled_result"}
    assert unsupported_rounds == {
        "status": "excluded",
        "reason": "unsupported_scheduled_rounds",
    }
