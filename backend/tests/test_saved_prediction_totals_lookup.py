import pandas as pd

from app.services import saved_prediction_service as service


def test_saved_odds_lookup_preserves_exact_total_and_prices(monkeypatch):
    monkeypatch.setattr(
        service.future_fight_odds_repository,
        "read_all_df",
        lambda: pd.DataFrame(
            [
                {
                    "fight_url": "http://www.ufcstats.com/fight-details/abc/",
                    "odds_available": True,
                    "rounds_line": 1.5,
                    "over_odds_american": -125,
                    "under_odds_american": 105,
                    "over_market_probability": 0.54,
                    "under_market_probability": 0.46,
                    "over_market_percentage": "54.0%",
                    "under_market_percentage": "46.0%",
                    "totals_bookmakers_matched": 4,
                }
            ]
        ),
    )

    lookup = service.load_future_odds_lookup()
    row = lookup["http://ufcstats.com/fight-details/abc"]

    assert row["rounds_line"] == 1.5
    assert row["over_odds_american"] == -125
    assert row["under_odds_american"] == 105
    assert row["over_market_probability"] == 0.54
    assert row["under_market_probability"] == 0.46
    assert row["totals_bookmakers_matched"] == 4
