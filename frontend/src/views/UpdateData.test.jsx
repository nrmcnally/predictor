import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

vi.mock("../api/client.js", () => ({
  checkHealth: vi.fn().mockResolvedValue({ hosted: false }),
  getUpdateStatus: vi.fn().mockResolvedValue({
    running: false,
    success: true,
    finished_at: "2026-07-13T10:00:00",
    message: "Incremental update completed successfully.",
  }),
  getLatestUpdateReport: vi.fn().mockResolvedValue({ report: null }),
  getDataOperationsHealth: vi.fn().mockResolvedValue({
    status: "attention",
    refresh: { age_hours: 2, success: true },
    odds: {
      refresh_available: false,
      provider_requests_remaining: 20,
      totals_coverage: { covered: 8, total: 56, ratio: 8 / 56, percentage: "14.3%" },
    },
    totals_history: {
      snapshot_rows: 32,
      unique_fights: 8,
      bookmakers: 4,
      lines: [1.5, 2.5, 3.5],
    },
    duration_evaluation: { scored_predictions: 3, pending_predictions: 5 },
    alerts: [
      {
        severity: "warning",
        code: "provider_quota_low",
        message: "Odds provider quota is low.",
      },
    ],
  }),
  startIncrementalUpdate: vi.fn(),
  uploadDataBundle: vi.fn(),
}));

import UpdateData from "./UpdateData.jsx";


test("shows daily refresh, totals coverage, and prospective duration health", async () => {
  render(<UpdateData />);

  expect(
    await screen.findByRole("heading", { name: "Refresh and totals health" })
  ).toBeInTheDocument();
  expect(screen.getAllByText("Needs attention").length).toBeGreaterThan(0);
  expect(screen.getByText("8 / 56")).toBeInTheDocument();
  expect(screen.getByText("3 settled")).toBeInTheDocument();
  expect(screen.getByText("Odds provider quota is low.")).toBeInTheDocument();
});
