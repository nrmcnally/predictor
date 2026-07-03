import { act, renderHook, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { useApi } from "./useApi.js";

test("resolves data and clears loading", async () => {
  const { result } = renderHook(() => useApi(() => Promise.resolve([1, 2, 3])));
  expect(result.current.loading).toBe(true);

  await waitFor(() => expect(result.current.loading).toBe(false));
  expect(result.current.data).toEqual([1, 2, 3]);
  expect(result.current.error).toBe("");
});

test("surfaces the error message on rejection", async () => {
  const { result } = renderHook(() =>
    useApi(() => Promise.reject(new Error("boom")))
  );
  await waitFor(() => expect(result.current.loading).toBe(false));
  expect(result.current.error).toBe("boom");
  expect(result.current.data).toBeNull();
});

test("reload() refetches; changed deps refetch", async () => {
  const fetcher = vi.fn(() => Promise.resolve("ok"));
  const { result, rerender } = renderHook(({ id }) => useApi(fetcher, [id]), {
    initialProps: { id: 1 },
  });
  await waitFor(() => expect(result.current.loading).toBe(false));
  expect(fetcher).toHaveBeenCalledTimes(1);

  act(() => result.current.reload());
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));

  rerender({ id: 2 });
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3));
});

test("a stale response never lands after deps change", async () => {
  let resolveFirst;
  const slowThenFast = vi
    .fn()
    .mockImplementationOnce(
      () => new Promise((resolve) => { resolveFirst = resolve; })
    )
    .mockImplementationOnce(() => Promise.resolve("fresh"));

  const { result, rerender } = renderHook(({ id }) => useApi(slowThenFast, [id]), {
    initialProps: { id: 1 },
  });
  rerender({ id: 2 });
  await waitFor(() => expect(result.current.data).toBe("fresh"));

  // The abandoned first request resolves late — it must not overwrite.
  act(() => resolveFirst("stale"));
  await waitFor(() => expect(result.current.data).toBe("fresh"));
});
