from app.services import future_card_service as service


def test_future_card_queries_duration_curve_at_current_total(monkeypatch):
    card = {
        "event_id": "event-1",
        "event_name": "Test Event",
        "event_date": "2026-01-01",
        "event_location": "Test",
        "event_url": "event-url",
        "fights": [
            {
                "fight_id": "fight-1",
                "fight_url": "http://www.ufcstats.com/fight-details/fight-1/",
                "fighter_1": "One",
                "fighter_2": "Two",
                "weight_class": "Lightweight",
                "fight_context": {"fight_context_scheduled_rounds": 3},
            }
        ],
    }
    captured = {}

    monkeypatch.setattr(service, "get_future_card", lambda _event_id: card)
    monkeypatch.setattr(service, "predict_fight_data", lambda **_kwargs: {"predicted_winner": "One"})
    monkeypatch.setattr(service, "_model_distance_probability", lambda *_args: 0.4)
    monkeypatch.setattr(
        service,
        "load_future_totals_line_lookup",
        lambda: {"http://ufcstats.com/fight-details/fight-1": 1.5},
    )

    def fake_duration(**kwargs):
        captured.update(kwargs)
        return {
            "available": True,
            "line": kwargs["market_line"],
            "over_probability": 0.6,
            "under_probability": 0.4,
            "curve": [],
        }

    monkeypatch.setattr(service, "predict_duration_data", fake_duration)

    result = service.get_future_card_predictions("event-1")

    assert captured["market_line"] == 1.5
    assert captured["fight_context"]["fight_context_scheduled_rounds"] == 3
    assert result["fights"][0]["duration_prediction"]["line"] == 1.5
