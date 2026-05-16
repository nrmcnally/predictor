from __future__ import annotations

import argparse

from app.services.prediction_service import (
    FighterNotFoundError,
    predict_fight_data,
)


def format_edge_value(value, unit: str) -> str:
    if value is None:
        return "unknown"

    if unit:
        return f"{value:+.2f} {unit}"

    return f"{value:+.2f}"


def print_prediction(result: dict) -> None:
    print()
    print("Fight prediction")
    print("=" * 60)
    print(f"Weight class: {result['weight_class']}")
    print(f"{result['fighter_a']}: {result['fighter_a_percentage']}")
    print(f"{result['fighter_b']}: {result['fighter_b_percentage']}")

    print()
    print("Raw model perspective scores:")
    print(
        f"- {result['fighter_a']} direct win score: "
        f"{result['fighter_a_direct_score'] * 100.0:.1f}%"
    )
    print(
        f"- {result['fighter_b']} direct win score: "
        f"{result['fighter_b_direct_score'] * 100.0:.1f}%"
    )

    print()
    print(f"Predicted winner: {result['predicted_winner']}")
    print(f"Model confidence: {result['confidence_percentage']}")
    print(f"Confidence label: {result['confidence_label']}")

    print()
    print("Basic matchup edges:")

    for edge in result["basic_matchup_edges"]:
        value_text = format_edge_value(
            value=edge["difference"],
            unit=edge["unit"],
        )

        print(
            f"- {result['fighter_a']} vs {result['fighter_b']} "
            f"{edge['label']}: {value_text}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--fighter-a",
        required=True,
        help="First fighter name.",
    )

    parser.add_argument(
        "--fighter-b",
        required=True,
        help="Second fighter name.",
    )

    parser.add_argument(
        "--weight-class",
        required=True,
        help='Weight class, like "Lightweight", "Middleweight", or "Heavyweight".',
    )

    args = parser.parse_args()

    try:
        result = predict_fight_data(
            fighter_a=args.fighter_a,
            fighter_b=args.fighter_b,
            weight_class=args.weight_class,
        )

        print_prediction(result)

    except FighterNotFoundError as error:
        print()
        print(error)

    except Exception as error:
        print()
        print(f"Prediction failed: {error}")


if __name__ == "__main__":
    main()