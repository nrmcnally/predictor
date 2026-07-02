import { useEffect, useState } from "react";

/**
 * True once `active` has been true for `delay` ms — used to explain slow
 * requests (the Fly machine auto-sleeps when idle; the first request after a
 * quiet spell takes a few seconds and looked like the app was broken).
 */
export function useSlowHint(active, delay = 2500) {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (!active) {
      // Timer-sync hook: clearing the hint when the request ends is the point.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSlow(false);
      return undefined;
    }
    const timer = setTimeout(() => setSlow(true), delay);
    return () => clearTimeout(timer);
  }, [active, delay]);

  return slow;
}
