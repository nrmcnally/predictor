import { useCallback, useEffect, useState } from "react";

/**
 * The one way to load API data in a view. Replaces the hand-rolled
 * useEffect + `active` flag + loading/error triplet that was copy-pasted
 * (and occasionally mis-copied) across ~10 views.
 *
 *   const { data, loading, error, reload } = useApi(() => getFriends(), []);
 *
 * `deps` refetches when inputs change (e.g. [scope, window]); `reload()`
 * refetches manually after a mutation. Stale responses never land: only the
 * latest in-flight request may set state.
 */
export function useApi(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);

  const reload = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    let active = true;
    // Fetch-on-render hook: resetting loading/error synchronously when inputs
    // change is the point — the "external system" here is the API request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError("");
    fetcher()
      .then((result) => {
        if (active) setData(result);
      })
      .catch((requestError) => {
        if (active) setError(requestError?.message || "Request failed.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);

  return { data, loading, error, reload, setData };
}
