import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { FightDurationBreakdown, FightDurationSummary } from "./FutureCards.jsx";

const MARKET_TOTAL = {
  odds_available: true,
  odds_bookmaker: "Consensus (no-vig)",
  rounds_line: 2.5,
  over_market_probability: 0.5,
  under_market_probability: 0.5,
  totals_bookmakers_matched: 4,
};

test("keeps a compact market reference visible when the duration model is unavailable", () => {
  render(
    <FightDurationSummary
      fight={{ model_distance_percentage: "61.0%" }}
      odds={{
        ...MARKET_TOTAL,
        over_market_probability: 0.56,
        under_market_probability: 0.44,
      }}
    />
  );

  expect(screen.getByText("Fight duration")).toBeInTheDocument();
  expect(screen.getByText("O/U 2.5")).toBeInTheDocument();
  expect(screen.getByText("Model pending")).toBeInTheDocument();
  expect(screen.getByText("No exact-line pick")).toBeInTheDocument();
  expect(screen.getByText("O 56.0%")).toBeInTheDocument();
  expect(screen.getByText("Market")).toBeInTheDocument();
  expect(screen.getByText("U 44.0%")).toBeInTheDocument();
  expect(screen.queryByText("Decision context")).not.toBeInTheDocument();
});

test("uses the compact infographic for an available FightIQ duration prediction", () => {
  render(
    <FightDurationSummary
      fight={{
        duration_prediction: {
          line: 2.5,
          over_probability: 0.54,
          under_probability: 0.46,
        },
      }}
      odds={MARKET_TOTAL}
    />
  );

  expect(screen.getByText("Over 2.5")).toBeInTheDocument();
  expect(screen.getByText("FightIQ")).toBeInTheDocument();
  expect(screen.getByText("O 54.0%")).toBeInTheDocument();
  expect(screen.getByText("U 46.0%")).toBeInTheDocument();
  expect(screen.getByText("54.0%")).toBeInTheDocument();
});

test("puts full model-versus-market context in the expanded breakdown", () => {
  render(
    <FightDurationBreakdown
      fight={{
        model_distance_percentage: "61.0%",
        duration_prediction: {
          line: 2.5,
          over_probability: 0.54,
          under_probability: 0.46,
        },
      }}
      odds={MARKET_TOTAL}
    />
  );

  expect(screen.getByText("FightIQ O/U prediction")).toBeInTheDocument();
  expect(screen.getByText("Over 2.5")).toBeInTheDocument();
  expect(screen.getByText("Model Over")).toBeInTheDocument();
  expect(screen.getByText("Model Under")).toBeInTheDocument();
  expect(screen.getByText("Market total")).toBeInTheDocument();
  expect(screen.getByText("2.5 rounds")).toBeInTheDocument();
  expect(screen.getByText("+4.0 pts on Over")).toBeInTheDocument();
  expect(screen.getByText("Decision context")).toBeInTheDocument();
  expect(screen.getByText("P(Decision), not O/U")).toBeInTheDocument();
});

test("shows both lines but hides the edge when model and market lines differ", () => {
  render(
    <FightDurationBreakdown
      fight={{
        duration_prediction: {
          line: 4.5,
          over_probability: 0.54,
          under_probability: 0.46,
        },
      }}
      odds={MARKET_TOTAL}
    />
  );

  expect(screen.getByText(/Line mismatch/)).toBeInTheDocument();
  expect(screen.getByText("Over 4.5")).toBeInTheDocument();
  expect(screen.getByText("Model Over")).toBeInTheDocument();
  expect(screen.getByText("2.5 rounds")).toBeInTheDocument();
  expect(screen.queryByText(/pts on Over/)).not.toBeInTheDocument();
});

test("rejects an incomplete duration payload instead of coercing null values", () => {
  render(
    <FightDurationSummary
      fight={{
        duration_prediction: {
          line: null,
          over_probability: null,
          under_probability: null,
        },
      }}
      odds={MARKET_TOTAL}
    />
  );

  expect(screen.getByText("Model pending")).toBeInTheDocument();
  expect(screen.getByText("No exact-line pick")).toBeInTheDocument();
  expect(screen.queryByText("FightIQ")).not.toBeInTheDocument();
});
