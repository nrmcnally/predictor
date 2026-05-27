import { useMemo } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  NumberInput,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import {
  IconChartBar,
  IconFilter,
  IconRefresh,
  IconTrophy,
  IconUsers,
} from "@tabler/icons-react";
import { FighterName } from "./FighterDisplay";

function formatNumber(value) {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  const numberValue = Number(value);

  if (!Number.isFinite(numberValue)) {
    return String(value);
  }

  return numberValue.toLocaleString();
}

function formatStatLabel(value = "") {
  const labels = {
    prior_elo: "Elo",
    prior_peak_elo: "Peak Elo",
    prior_win_rate: "Win rate",
    recent_5_win_rate: "Recent 5 win rate",
    prior_finish_win_rate: "Finish win rate",
    prior_finish_loss_rate: "Finish loss rate",
    prior_fights: "UFC fights",
    prior_wins: "UFC wins",
    prior_losses: "UFC losses",
    avg_sig_str_differential_per_15: "Sig. strike diff / 15",
    avg_sig_str_landed_per_15: "Sig. strikes landed / 15",
    avg_sig_str_absorbed_per_15: "Sig. strikes absorbed / 15",
    avg_sig_str_accuracy: "Sig. strike accuracy",
    avg_sig_str_defense: "Sig. strike defense",
    avg_kd_for: "Knockdowns for",
    avg_kd_against: "Knockdowns against",
    avg_td_landed_per_15: "Takedowns landed / 15",
    avg_td_attempted_per_15: "Takedowns attempted / 15",
    avg_td_accuracy: "Takedown accuracy",
    avg_td_defense: "Takedown defense",
    avg_td_absorbed_per_15: "Takedowns absorbed / 15",
    avg_ctrl_seconds_per_15: "Control seconds / 15",
    avg_ctrl_absorbed_seconds_per_15: "Control absorbed / 15",
    avg_sub_att_per_15: "Sub attempts / 15",
    height_inches: "Height",
    reach_inches: "Reach",
    reach_minus_height_inches: "Reach minus height",
    age_years: "Age",
  };

  return labels[value] ?? value.replaceAll("_", " ");
}

function formatLeaderboardStatValue(key, value) {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  const numberValue = Number(value);

  if (!Number.isFinite(numberValue)) {
    return String(value);
  }

  if (key.includes("rate") || key.includes("accuracy") || key.includes("defense")) {
    return `${(numberValue * 100).toFixed(1)}%`;
  }

  if (key.includes("height") || key.includes("reach")) {
    return `${numberValue.toFixed(1)} in`;
  }

  return numberValue.toFixed(2);
}

function MetricPill({ label, value, icon }) {
  return (
    <Paper withBorder radius="lg" p="md" className="mantine-dashboard-metric">
      <Group gap="xs" align="center" mb={4}>
        {icon}
        <Text size="xs" c="dimmed" fw={850} tt="uppercase" lts="0.06em">
          {label}
        </Text>
      </Group>
      <Text fw={900} size="xl" lh={1.1}>
        {value}
      </Text>
    </Paper>
  );
}

