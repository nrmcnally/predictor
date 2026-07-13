import math

import pandas as pd

from app.features.duration_features import build_prediction_duration_features


def test_duration_pair_features_are_orientation_invariant():
    fighter_a = pd.Series(
        {
            "prior_fights": 12,
            "avg_fight_duration_seconds": 640,
            "durability_risk_score": 0.2,
        }
    )
    fighter_b = pd.Series(
        {
            "prior_fights": 8,
            "avg_fight_duration_seconds": 420,
            "durability_risk_score": 0.7,
        }
    )
    context = {
        "fight_context_scheduled_rounds": 3,
        "fight_context_is_five_round": 0,
        "fight_context_is_main_event": 0,
    }

    direct = build_prediction_duration_features(
        fighter_a,
        fighter_b,
        weight_class="Lightweight",
        fight_context=context,
    )
    swapped = build_prediction_duration_features(
        fighter_b,
        fighter_a,
        weight_class="Lightweight",
        fight_context=context,
    )

    assert direct.keys() == swapped.keys()
    for key in direct:
        left = direct[key]
        right = swapped[key]
        if isinstance(left, float) and math.isnan(left):
            assert isinstance(right, float) and math.isnan(right)
        else:
            assert left == right
