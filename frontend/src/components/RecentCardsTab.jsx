import {
  Alert,
  Badge,
  Button,
  Card,
  Divider,
  Grid,
  Group,
  Paper,
  ScrollArea,
  SimpleGrid,
  Stack,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import {
  IconAlertTriangle,
  IconCalendarCheck,
  IconCheck,
  IconClock,
  IconRefresh,
  IconTargetArrow,
  IconX,
} from "@tabler/icons-react";

import { FighterMatchup, FighterName } from "./FighterDisplay";
import RecentFightDetails from "./RecentFightDetails";

function getRecentCardStatusClass(status = "") {
  const normalizedStatus = String(status).toLowerCase();

  if (normalizedStatus === "completed") {
    return "completed";
  }

  if (normalizedStatus === "partially_completed") {
    return "partial";
  }

  return "waiting";
}

function getRecentCardStatusLabel(status = "") {
  const statusClass = getRecentCardStatusClass(status);

  if (statusClass === "completed") {
    return "Completed";
  }

  if (statusClass === "partial") {
    return "Partial";
  }

  return "Waiting";
}

function getRecentCardStatusColor(status = "") {
  const statusClass = getRecentCardStatusClass(status);

  if (statusClass === "completed") {
    return "green";
  }

  if (statusClass === "partial") {
    return "blue";
  }

  return "gray";
}

function getRecentFightResultClass(fight) {
  if (!fight?.actual_result_available) {
    return "waiting";
  }

  if (
    !fight?.prediction_available ||
    fight.prediction_correct === null ||
    fight.prediction_correct === undefined
  ) {
    return "no-prediction";
  }

  if (fight.prediction_correct === true) {
    return "correct";
  }

  return "incorrect";
}

function getRecentFightResultLabel(resultClass) {
  if (resultClass === "correct") {
    return "Correct";
  }

  if (resultClass === "incorrect") {
    return "Wrong";
  }

  if (resultClass === "no-prediction") {
    return "No prediction";
  }

  return "Waiting";
}

function getRecentFightResultColor(resultClass) {
  if (resultClass === "correct") {
    return "green";
  }

  if (resultClass === "incorrect") {
    return "red";
  }

  if (resultClass === "no-prediction") {
    return "gray";
  }

  return "yellow";
}

function getRecentFightResultIcon(resultClass) {
  if (resultClass === "correct") {
    return <IconCheck size={15} />;
  }

  if (resultClass === "incorrect") {
    return <IconX size={15} />;
  }

  return <IconClock size={15} />;
}

function SummaryMetric({ label, value, tone = "default" }) {
  const colors = {
    default: "gray",
    good: "green",
    info: "blue",
    warning: "yellow",
    danger: "red",
    muted: "gray",
  };

  return (
    <Paper withBorder radius="lg" p="md" className="mantine-summary-metric">
      <Text size="xs" fw={800} tt="uppercase" c="dimmed">
        {label}
      </Text>
      <Text size="xl" fw={900} c={colors[tone] || "gray"} mt={4}>
        {value ?? "N/A"}
      </Text>
    </Paper>
  );
}

export default function RecentCardsTab({
  recentCards = [],
  recentLoading = false,
  recentError = "",
  loadRecentCards,
  selectedRecentCardId = "",
  setSelectedRecentCardId,
  selectedRecentCard,
  selectedRecentCardSummary = {},
  selectedRecentFight,
  setSelectedRecentFight,
  fighterImageLookup = {},
  openFighterProfile,
}) {
  return (
    <Grid gutter="lg" align="flex-start" className="mantine-page-grid mantine-recent-page">
      <Grid.Col span={{ base: 12, lg: 3 }}>
        <Card withBorder radius="xl" padding="lg" className="mantine-panel sticky-panel">
          <Group justify="space-between" align="center" mb="md">
            <div>
              <Text size="xs" fw={900} tt="uppercase" c="blue">
                Tracking
              </Text>
              <Title order={2} size="h3">
                Recent cards
              </Title>
            </div>

            <Tooltip label="Reload saved cards and scored results">
              <Button
                type="button"
                variant="light"
                size="xs"
                leftSection={<IconRefresh size={15} />}
                onClick={loadRecentCards}
                loading={recentLoading}
              >
                Reload
              </Button>
            </Tooltip>
          </Group>

          {recentError && (
            <Alert color="red" icon={<IconAlertTriangle size={16} />} mb="sm">
              {recentError}
            </Alert>
          )}

          <ScrollArea.Autosize mah={720} offsetScrollbars>
            <Stack gap="xs">
              {recentCards.length === 0 && !recentLoading && (
                <Paper withBorder radius="lg" p="md" className="mantine-empty-mini">
                  <Text fw={900}>No saved cards yet</Text>
                  <Text c="dimmed" size="sm" mt={4}>
                    Save future-card predictions first, then this tab can compare them
                    against actual results later.
                  </Text>
                </Paper>
              )}

              {recentCards.map((card) => {
                const isActive = selectedRecentCardId === card.event_id;
                const statusLabel = getRecentCardStatusLabel(card.status);
                const statusColor = getRecentCardStatusColor(card.status);

                return (
                  <Paper
                    key={card.event_id}
                    component="button"
                    type="button"
                    withBorder
                    radius="lg"
                    p="md"
                    className={`mantine-list-button ${isActive ? "active" : ""}`}
                    onClick={() => {
                      setSelectedRecentCardId(card.event_id);
                      setSelectedRecentFight(null);
                    }}
                  >
                    <Group justify="space-between" align="flex-start" gap="sm" wrap="nowrap">
                      <div>
                        <Text fw={900} size="sm" lh={1.25}>
                          {card.event_name}
                        </Text>
                        <Text size="xs" c="dimmed" mt={5}>
                          {card.event_date}
                        </Text>
                        <Text size="xs" c="dimmed" lineClamp={2}>
                          {card.event_location}
                        </Text>
                      </div>

                      <Badge variant={isActive ? "filled" : "light"} color={statusColor} size="sm">
                        {statusLabel}
                      </Badge>
                    </Group>

                    <Text size="xs" c="dimmed" mt="xs" fw={700}>
                      {card.status === "completed"
                        ? `${card.accuracy_percentage || "N/A"} accuracy`
                        : card.status === "partially_completed"
                          ? `${card.actual_result_count} of ${card.fight_count} results in`
                          : `${card.fight_count} saved predictions`}
                    </Text>
                  </Paper>
                );
              })}
            </Stack>
          </ScrollArea.Autosize>
        </Card>
      </Grid.Col>

      <Grid.Col span={{ base: 12, lg: 5 }}>
        <Card withBorder radius="xl" padding="lg" className="mantine-panel">
          {!selectedRecentCard && (
            <Stack align="center" justify="center" mih={360} ta="center">
              <IconCalendarCheck size={42} stroke={1.6} />
              <div>
                <Title order={2} size="h3">
                  {recentLoading ? "Loading card..." : "Select a recent card"}
                </Title>
                <Text c="dimmed" mt={6}>
                  Pick a saved card to compare pre-fight predictions against actual results.
                </Text>
              </div>
            </Stack>
          )}

          {selectedRecentCard && (
            <Stack gap="lg">
              <Group justify="space-between" align="flex-start" gap="md">
                <div>
                  <Text size="xs" fw={900} tt="uppercase" c="blue">
                    Saved card
                  </Text>
                  <Title order={2} size="h3">
                    {selectedRecentCard.event_name}
                  </Title>
                  <Text c="dimmed" size="sm" mt={4}>
                    {selectedRecentCard.event_date} • {selectedRecentCard.event_location}
                  </Text>
                </div>

                <Paper withBorder radius="lg" p="md" className="mantine-recent-score-card">
                  <Badge
                    variant="light"
                    color={getRecentCardStatusColor(selectedRecentCard.status)}
                    mb={8}
                  >
                    {selectedRecentCard.status === "completed"
                      ? "Completed"
                      : selectedRecentCard.status === "partially_completed"
                        ? "Partially completed"
                        : "Waiting for results"}
                  </Badge>

                  <Text fw={900} size="xl">
                    {selectedRecentCardSummary.accuracyPercentage}
                  </Text>
                  <Text size="xs" c="dimmed" fw={700}>
                    {selectedRecentCardSummary.correctCount} correct of {" "}
                    {selectedRecentCardSummary.predictedCompletedCount} scored predictions
                  </Text>
                  <Text size="xs" c="dimmed" fw={700} mt={4}>
                    Market: {selectedRecentCardSummary.marketAccuracyPercentage} over {" "}
                    {selectedRecentCardSummary.marketCompletedCount} scored fights
                  </Text>
                </Paper>
              </Group>

              <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
                <SummaryMetric label="Total fights" value={selectedRecentCardSummary.totalFights} />
                <SummaryMetric label="Results in" value={selectedRecentCardSummary.actualResultCount} tone="info" />
                <SummaryMetric label="Correct" value={selectedRecentCardSummary.correctCount} tone="good" />
                <SummaryMetric label="Wrong" value={selectedRecentCardSummary.wrongCount} tone="danger" />
                <SummaryMetric label="Waiting" value={selectedRecentCardSummary.waitingCount} tone="warning" />
                <SummaryMetric label="Accuracy" value={selectedRecentCardSummary.accuracyPercentage} tone="good" />
                <SummaryMetric label="Market accuracy" value={selectedRecentCardSummary.marketAccuracyPercentage} tone="info" />
                <SummaryMetric label="Market scored" value={selectedRecentCardSummary.marketCompletedCount} />
              </SimpleGrid>

              {selectedRecentCard.status === "waiting_for_results" && (
                <Alert color="blue" icon={<IconClock size={16} />}>
                  This card is waiting for completed fight results. After the event happens,
                  run the Update Data pipeline to scrape results and score the saved predictions.
                </Alert>
              )}

              <Divider />

              <Stack gap="sm">
                {selectedRecentCard.fights?.map((fight) => {
                  const resultClass = getRecentFightResultClass(fight);
                  const resultColor = getRecentFightResultColor(resultClass);
                  const isActive = selectedRecentFight?.fight_id === fight.fight_id;

                  return (
                    <Paper
                      key={fight.fight_id}
                      component="button"
                      type="button"
                      withBorder
                      radius="lg"
                      p="md"
                      className={`mantine-fight-card mantine-recent-fight-card ${isActive ? "active" : ""}`}
                      onClick={() => setSelectedRecentFight(fight)}
                    >
                      <Group justify="space-between" align="flex-start" gap="md" wrap="nowrap">
                        <Stack gap={6} miw={0}>
                          <Text fw={900} lh={1.25}>
                            <FighterMatchup
                              fighter1={fight.fighter_1}
                              fighter2={fight.fighter_2}
                              imageLookup={fighterImageLookup}
                              onFighterClick={openFighterProfile}
                            />
                          </Text>

                          <Group gap="xs">
                            <Badge variant="light" color="gray">
                              {fight.weight_class || "Weight class unknown"}
                            </Badge>
                            {fight.confidence_percentage && (
                              <Badge variant="light" color="blue">
                                {fight.confidence_percentage} confidence
                              </Badge>
                            )}
                            {fight.odds_available && (
                              <Badge variant="light" color="violet">
                                Market: {fight.market_favorite || "N/A"} {" "}
                                {fight.market_favorite_percentage || ""}
                              </Badge>
                            )}
                          </Group>

                          <Text size="xs" c="dimmed" fw={700}>
                            Predicted: {fight.predicted_winner || "N/A"}
                          </Text>
                        </Stack>

                        <Stack gap={5} align="flex-end" className="mantine-pick-stack">
                          <Badge
                            variant="light"
                            color={resultColor}
                            leftSection={getRecentFightResultIcon(resultClass)}
                          >
                            {getRecentFightResultLabel(resultClass)}
                          </Badge>

                          {fight.actual_result_available ? (
                            <>
                              <Text fw={900} ta="right">
                                <FighterName
                                  name={fight.actual_winner}
                                  imageLookup={fighterImageLookup}
                                />
                              </Text>
                              <Text size="xs" c="dimmed" ta="right" fw={700}>
                                {!fight.prediction_available
                                  ? "No saved prediction"
                                  : fight.actual_method
                                    ? `${fight.actual_method}${fight.actual_round ? ` • R${fight.actual_round}` : ""}`
                                    : "Actual winner"}
                              </Text>
                            </>
                          ) : (
                            <>
                              <Text fw={900} ta="right">
                                {fight.predicted_winner ? (
                                  <FighterName
                                    name={fight.predicted_winner}
                                    imageLookup={fighterImageLookup}
                                  />
                                ) : (
                                  "No prediction"
                                )}
                              </Text>
                              <Text size="xs" c="dimmed" ta="right" fw={700}>
                                Awaiting result
                              </Text>
                            </>
                          )}
                        </Stack>
                      </Group>
                    </Paper>
                  );
                })}
              </Stack>
            </Stack>
          )}
        </Card>
      </Grid.Col>

      <Grid.Col span={{ base: 12, lg: 4 }}>
        <Card withBorder radius="xl" padding="lg" className="mantine-panel sticky-panel">
          <Group gap="sm" mb="md">
            <IconTargetArrow size={20} />
            <div>
              <Text size="xs" fw={900} tt="uppercase" c="blue">
                Result panel
              </Text>
              <Title order={2} size="h3">
                Fight detail
              </Title>
            </div>
          </Group>

          <RecentFightDetails
            fight={selectedRecentFight}
            fighterImageLookup={fighterImageLookup}
          />
        </Card>
      </Grid.Col>
    </Grid>
  );
}
