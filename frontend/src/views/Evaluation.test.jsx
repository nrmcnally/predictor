import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { DurationEvaluationPanel } from "./Evaluation.jsx";


const BASE_PAYLOAD = {
  semantic_contract:
    "A market-independent survival curve is queried at the exact line; P(Decision) is never substituted.",
  readiness: {
    historical_backtest_available: false,
    future_duration_snapshots: 0,
    settled_future_duration_predictions: 0,
    saved_totals_snapshots: 0,
  },
  historical: {
    available: false,
    status: "not_trained",
    message: "No exact-line duration backtest artifact is installed.",
  },
  prospective: {
    available: false,
    status: "not_collecting",
    message: "No frozen exact-line duration predictions have been saved yet.",
    saved_predictions: 0,
    scored_predictions: 0,
    pending_predictions: 0,
    invalid_predictions: 0,
    excluded_results: 0,
    future_card_results: [],
  },
};


test("shows honest readiness states without treating decision probability as over under", () => {
  render(
    <DurationEvaluationPanel
      payload={BASE_PAYLOAD}
      loading={false}
      error=""
      onRefresh={vi.fn()}
    />
  );

  expect(screen.getByText(/P\(Decision\) is never substituted/)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Chronological 80/20 evaluation" })).toBeInTheDocument();
  expect(screen.getByText("No exact-line duration backtest artifact is installed.")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Frozen prospective evaluation" })).toBeInTheDocument();
  expect(screen.getByText("No frozen exact-line duration predictions have been saved yet.")).toBeInTheDocument();
  expect(screen.queryByText("Model distance")).not.toBeInTheDocument();
});


test("renders historical holdout metrics and settled future-card results separately", () => {
  render(
    <DurationEvaluationPanel
      payload={{
        ...BASE_PAYLOAD,
        readiness: {
          historical_backtest_available: true,
          future_duration_snapshots: 1,
          settled_future_duration_predictions: 1,
          saved_totals_snapshots: 1,
        },
        historical: {
          available: true,
          status: "experimental_backtest",
          model: {
            name: "Discrete-time half-round survival baseline",
            type: "discrete_time_survival",
            promotion_status: "experimental",
          },
          split: {
            training_fights: 80,
            test_fights: 20,
            training_fraction: 0.8,
            test_fraction: 0.2,
            test_date_min: "2024-01-01",
            test_date_max: "2026-01-01",
          },
          metrics: {
            fight_count: 20,
            unique_fights: 10,
            accuracy: 0.65,
            brier_score: 0.22,
            log_loss: 0.63,
            roc_auc: 0.68,
            over_rate: 0.55,
          },
          base_rate_metrics: {
            fight_count: 20,
            accuracy: 0.55,
            brier_score: 0.25,
            log_loss: 0.69,
            roc_auc: 0.5,
          },
          by_line: [
            { line: 2.5, fight_count: 20, accuracy: 0.65, brier_score: 0.22, log_loss: 0.63, roc_auc: 0.68 },
          ],
          recent_results: [],
          survival_validation: { monotonicity_violations: 0 },
        },
        prospective: {
          available: true,
          status: "ready",
          saved_predictions: 1,
          scored_predictions: 1,
          pending_predictions: 0,
          invalid_predictions: 0,
          excluded_results: 0,
          metrics: {
            fight_count: 1,
            accuracy: 1,
            accuracy_ci95_lower: 0.21,
            accuracy_ci95_upper: 1,
            brier_score: 0.16,
            log_loss: 0.51,
            roc_auc: null,
            actual_over_rate: 1,
            predicted_over_rate: 1,
            majority_baseline_accuracy: 1,
            accuracy_above_majority: 0,
            evidence: {
              level: "very_early",
              label: "Very early",
              message: "Too few frozen future predictions for a stable performance claim.",
            },
          },
          by_line: [],
          future_card_results: [
            {
              fight_url: "fight-1",
              event_name: "Test Event",
              event_date: "2026-01-01",
              fighter_1: "One",
              fighter_2: "Two",
              line: 2.5,
              predicted_side: "over",
              predicted_probability: 0.6,
              actual_side: "over",
              correct: true,
            },
          ],
        },
      }}
      loading={false}
      error=""
      onRefresh={vi.fn()}
    />
  );

  expect(screen.getByText("Discrete-time half-round survival baseline")).toBeInTheDocument();
  expect(screen.getByText("Per-line training base rate")).toBeInTheDocument();
  expect(screen.getByText(/observed monotonicity violations: 0/)).toBeInTheDocument();
  expect(screen.getAllByText("O/U 2.5").length).toBeGreaterThan(0);
  expect(screen.getByText("One vs Two")).toBeInTheDocument();
  expect(screen.getByText("Correct")).toBeInTheDocument();
  expect(screen.getByText("Very early")).toBeInTheDocument();
  expect(screen.getByText(/currently matches the always-Over baseline/)).toBeInTheDocument();
});
