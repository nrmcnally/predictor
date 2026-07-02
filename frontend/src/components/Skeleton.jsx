/**
 * Shimmering placeholder rows shown while a list loads — the layout appears
 * instantly instead of a spinner-flash followed by content popping in (W6).
 */
export function SkeletonRows({ rows = 4, height = 72 }) {
  return (
    <div className="skeleton-list" aria-hidden="true">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton-row" style={{ height }} />
      ))}
    </div>
  );
}