export default function LeaderboardsTab({
  leaderboards,
  leaderboardsLoading = false,
  leaderboardsError = "",
  leaderboardOptions,
  leaderboardScope,
  setLeaderboardScope,
  leaderboardWeightClass,
  setLeaderboardWeightClass,
  leaderboardCategory,
  setLeaderboardCategory,
  leaderboardDirection,
  setLeaderboardDirection,
  leaderboardTop,
  setLeaderboardTop,
  leaderboardMinFights,
  setLeaderboardMinFights,
  leaderboardMaxInactiveDays,
  setLeaderboardMaxInactiveDays,
  loadLeaderboards,
  fighterImageLookup = {},
  openFighterProfile,
}) {
  const leaderboardCategoryPayload = useMemo(() => {
    if (!leaderboards) {
      return null;
    }

    if (leaderboardScope === "overall") {
      return leaderboards.overall?.categories?.[leaderboardCategory] ?? null;
    }

    return (
      leaderboards.weight_classes?.[leaderboardWeightClass]?.categories?.[
        leaderboardCategory
      ] ?? null
    );
  }, [leaderboards, leaderboardScope, leaderboardWeightClass, leaderboardCategory]);

  const displayedLeaderboardRows =
    leaderboardCategoryPayload?.[leaderboardDirection] ?? [];

  const leaderboardCategoryOptions =
    leaderboardOptions?.categories ?? [
      { value: "overall", label: "Overall" },
      { value: "striking", label: "Striking" },
      { value: "grappling", label: "Grappling" },
      { value: "wrestling", label: "Wrestling" },
      { value: "finishing", label: "Finishing" },
      { value: "defense", label: "Defense" },
      { value: "elo", label: "Elo" },
      { value: "experience", label: "Experience" },
      { value: "reach", label: "Reach" },
      { value: "reach_for_size", label: "Reach for Size" },
    ];

  const leaderboardWeightClassOptions = leaderboardOptions?.weight_classes ?? [];
  const selectedCategoryLabel =
    leaderboardCategoryOptions.find((category) => category.value === leaderboardCategory)
      ?.label ?? leaderboardCategory;

  return (
    <Stack gap="lg" className="mantine-leaderboards-page">
      <Card withBorder radius="xl" shadow="sm" p="xl">
        <Group justify="space-between" align="flex-start" gap="lg">
          <div>
            <Text size="xs" c="blue" fw={900} tt="uppercase" lts="0.08em">
              Fighter analysis
            </Text>
            <Title order={2} mt={4}>Leaderboards</Title>
            <Text c="dimmed" size="sm" mt="xs" maw={760} lh={1.55}>
              Rank fighters by category using the current feature dataset. Composite
              categories are for analysis and depend on the feature weights in the backend.
            </Text>
          </div>

          <Button
            radius="lg"
            leftSection={<IconRefresh size={17} />}
            onClick={loadLeaderboards}
            loading={leaderboardsLoading}
          >
            Load leaderboards
          </Button>
        </Group>

        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md" mt="xl">
          <Select
            label="Scope"
            value={leaderboardScope}
            onChange={(value) => setLeaderboardScope(value || "overall")}
            data={[
              { value: "overall", label: "Overall" },
              { value: "weight_class", label: "By weight class" },
            ]}
            radius="lg"
            leftSection={<IconUsers size={16} />}
          />

          <Select
            label="Weight class"
            value={leaderboardWeightClass}
            onChange={(value) => setLeaderboardWeightClass(value || leaderboardWeightClass)}
            data={leaderboardWeightClassOptions}
            disabled={leaderboardScope === "overall"}
            radius="lg"
          />

          <Select
            label="Category"
            value={leaderboardCategory}
            onChange={(value) => setLeaderboardCategory(value || "overall")}
            data={leaderboardCategoryOptions}
            radius="lg"
            leftSection={<IconChartBar size={16} />}
          />

          <Select
            label="Direction"
            value={leaderboardDirection}
            onChange={(value) => setLeaderboardDirection(value || "best")}
            data={[
              { value: "best", label: "Best" },
              { value: "worst", label: "Worst" },
            ]}
            radius="lg"
            leftSection={<IconFilter size={16} />}
          />
        </SimpleGrid>

        <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md" mt="md">
          <NumberInput
            label="Top"
            min={1}
            max={25}
            value={leaderboardTop}
            onChange={(value) => setLeaderboardTop(Number(value) || 5)}
            radius="lg"
          />

          <NumberInput
            label="Minimum fights"
            min={0}
            value={leaderboardMinFights}
            onChange={(value) => setLeaderboardMinFights(Number(value) || 0)}
            radius="lg"
          />

          <NumberInput
            label="Max inactive days"
            min={0}
            value={leaderboardMaxInactiveDays}
            onChange={(value) => setLeaderboardMaxInactiveDays(Number(value) || 0)}
            radius="lg"
          />
        </SimpleGrid>

        {leaderboardsError && (
          <Alert color="red" radius="lg" mt="md">
            {leaderboardsError}
          </Alert>
        )}

        {leaderboards?.metadata && (
          <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md" mt="xl">
            <MetricPill
              label="Fighters after filters"
              value={formatNumber(leaderboards.metadata.fighter_rows_after_filters)}
              icon={<IconUsers size={16} />}
            />
            <MetricPill
              label="Minimum fights"
              value={formatNumber(leaderboards.metadata.min_fights)}
              icon={<IconFilter size={16} />}
            />
            <MetricPill
              label="Activity filter"
              value={leaderboards.metadata.max_inactive_days ?? "Disabled"}
              icon={<IconChartBar size={16} />}
            />
          </SimpleGrid>
        )}
      </Card>

      <Card withBorder radius="xl" shadow="sm" p="xl">
        <Group justify="space-between" align="flex-start" mb="lg">
          <div>
            <Text size="xs" c="blue" fw={900} tt="uppercase" lts="0.08em">
              {leaderboardDirection === "best" ? "Best" : "Worst"} category ranking
            </Text>
            <Title order={2} mt={4}>
              {leaderboardScope === "overall" ? "Overall" : leaderboardWeightClass} • {selectedCategoryLabel}
            </Title>
          </div>

          <Badge size="lg" radius="md" variant="light" leftSection={<IconTrophy size={14} />}>
            {formatNumber(displayedLeaderboardRows.length)} rows
          </Badge>
        </Group>

        {displayedLeaderboardRows.length === 0 ? (
          <Paper withBorder radius="xl" p="xl" ta="center">
            <Title order={3}>No leaderboard rows</Title>
            <Text c="dimmed" mt="xs">
              Try lowering minimum fights, disabling the inactivity filter with 0,
              or choosing another category.
            </Text>
          </Paper>
        ) : (
          <Stack gap="md">
            {displayedLeaderboardRows.map((row) => (
              <Paper
                withBorder
                radius="xl"
                p="md"
                className="mantine-leaderboard-row"
                key={`${row.rank}-${row.fighter}`}
              >
                <Group align="flex-start" wrap="nowrap" gap="md">
                  <Badge
                    size="xl"
                    radius="lg"
                    variant={row.rank <= 3 ? "filled" : "light"}
                    color={row.rank <= 3 ? "blue" : "gray"}
                    className="mantine-leaderboard-rank"
                  >
                    #{row.rank}
                  </Badge>

                  <Stack gap={4} className="mantine-leaderboard-fighter">
                    <Title order={3} lh={1.1}>
                      <FighterName
                        name={row.fighter}
                        imageLookup={fighterImageLookup}
                        size="xl"
                        onClick={openFighterProfile}
                      />
                    </Title>
                    <Text c="dimmed" size="sm">
                      {row.weight_class} • {formatNumber(row.prior_fights)} UFC fights
                    </Text>
                  </Stack>

                  <Paper withBorder radius="lg" p="sm" className="mantine-leaderboard-score">
                    <Text size="xs" c="dimmed" fw={850} tt="uppercase">Score</Text>
                    <Text fw={950} size="xl">{row.score}</Text>
                  </Paper>
                </Group>

                <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="sm" mt="md">
                  {Object.entries(row.supporting_stats ?? {}).map(([key, value]) => (
                    <Paper withBorder radius="lg" p="sm" key={key}>
                      <Text size="xs" c="dimmed" fw={800}>{formatStatLabel(key)}</Text>
                      <Text fw={850}>{formatLeaderboardStatValue(key, value)}</Text>
                    </Paper>
                  ))}
                </SimpleGrid>
              </Paper>
            ))}
          </Stack>
        )}
      </Card>
    </Stack>
  );
}
