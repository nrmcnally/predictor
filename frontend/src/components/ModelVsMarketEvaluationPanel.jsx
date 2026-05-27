import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import {
  IconChartBar,
  IconRefresh,
  IconScale,
  IconTrendingUp,
} from "@tabler/icons-react";

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

function formatEvaluationPercentage(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "N/A";
  }

  return `${(Number(value) * 100).toFixed(1)}%`;
}

function MetricCard({ label, value, icon }) {
  return (
    <Paper withBorder radius="lg" p="md" className="mantine-evaluation-metric">
      <Group gap="xs" mb={4}>
        {icon}
        <Text size="xs" c="dimmed" fw={850} tt="uppercase" lts="0.06em">
          {label}
        </Text>
      </Group>
      <Text fw={950} size="xl" lh={1.1}>{value}</Text>
    </Paper>
  );
}

function FightRow({ fight }) {
  if (!fight) {
    return null;
  }

  const modelColor = fight.model_correct === true ? "green" : fight.model_correct === false ? "red" : "gray";
  const marketColor = fight.market_correct === true ? "green" : fight.market_correct === false ? "red" : "gray";

  return (
    <Paper withBorder radius="lg" p="md" className="mantine-market-fight-row">
      <Group justify="space-between" align="flex-start" gap="md">
        <div>
          <Text fw={850}>{fight.fighter_1 || "Fighter 1"} vs {fight.fighter_2 || "Fighter 2"}</Text>
          <Text c="dimmed" size="sm">
            {fight.event_date || "Unknown date"} • {fight.event_name || "Unknown event"}
          </Text>
        </div>

        <Group gap="xs">
          <Badge color={modelColor} variant="light">Model {fight.model_correct === true ? "correct" : fight.model_correct === false ? "wrong" : "N/A"}</Badge>
          <Badge color={marketColor} variant="light">Market {fight.market_correct === true ? "correct" : fight.market_correct === false ? "wrong" : "N/A"}</Badge>
        </Group>
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="sm" mt="md">
        <Paper withBorder radius="md" p="sm">
          <Text size="xs" c="dimmed" fw={800}>Model pick</Text>
          <Text fw={850}>{fight.predicted_winner || "N/A"}</Text>
        </Paper>
        <Paper withBorder radius="md" p="sm">
          <Text size="xs" c="dimmed" fw={800}>Market favorite</Text>
          <Text fw={850}>{fight.market_favorite || "N/A"}</Text>
        </Paper>
        <Paper withBorder radius="md" p="sm">
          <Text size="xs" c="dimmed" fw={800}>Actual winner</Text>
          <Text fw={850}>{fight.actual_winner || "N/A"}</Text>
        </Paper>
      </SimpleGrid>
    </Paper>
  );
}

function FightBucket({ title, description, fights = [] }) {
  return (
    <Card withBorder radius="xl" shadow="sm" p="xl">
      <Title order={3}>{title}</Title>
      {description && <Text c="dimmed" size="sm" mt={4}>{description}</Text>}

      {fights.length === 0 ? (
        <Text c="dimmed" mt="md">No fights in this bucket yet.</Text>
      ) : (
        <Stack gap="sm" mt="md">
          {fights.map((fight, index) => (
            <FightRow key={`${title}-${fight.event_id}-${fight.fight_url}-${index}`} fight={fight} />
          ))}
        </Stack>
      )}
    </Card>
  );
}

