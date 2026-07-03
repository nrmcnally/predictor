/**
 * Hash-route parsing (W7), extracted pure so it's unit-testable (W8).
 * Routes look like #/view or #/view/param — the param deep-links into a view
 * (#/fighters/<name>, #/picks/<event_id>, #/friends/<username>).
 */

export function parseRoute(hash, validViews, fallbackView) {
  const raw = String(hash || "").replace(/^#\/?/, "");
  const slash = raw.indexOf("/");
  const name = slash === -1 ? raw : raw.slice(0, slash);
  let param = "";
  if (slash !== -1) {
    try {
      param = decodeURIComponent(raw.slice(slash + 1));
    } catch {
      // Malformed percent-encoding: use it verbatim rather than crash.
      param = raw.slice(slash + 1);
    }
  }
  return validViews.has(name)
    ? { view: name, param }
    : { view: fallbackView, param: "" };
}

export function routeHash(view, param = "") {
  return param ? `#/${view}/${encodeURIComponent(param)}` : `#/${view}`;
}
