import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { useSlowHint } from "./useSlowHint.js";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

test("stays quiet before the delay, fires after it", () => {
  const { result, rerender } = renderHook(({ active }) => useSlowHint(active, 1000), {
    initialProps: { active: false },
  });
  expect(result.current).toBe(false);

  rerender({ active: true });
  act(() => vi.advanceTimersByTime(999));
  expect(result.current).toBe(false);

  act(() => vi.advanceTimersByTime(1));
  expect(result.current).toBe(true);
});

test("resets when the request finishes", () => {
  const { result, rerender } = renderHook(({ active }) => useSlowHint(active, 500), {
    initialProps: { active: true },
  });
  act(() => vi.advanceTimersByTime(500));
  expect(result.current).toBe(true);

  rerender({ active: false });
  expect(result.current).toBe(false);

  // A new request starts the clock over.
  rerender({ active: true });
  act(() => vi.advanceTimersByTime(499));
  expect(result.current).toBe(false);
});
