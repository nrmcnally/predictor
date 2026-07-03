import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { ErrorBoundary } from "./ErrorBoundary.jsx";

function Bomb() {
  throw new Error("kaboom");
}

test("renders children when nothing throws", () => {
  render(
    <ErrorBoundary>
      <p>all good</p>
    </ErrorBoundary>
  );
  expect(screen.getByText("all good")).toBeInTheDocument();
});

test("a throwing child shows the fallback instead of white-screening", () => {
  // React logs caught render errors; keep the test output clean.
  const spy = vi.spyOn(console, "error").mockImplementation(() => {});
  render(
    <ErrorBoundary>
      <Bomb />
    </ErrorBoundary>
  );
  expect(screen.getByText("This corner hit the canvas.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument();
  spy.mockRestore();
});
