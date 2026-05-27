import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Paper,
  Progress,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import {
  IconAlertTriangle,
  IconCheck,
  IconDatabase,
  IconRefresh,
  IconRocket,
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

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || !Number.isFinite(Number(seconds))) {
    return "N/A";
  }

  const totalSeconds = Math.round(Number(seconds));
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;

  if (minutes <= 0) {
    return `${remainingSeconds}s`;
  }

  return `${minutes}m ${remainingSeconds}s`;
}

function MetricCard({ label, value }) {
  return (
    <Paper withBorder radius="lg" p="md" className="mantine-update-metric">
      <Text size="xs" c="dimmed" fw={850} tt="uppercase" lts="0.06em">
        {label}
      </Text>
      <Text fw={950} size="xl" mt={4} lh={1.1}>{value}</Text>
    </Paper>
  );
}

function DetailRow({ label, value }) {
  return (
    <Group justify="space-between" align="flex-start" gap="md" py={8} className="mantine-update-detail-row">
      <Text c="dimmed" size="sm">{label}</Text>
      <Text fw={850} ta="right">{value}</Text>
    </Group>
  );
}

function DetailCard({ title, children }) {
  return (
    <Card withBorder radius="xl" shadow="sm" p="lg">
      <Title order={3} mb="sm">{title}</Title>
      <Stack gap={0}>{children}</Stack>
    </Card>
  );
}

