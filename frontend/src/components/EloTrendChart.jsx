import { StatTile } from "./ui.jsx";

export default function EloTrendChart({ eloHistory = [] }) {
  const rows = (eloHistory || [])
    .filter(
      (row) =>
        row?.prior_elo !== null &&
        row?.prior_elo !== undefined &&
        Number.isFinite(Number(row.plotted_elo ?? row.prior_elo))
    )
    .slice(-12);

  if (rows.length < 2) {
    return <p className="dim-note">Not enough Elo history to draw a trend yet.</p>;
  }

  const width = 760;
  const height = 250;
  const padding = { top: 24, right: 26, bottom: 38, left: 56 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const values = rows.map((row) => Number(row.plotted_elo ?? row.prior_elo));
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = Math.max(1, maxValue - minValue);
  const paddedMin = minValue - range * 0.18;
  const paddedMax = maxValue + range * 0.18;
  const paddedRange = Math.max(1, paddedMax - paddedMin);

  const points = rows.map((row, index) => ({
    ...row,
    elo: Number(row.plotted_elo ?? row.prior_elo),
    x: padding.left + (index / (rows.length - 1)) * chartWidth,
    y:
      padding.top +
      ((paddedMax - Number(row.plotted_elo ?? row.prior_elo)) / paddedRange) * chartHeight,
  }));

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");

  const areaPath = `${linePath} L ${points[points.length - 1].x.toFixed(1)} ${
    padding.top + chartHeight
  } L ${points[0].x.toFixed(1)} ${padding.top + chartHeight} Z`;

  const first = points[0];
  const last = points[points.length - 1];
  const netChange = last.elo - first.elo;
  const sequence = [...rows]
    .slice(-6)
    .reverse()
    .map((row) => String(row.result || "?").trim().slice(0, 1).toUpperCase() || "?")
    .join(" · ");

  const ticks = [paddedMin, (paddedMin + paddedMax) / 2, paddedMax];

  return (
    <div className="elo-chart">
      <div className="tile-row three">
        <StatTile label="Current Elo" value={last.elo.toFixed(0)} />
        <StatTile
          label="Trend (shown fights)"
          value={`${netChange >= 0 ? "+" : ""}${netChange.toFixed(0)}`}
          tone={netChange >= 0 ? "win" : "loss"}
        />
        <StatTile label="Recent sequence" value={sequence || "N/A"} />
      </div>

      <div className="chart-surface">
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Fighter Elo trend chart">
          <defs>
            <linearGradient id="elo-area" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent-gold)" stopOpacity="0.32" />
              <stop offset="100%" stopColor="var(--accent-gold)" stopOpacity="0" />
            </linearGradient>
          </defs>

          {ticks.map((tick) => {
            const y = padding.top + ((paddedMax - tick) / paddedRange) * chartHeight;

            return (
              <g key={tick.toFixed(2)}>
                <line
                  x1={padding.left}
                  x2={width - padding.right}
                  y1={y}
                  y2={y}
                  className="chart-grid"
                />
                <text x={padding.left - 10} y={y + 4} textAnchor="end" className="chart-text">
                  {tick.toFixed(0)}
                </text>
              </g>
            );
          })}

          <path d={areaPath} fill="url(#elo-area)" />
          <path d={linePath} fill="none" className="chart-line" />

          {points.map((point) => {
            const result = String(point.result || "").toLowerCase();
            const dotClass =
              result === "win" ? "dot-win" : result === "loss" ? "dot-loss" : "dot-other";

            return (
              <circle
                key={`${point.fight_url || point.event_date}-${point.elo}`}
                cx={point.x}
                cy={point.y}
                r="5.5"
                className={`chart-dot ${dotClass}`}
              >
                <title>
                  {`${point.event_date || "Unknown date"}: ${point.result || "?"} vs ${
                    point.opponent || "Unknown"
                  } — Elo ${point.elo.toFixed(0)}`}
                </title>
              </circle>
            );
          })}

          <text x={padding.left} y={height - 12} className="chart-text">
            {first.event_date || ""}
          </text>
          <text x={width - padding.right} y={height - 12} textAnchor="end" className="chart-text">
            {last.event_date || ""}
          </text>
        </svg>
      </div>

      <div className="chart-legend">
        <span className="legend-item win">Win</span>
        <span className="legend-item loss">Loss</span>
        <span className="legend-item other">Other / NC</span>
      </div>
    </div>
  );
}
