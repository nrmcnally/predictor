import { expect, test } from "vitest";
import { marketOutlierState } from "./marketOutlier.js";

test("model beating the market flags green, losing to it flags red", () => {
  // Disagreement fights: exactly one side is right.
  expect(
    marketOutlierState({ prediction_correct: true, market_correct: false })
  ).toBe("market-beat");
  expect(
    marketOutlierState({ prediction_correct: false, market_correct: true })
  ).toBe("market-lost");
  // SQLite-style 1/0 flags behave the same.
  expect(marketOutlierState({ prediction_correct: 1, market_correct: 0 })).toBe(
    "market-beat"
  );
});

test("agreement or unscored fights get no highlight", () => {
  // Model and market picked the same fighter - both right or both wrong.
  expect(
    marketOutlierState({ prediction_correct: true, market_correct: true })
  ).toBe("");
  expect(
    marketOutlierState({ prediction_correct: false, market_correct: false })
  ).toBe("");
  // No result yet / no odds: nothing to grade.
  expect(
    marketOutlierState({ prediction_correct: null, market_correct: true })
  ).toBe("");
  expect(
    marketOutlierState({ prediction_correct: true, market_correct: undefined })
  ).toBe("");
});
