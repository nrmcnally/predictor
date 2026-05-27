import {
  Badge,
  Group,
  Paper,
  SimpleGrid,
  Text,
  useComputedColorScheme,
} from "@mantine/core";

export default function FighterEloTrendChart({ eloHistory = [] }) {
  const computedColorScheme = useComputedColorScheme("light", {
    getInitialValueInEffect: true,
  });
  const isDark = computedColorScheme === "dark";

  const chartRows = (eloHistory || [])
    .filter(
      (row) =>
        row?.prior_elo !== null &&
        row?.prior_elo !== undefined &&
        Number.isFinite(Number(row.plotted_elo ?? row.prior_elo))
    )
    .slice(-12);

  if (chartRows.length < 2) {
    return <Text c="dimmed">Not enough Elo history to draw a trend yet.</Text>;
  }

  const width = 720;
  const height = 260;
  const padding = { top: 28, right: 30, bottom: 42, left: 54 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const eloValues = chartRows.map((row) => Number(row.plotted_elo ?? row.prior_elo));
  const minElo = Math.min(...eloValues);
  const maxElo = Math.max(...eloValues);
  const range = Math.max(1, maxElo - minElo);
  const paddedMin = minElo - range * 0.15;
  const paddedMax = maxElo + range * 0.15;
  const paddedRange = Math.max(1, paddedMax - paddedMin);

  const points = chartRows.map((row, index) => {
    const x =
      padding.left +
      (chartRows.length === 1 ? chartWidth / 2 : (index / (chartRows.length - 1)) * chartWidth);
    const y = padding.top + ((paddedMax - Number(row.plotted_elo ?? row.prior_elo)) / paddedRange) * chartHeight;

    return {
      ...row,
      x,
      y,
      elo: Number(row.plotted_elo ?? row.prior_elo),
    };
  });

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");

  const firstPoint = points[0];
  const lastPoint = points[points.length - 1];
  const netChange = lastPoint.elo - firstPoint.elo;
  const netChangeLabel = `${netChange >= 0 ? "+" : ""}${netChange.toFixed(0)}`;
  const recentResults = [...chartRows]
    .slice(-6)
    .reverse()
    .map((row) => String(row.result || "?").trim().slice(0, 1).toUpperCase() || "?");

  const yTicks = [paddedMin, (paddedMin + paddedMax) / 2, paddedMax];

  const chartSurface = isDark ? "#101827" : "#fcfcfd";
  const gridStroke = isDark ? "#263244" : "#eaecf0";
  const textFill = isDark ? "#a9b4c6" : "#667085";
  const lineStroke = isDark ? "#7aa2f7" : "#1d4ed8";
  const winFill = isDark ? "#34d399" : "#067647";
  const lossFill = isDark ? "#fb7185" : "#b42318";
  const otherFill = isDark ? "#94a3b8" : "#667085";
  const pointStroke = isDark ? "#0b1220" : "#ffffff";

  return (
    <div className="mantine-elo-trend-chart">
      <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md" mb="md">
        <Paper withBorder radius="lg" p="md" className="mantine-profile-metric">
          <Text size="xs" c="dimmed" fw={850} tt="uppercase" lts="0.06em">
            Current plotted Elo
          </Text>
          <Text fw={950} size="xl" mt={4}>{lastPoint.elo.toFixed(0)}</Text>
        </Paper>

        <Paper withBorder radius="lg" p="md" className="mantine-profile-metric">
          <Text size="xs" c="dimmed" fw={850} tt="uppercase" lts="0.06em">
            Trend over shown fights
          </Text>
          <Text fw={950} size="xl" mt={4} c={netChange >= 0 ? "green" : "red"}>
            {netChangeLabel}
          </Text>
        </Paper>

        <Paper withBorder radius="lg" p="md" className="mantine-profile-metric">
          <Text size="xs" c="dimmed" fw={850} tt="uppercase" lts="0.06em">
            Recent sequence
          </Text>
          <Text fw={950} size="xl" mt={4}>{recentResults.length ? recentResults.join(" - ") : "N/A"}</Text>
        </Paper>
      </SimpleGrid>

      <Paper withBorder radius="xl" p="sm" className="mantine-elo-chart-surface">
        <div style={{ overflowX: "auto" }}>
          <svg
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            aria-label="Fighter Elo trend chart"
            style={{ width: "100%", minWidth: 540, display: "block" }}
          >
            <rect x="0" y="0" width={width} height={height} rx="18" fill={chartSurface} />

            {yTicks.map((tick) => {
              const y = padding.top + ((paddedMax - tick) / paddedRange) * chartHeight;

              return (
                <g key={tick.toFixed(2)}>
                  <line
                    x1={padding.left}
                    x2={width - padding.right}
                    y1={y}
                    y2={y}
                    stroke={gridStroke}
                    strokeWidth="1"
                  />
                  <text
                    x={padding.left - 10}
                    y={y + 4}
                    textAnchor="end"
                    fontSize="12"
                    fill={textFill}
                  >
                    {tick.toFixed(0)}
                  </text>
                </g>
              );
            })}

            <path
              d={linePath}
              fill="none"
              stroke={lineStroke}
              strokeWidth="4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {points.map((point) => {
              const result = String(point.result || "").toLowerCase();
              const fill = result === "win" ? winFill : result === "loss" ? lossFill : otherFill;

              return (
                <g key={`${point.fight_url || point.event_date}-${point.opponent || point.elo}`}>
                  <circle cx={point.x} cy={point.y} r="7" fill={fill} stroke={pointStroke} strokeWidth="3">
                    <title>
                      {`${point.event_date || "Unknown date"}: ${point.result || "Result unknown"} vs ${point.opponent || "Unknown"} — Elo ${point.elo.toFixed(0)}`}
                    </title>
                  </circle>
                </g>
              );
            })}

            <text x={padding.left} y={height - 16} fontSize="12" fill={textFill}>
              {firstPoint.event_date || "First shown fight"}
            </text>

            <text x={width - padding.right} y={height - 16} textAnchor="end" fontSize="12" fill={textFill}>
              {lastPoint.event_date || "Latest shown fight"}
            </text>
          </svg>
        </div>
      </Paper>

      <Group gap="xs" mt="md">
        <Badge color="green" variant="light">Green = win</Badge>
        <Badge color="red" variant="light">Red = loss</Badge>
        <Badge color="blue" variant="light">Line uses post-fight/current Elo</Badge>
      </Group>
    </div>
  );
}