export default function ModelVsMarketEvaluationPanel({
  evaluation,
  loading = false,
  error = "",
  onReload,
}) {
  if (loading) {
    return (
      <Card withBorder radius="xl" shadow="sm" p="xl">
        <Text size="xs" c="blue" fw={900} tt="uppercase" lts="0.08em">Model vs market</Text>
        <Title order={2} mt={4}>Loading model-vs-market evaluation...</Title>
      </Card>
    );
  }

  if (error) {
    return <Alert color="red" radius="lg">{error}</Alert>;
  }

  if (!evaluation) {
    return null;
  }

  if (!evaluation.available) {
    return (
      <Card withBorder radius="xl" shadow="sm" p="xl">
        <Group justify="space-between" align="flex-start">
          <div>
            <Text size="xs" c="blue" fw={900} tt="uppercase" lts="0.08em">Model vs market</Text>
            <Title order={2} mt={4}>Market comparison unavailable</Title>
            <Text c="dimmed" mt="xs">
              {evaluation.message || "No saved fights have both actual results and saved market odds yet."}
            </Text>
          </div>
          {onReload && <Button variant="light" radius="lg" leftSection={<IconRefresh size={16} />} onClick={onReload}>Reload</Button>}
        </Group>

        {evaluation.summary?.saved_rows !== undefined && (
          <Badge mt="md" size="lg" variant="light">Saved prediction rows: {formatNumber(evaluation.summary.saved_rows)}</Badge>
        )}
      </Card>
    );
  }

  const summary = evaluation.summary ?? {};
  const interestingFights = evaluation.interesting_fights ?? {};
  const notes = evaluation.notes ?? [];

  return (
    <Stack gap="lg" className="mantine-market-evaluation-section">
      <Card withBorder radius="xl" shadow="sm" p="xl">
        <Group justify="space-between" align="flex-start" mb="xl">
          <div>
            <Text size="xs" c="blue" fw={900} tt="uppercase" lts="0.08em">Model vs market</Text>
            <Title order={2} mt={4}>Saved odds snapshot evaluation</Title>
            <Text c="dimmed" size="sm" mt="xs" maw={780}>
              Compares saved pre-fight model picks against saved market favorites once actual results are available.
            </Text>
          </div>
          {onReload && <Button variant="light" radius="lg" leftSection={<IconRefresh size={16} />} onClick={onReload}>Reload</Button>}
        </Group>

        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
          <MetricCard label="Scored fights" value={formatNumber(summary.scored_fights)} icon={<IconChartBar size={16} />} />
          <MetricCard label="Model accuracy" value={summary.model_accuracy_percentage || "N/A"} icon={<IconTrendingUp size={16} />} />
          <MetricCard label="Market accuracy" value={summary.market_accuracy_percentage || "N/A"} icon={<IconScale size={16} />} />
          <MetricCard label="Model-only wins" value={formatNumber(summary.model_edge_count)} icon={<IconTrendingUp size={16} />} />
          <MetricCard label="Market-only wins" value={formatNumber(summary.market_edge_count)} icon={<IconScale size={16} />} />
          <MetricCard label="Agreement fights" value={formatNumber(summary.agreement_count)} icon={<IconChartBar size={16} />} />
        </SimpleGrid>

        <Group gap="xs" mt="lg">
          <Badge variant="light" size="lg">Agreement accuracy: {summary.agreement_accuracy_percentage || "N/A"}</Badge>
          <Badge variant="light" size="lg">Model disagreement: {summary.model_disagreement_accuracy_percentage || "N/A"}</Badge>
          <Badge variant="light" size="lg">Market disagreement: {summary.market_disagreement_accuracy_percentage || "N/A"}</Badge>
          <Badge variant="light" size="lg">Avg model confidence: {formatEvaluationPercentage(summary.average_model_confidence)}</Badge>
          <Badge variant="light" size="lg">Avg market confidence: {formatEvaluationPercentage(summary.average_market_confidence)}</Badge>
        </Group>

        {notes.length > 0 && (
          <Alert color="blue" variant="light" radius="lg" mt="lg">
            <Stack gap={4}>
              {notes.map((note) => <Text key={note} size="sm">{note}</Text>)}
            </Stack>
          </Alert>
        )}
      </Card>

      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
        <FightBucket
          title="Model-only wins"
          description="Fights where the model picked the winner and the saved market favorite lost."
          fights={interestingFights.model_only_wins ?? []}
        />
        <FightBucket
          title="Market-only wins"
          description="Fights where the saved market favorite won and the model pick lost."
          fights={interestingFights.market_only_wins ?? []}
        />
      </SimpleGrid>

      <Card withBorder radius="xl" shadow="sm" p="xl">
        <Title order={3}>Biggest model-market disagreements</Title>
        <Text c="dimmed" size="sm" mt={4}>
          Highest-confidence gaps among fights where the model pick and market favorite were different.
        </Text>
        {(interestingFights.biggest_disagreements ?? []).length === 0 ? (
          <Text c="dimmed" mt="md">No model-market disagreements are scored yet.</Text>
        ) : (
          <Stack gap="sm" mt="md">
            {(interestingFights.biggest_disagreements ?? []).map((fight, index) => (
              <FightRow key={`disagreement-${fight.event_id}-${fight.fight_url}-${index}`} fight={fight} />
            ))}
          </Stack>
        )}
      </Card>

      <Card withBorder radius="xl" shadow="sm" p="xl">
        <Title order={3}>Event breakdown</Title>
        {(evaluation.event_breakdown ?? []).length === 0 ? (
          <Text c="dimmed" mt="md">No scored event-level market data yet.</Text>
        ) : (
          <Stack gap="sm" mt="md">
            {(evaluation.event_breakdown ?? []).map((eventRow, index) => (
              <Paper withBorder radius="lg" p="md" key={`${eventRow.event_name}-${eventRow.event_date}-${index}`}>
                <Group justify="space-between" align="center" gap="md">
                  <div>
                    <Text fw={850}>{eventRow.event_name || "Unknown event"}</Text>
                    <Text c="dimmed" size="sm">{eventRow.event_date || "Unknown date"} • {formatNumber(eventRow.scored_fights)} scored fights</Text>
                  </div>
                  <Group gap="xs">
                    <Badge variant="light">Model {eventRow.model_accuracy_percentage || "N/A"}</Badge>
                    <Badge variant="light">Market {eventRow.market_accuracy_percentage || "N/A"}</Badge>
                    <Badge variant="light">Disagreements {formatNumber(eventRow.disagreement_count)}</Badge>
                  </Group>
                </Group>
              </Paper>
            ))}
          </Stack>
        )}
      </Card>
    </Stack>
  );
}