export default function UpdateDataTab({
  startIncrementalUpdate,
  updateLoading = false,
  updateStatus,
  updateError = "",
  latestReport,
  latestReportSummary,
  latestReportStartedAt,
  latestReportFinishedAt,
  latestReportDuration,
  loadLatestReport,
  fightStatsUpdateDetails = {},
  trainModelDetails = {},
  refreshFutureCardsDetails = {},
  saveFuturePredictionsDetails = {},
}) {
  const progressPercent = updateStatus?.progress_percent ?? 0;
  const updateRunning = Boolean(updateStatus?.running);
  const latestSuccess = latestReportSummary?.success === true;
  const latestFailed = latestReportSummary?.success === false;

  return (
    <Stack gap="lg" className="mantine-update-page">
      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
        <Card withBorder radius="xl" shadow="sm" p="xl">
          <Group gap="xs" mb="xs">
            <IconRocket size={20} />
            <Text size="xs" c="blue" fw={900} tt="uppercase" lts="0.08em">
              Incremental update
            </Text>
          </Group>
          <Title order={2}>Update data and retrain model</Title>
          <Text c="dimmed" size="sm" mt="sm" lh={1.6}>
            This updates completed events, scrapes only missing fight details, rebuilds features,
            retrains the calibrated model, rebuilds current fighter features, refreshes future cards,
            and saves future-card predictions.
          </Text>
          <Text c="dimmed" size="sm" mt="xs" lh={1.6}>
            Most updates should be much faster than a full rebuild, but it can still take several minutes if new fights are available.
          </Text>

          <Button
            mt="xl"
            size="md"
            radius="lg"
            leftSection={<IconRocket size={17} />}
            onClick={startIncrementalUpdate}
            disabled={updateLoading || updateRunning}
            loading={updateLoading || updateRunning}
          >
            {updateRunning ? "Update running..." : "Start incremental update"}
          </Button>

          {updateError && <Alert color="red" radius="lg" mt="md">{updateError}</Alert>}
        </Card>

        <Card withBorder radius="xl" shadow="sm" p="xl">
          <Group justify="space-between" align="flex-start" mb="lg">
            <div>
              <Text size="xs" c="blue" fw={900} tt="uppercase" lts="0.08em">
                Pipeline status
              </Text>
              <Title order={2}>Update progress</Title>
            </div>
            <Badge color={updateRunning ? "blue" : "gray"} variant="light" size="lg">
              {updateRunning ? "Running" : "Idle"}
            </Badge>
          </Group>

          <Group justify="space-between" mb="xs">
            <Text fw={950} size="xl">{progressPercent}%</Text>
            <Text c="dimmed" size="sm">
              Stage {updateStatus?.current_stage_index ?? 0} of {updateStatus?.total_stages ?? 12}
            </Text>
          </Group>
          <Progress value={progressPercent} radius="xl" size="lg" animated={updateRunning} />

          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md" mt="xl">
            <MetricCard label="Status" value={updateRunning ? "Running" : "Idle"} />
            <MetricCard label="Current stage" value={updateStatus?.current_stage ?? "None"} />
            <MetricCard label="Message" value={updateStatus?.message ?? "No status yet."} />
            <MetricCard
              label="Last result"
              value={updateStatus?.success === true ? "Success" : updateStatus?.success === false ? "Failed" : "Not finished"}
            />
          </SimpleGrid>
        </Card>
      </SimpleGrid>

      <Card withBorder radius="xl" shadow="sm" p="xl">
        <Group justify="space-between" align="flex-start" mb="lg">
          <div>
            <Text size="xs" c="blue" fw={900} tt="uppercase" lts="0.08em">
              Last update report
            </Text>
            <Title order={2}>Update summary</Title>
          </div>
          <Button variant="light" radius="lg" leftSection={<IconRefresh size={16} />} onClick={loadLatestReport}>
            Reload report
          </Button>
        </Group>

        {!latestReport?.available && (
          <Paper withBorder radius="xl" p="xl" ta="center">
            <Title order={3}>No report yet</Title>
            <Text c="dimmed" mt="xs">{latestReport?.message ?? "Run an update to generate a report."}</Text>
          </Paper>
        )}

        {latestReport?.available && latestReportSummary && (
          <Stack gap="lg">
            <Alert
              color={latestSuccess ? "green" : latestFailed ? "red" : "gray"}
              radius="lg"
              icon={latestSuccess ? <IconCheck size={18} /> : <IconAlertTriangle size={18} />}
            >
              <Text fw={850}>
                {latestSuccess ? "Latest update completed successfully" : "Latest update finished with failures"}
              </Text>
              <Text size="sm">
                Started {latestReportStartedAt || "N/A"} • Finished {latestReportFinishedAt || "N/A"} • Duration {formatDuration(latestReportDuration)}
              </Text>
            </Alert>

            <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
              <MetricCard label="Completed events" value={formatNumber(latestReportSummary.completed_events_rows)} />
              <MetricCard label="Event fights" value={formatNumber(latestReportSummary.event_fights_rows)} />
              <MetricCard label="Fight stat rows" value={formatNumber(latestReportSummary.fight_stats_rows)} />
              <MetricCard label="Current fighters" value={formatNumber(latestReportSummary.current_fighter_features_rows)} />
              <MetricCard label="Upcoming events" value={formatNumber(latestReportSummary.upcoming_events_rows)} />
              <MetricCard label="Upcoming fights" value={formatNumber(latestReportSummary.upcoming_fights_rows)} />
              <MetricCard label="Saved predictions" value={formatNumber(latestReportSummary.saved_card_predictions_rows)} />
              <MetricCard label="Training rows" value={formatNumber(latestReportSummary.training_matchups_rows)} />
            </SimpleGrid>

            <SimpleGrid cols={{ base: 1, lg: 3 }} spacing="lg">
              <DetailCard title="Fight stats update">
                <DetailRow label="Missing fights checked" value={formatNumber(fightStatsUpdateDetails.missing_fights_checked)} />
                <DetailRow label="Fights scraped" value={formatNumber(fightStatsUpdateDetails.missing_fights_scraped)} />
                <DetailRow label="Skipped fights" value={formatNumber(fightStatsUpdateDetails.skipped_fight_count)} />
                <DetailRow label="New stat rows" value={formatNumber(fightStatsUpdateDetails.new_fighter_stat_rows)} />
              </DetailCard>

              <DetailCard title="Model training">
                <DetailRow label="Best model" value={trainModelDetails.best_model_name || "N/A"} />
                <DetailRow
                  label="Fight accuracy"
                  value={trainModelDetails.best_model_metrics?.accuracy !== undefined ? `${(trainModelDetails.best_model_metrics.accuracy * 100).toFixed(1)}%` : "N/A"}
                />
                <DetailRow
                  label="Brier score"
                  value={trainModelDetails.best_model_metrics?.brier_score !== undefined ? Number(trainModelDetails.best_model_metrics.brier_score).toFixed(4) : "N/A"}
                />
                <DetailRow
                  label="Log loss"
                  value={trainModelDetails.best_model_metrics?.log_loss !== undefined ? Number(trainModelDetails.best_model_metrics.log_loss).toFixed(4) : "N/A"}
                />
              </DetailCard>

              <DetailCard title="Future cards">
                <DetailRow label="Upcoming events" value={formatNumber(refreshFutureCardsDetails.events)} />
                <DetailRow label="Upcoming fights" value={formatNumber(refreshFutureCardsDetails.fights)} />
                <DetailRow label="Cards saved" value={formatNumber(saveFuturePredictionsDetails.cards_saved)} />
                <DetailRow label="Prediction rows saved" value={formatNumber(saveFuturePredictionsDetails.total_rows)} />
              </DetailCard>
            </SimpleGrid>

            {fightStatsUpdateDetails.skipped_fights?.length > 0 && (
              <Card withBorder radius="xl" p="lg" className="mantine-skipped-fights-card">
                <Title order={3}>Skipped fights</Title>
                <Text c="dimmed" size="sm" mt={4}>
                  These fights were detected but skipped because complete stat tables were unavailable.
                </Text>
                <Stack gap="sm" mt="md">
                  {fightStatsUpdateDetails.skipped_fights.slice(0, 8).map((fight, index) => (
                    <Paper withBorder radius="lg" p="md" key={`${fight.fight_url}-${index}`}>
                      <Text fw={850}>{fight.fighter_1} vs {fight.fighter_2}</Text>
                      <Text c="dimmed" size="sm">{fight.reason}</Text>
                    </Paper>
                  ))}
                </Stack>
                {fightStatsUpdateDetails.skipped_fights.length > 8 && (
                  <Text c="dimmed" size="sm" mt="md">
                    Showing 8 of {fightStatsUpdateDetails.skipped_fights.length} skipped fights.
                  </Text>
                )}
              </Card>
            )}

            {latestReportSummary.failed_stages?.length > 0 && (
              <Alert color="red" radius="lg">
                Failed stages: {latestReportSummary.failed_stages.join(", ")}
              </Alert>
            )}
          </Stack>
        )}
      </Card>
    </Stack>
  );
}
