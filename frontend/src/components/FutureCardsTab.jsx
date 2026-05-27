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
  IconCalendarEvent,
  IconRefresh,
  IconTargetArrow,
} from "@tabler/icons-react";

import { FighterMatchup, FighterName } from "./FighterDisplay";
import PredictionDetails from "./PredictionDetails";
import FightOddsComparison from "./FightOddsComparison";

function SummaryMetric({ label, value, tone = "default" }) {
  const colors = {
    default: "gray",
    good: "green",
    info: "blue",
    warning: "yellow",
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

function getConfidenceColor(label = "") {
  const normalized = String(label).toLowerCase();

  if (normalized.includes("high") || normalized.includes("strong")) {
    return "green";
  }

  if (normalized.includes("moderate")) {
    return "blue";
  }

  if (normalized.includes("close") || normalized.includes("slight")) {
    return "yellow";
  }

  return "gray";
}

export default function FutureCardsTab({
  cardsLoading = false,
  cardsError = "",
  futureFightOddsError = "",
  futureCards = [],
  selectedCardId = "",
  setSelectedCardId,
  selectedCard,
  cardPredictionsLoading = false,
  selectedFutureCardSummary = {},
  selectedFightPrediction,
  setSelectedFightPrediction,
  refreshFutureCards,
  loadCardPredictions,
  fighterImageLookup = {},
  openFighterProfile,
  futureFightOdds = [],
  getOddsForFight,
}) {
  return (
    <Grid gutter="lg" align="flex-start" className="mantine-page-grid">
      <Grid.Col span={{ base: 12, lg: 3 }}>
        <Card withBorder radius="xl" padding="lg" className="mantine-panel sticky-panel">
          <Group justify="space-between" align="center" mb="md">
            <div>
              <Text size="xs" fw={900} tt="uppercase" c="blue">
                Schedule
              </Text>
              <Title order={2} size="h3">
                Future cards
              </Title>
            </div>

            <Tooltip label="Refresh upcoming card list and odds">
              <Button
                type="button"
                variant="light"
                size="xs"
                leftSection={<IconRefresh size={15} />}
                onClick={refreshFutureCards}
                loading={cardsLoading}
              >
                Refresh
              </Button>
            </Tooltip>
          </Group>

          {cardsError && (
            <Alert color="red" icon={<IconAlertTriangle size={16} />} mb="sm">
              {cardsError}
            </Alert>
          )}

          {futureFightOddsError && (
            <Alert color="yellow" icon={<IconAlertTriangle size={16} />} mb="sm">
              {futureFightOddsError}
            </Alert>
          )}

          <ScrollArea.Autosize mah={720} offsetScrollbars>
            <Stack gap="xs">
              {futureCards.length === 0 && !cardsLoading && (
                <Text c="dimmed" size="sm">
                  No future cards loaded yet.
                </Text>
              )}

              {futureCards.map((card) => {
                const isActive = selectedCardId === card.event_id;

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
                      setSelectedCardId(card.event_id);
                      setSelectedFightPrediction(null);
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

                      <Badge variant={isActive ? "filled" : "light"} color="blue" size="sm">
                        {card.fight_count}
                      </Badge>
                    </Group>
                  </Paper>
                );
              })}
            </Stack>
          </ScrollArea.Autosize>
        </Card>
      </Grid.Col>

      <Grid.Col span={{ base: 12, lg: 5 }}>
        <Card withBorder radius="xl" padding="lg" className="mantine-panel">
          {!selectedCard && (
            <Stack align="center" justify="center" mih={360} ta="center">
              <IconCalendarEvent size={42} stroke={1.6} />
              <div>
                <Title order={2} size="h3">
                  {cardPredictionsLoading ? "Loading card..." : "Select a card"}
                </Title>
                <Text c="dimmed" mt={6}>
                  Pick an upcoming card to see scheduled fight predictions.
                </Text>
              </div>
            </Stack>
          )}

          {selectedCard && (
            <Stack gap="lg">
              <Group justify="space-between" align="flex-start" gap="md">
                <div>
                  <Text size="xs" fw={900} tt="uppercase" c="blue">
                    Selected card
                  </Text>
                  <Title order={2} size="h3">
                    {selectedCard.event_name}
                  </Title>
                  <Text c="dimmed" size="sm" mt={4}>
                    {selectedCard.event_date} • {selectedCard.event_location}
                  </Text>
                </div>

                <Button
                  type="button"
                  variant="light"
                  leftSection={<IconRefresh size={16} />}
                  onClick={() => loadCardPredictions(selectedCard.event_id)}
                  loading={cardPredictionsLoading}
                >
                  Reload
                </Button>
              </Group>

              <SimpleGrid cols={{ base: 2, sm: 3 }} spacing="sm">
                <SummaryMetric label="Total fights" value={selectedFutureCardSummary.totalFights} />
                <SummaryMetric
                  label="Predictions"
                  value={selectedFutureCardSummary.predictionAvailableCount}
                  tone="good"
                />
                <SummaryMetric
                  label="No prediction"
                  value={selectedFutureCardSummary.predictionUnavailableCount}
                  tone="warning"
                />
                <SummaryMetric
                  label="Strong leans"
                  value={selectedFutureCardSummary.highConfidenceCount}
                  tone="good"
                />
                <SummaryMetric
                  label="Moderate"
                  value={selectedFutureCardSummary.moderateConfidenceCount}
                  tone="info"
                />
                <SummaryMetric
                  label="Close fights"
                  value={selectedFutureCardSummary.closeFightCount}
                  tone="muted"
                />
              </SimpleGrid>

              <Divider />

              <Stack gap="sm">
                {selectedCard.fights?.map((fight) => {
                  const isActive =
                    selectedFightPrediction &&
                    fight.prediction?.fighter_a === selectedFightPrediction.fighter_a &&
                    fight.prediction?.fighter_b === selectedFightPrediction.fighter_b;

                  const odds =
                    typeof getOddsForFight === "function"
                      ? getOddsForFight(futureFightOdds, fight.fight_url)
                      : null;

                  return (
                    <Paper
                      key={fight.fight_id}
                      withBorder
                      radius="lg"
                      p="md"
                      className={`mantine-fight-card ${isActive ? "active" : ""} ${
                        fight.prediction_available ? "clickable" : ""
                      }`}
                      onClick={() => {
                        if (fight.prediction_available) {
                          setSelectedFightPrediction(fight.prediction);
                        }
                      }}
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
                            {fight.prediction_available && fight.prediction?.confidence_label && (
                              <Badge
                                variant="light"
                                color={getConfidenceColor(fight.prediction.confidence_label)}
                              >
                                {fight.prediction.confidence_label}
                              </Badge>
                            )}
                          </Group>
                        </Stack>

                        {fight.prediction_available ? (
                          <Stack gap={3} align="flex-end" className="mantine-pick-stack">
                            <Text size="xs" c="dimmed" fw={800} tt="uppercase">
                              Pick
                            </Text>
                            <Text fw={900} c="blue" ta="right">
                              <FighterName
                                name={fight.prediction.predicted_winner}
                                imageLookup={fighterImageLookup}
                              />
                            </Text>
                            <Text size="sm" c="dimmed" fw={800}>
                              {fight.prediction.confidence_percentage}
                            </Text>
                          </Stack>
                        ) : (
                          <Stack gap={3} align="flex-end" className="mantine-pick-stack">
                            <Text size="xs" c="red" fw={900} tt="uppercase">
                              No prediction
                            </Text>
                            <Text size="sm" c="dimmed" ta="right" maw={190} lineClamp={2}>
                              {fight.error?.message ?? "Missing fighter data"}
                            </Text>
                          </Stack>
                        )}
                      </Group>

                      <div className="mantine-fight-odds-wrap">
                        <FightOddsComparison fight={fight} odds={odds} />
                      </div>
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
                Prediction panel
              </Text>
              <Title order={2} size="h3">
                Fight detail
              </Title>
            </div>
          </Group>

          <PredictionDetails
            prediction={selectedFightPrediction}
            fighterImageLookup={fighterImageLookup}
          />
        </Card>
      </Grid.Col>
    </Grid>
  );
}
