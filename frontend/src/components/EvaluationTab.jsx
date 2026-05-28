import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  NumberInput,
  Paper,
  ScrollArea,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import {
  IconChartBar,
  IconRefresh,
  IconTarget,
  IconTrendingUp,
} from "@tabler/icons-react";
import ModelVsMarketEvaluationPanel from "./ModelVsMarketEvaluationPanel";

function formatCalibrationGap(row) {
  if (
    row?.accuracy === null ||
    row?.accuracy === undefined ||
    row?.average_confidence === null ||
    row?.average_confidence === undefined
  ) {
    return "N/A";
  }

  const gap = Number(row.accuracy) - Number(row.average_confidence);

  if (!Number.isFinite(gap)) {
    return "N/A";
  }

  const sign = gap >= 0 ? "+" : "";
  return `${sign}${(gap * 100).toFixed(1)} pts`;
}

function getCalibrationClass(row) {
  if (
    row?.accuracy === null ||
    row?.accuracy === undefined ||
    row?.average_confidence === null ||
    row?.average_confidence === undefined
  ) {
    return "gray";
  }

  const gap = Math.abs(Number(row.accuracy) - Number(row.average_confidence));

  if (!Number.isFinite(gap)) {
    return "gray";
  }

  if (gap <= 0.05) {
    return "green";
  }

  if (gap <= 0.10) {
    return "yellow";
  }

  return "red";
}

function getSampleSizeClass(fightCount) {
  const count = Number(fightCount);

  if (!Number.isFinite(count)) {
    return "gray";
  }

  if (count < 20) {
    return "yellow";
  }

  if (count < 50) {
    return "blue";
  }

  return "green";
}

function getSampleSizeLabel(fightCount) {
  const count = Number(fightCount);

  if (!Number.isFinite(count)) {
    return "Unknown sample";
  }

  if (count < 20) {
    return "Low sample";
  }

  if (count < 50) {
    return "Moderate sample";
  }

  return "Good sample";
}

function formatModelName(modelName = "") {
  const names = {
    calibrated_logistic_regression: "Calibrated Logistic",
    calibrated_random_forest: "Calibrated Random Forest",
    calibrated_xgboost: "Calibrated XGBoost",
    calibrated_extra_trees: "Calibrated Extra Trees",
    calibrated_hist_gradient_boosting: "Calibrated Hist Gradient",
    logistic_regression: "Logistic Regression",
    random_forest: "Random Forest",
    xgboost: "XGBoost",
    extra_trees: "Extra Trees",
    hist_gradient_boosting: "Hist Gradient Boosting",
    elo_baseline: "Elo Baseline",
    ensemble_average: "Ensemble Average",
  };

  return names[modelName] ?? modelName.replaceAll("_", " ");
}

function formatMetricPercent(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "N/A";
  }

  return `${(Number(value) * 100).toFixed(1)}%`;
}

function formatMetricDecimal(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "N/A";
  }

  return Number(value).toFixed(4);
}

function formatInteger(value) {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  const numberValue = Number(value);

  if (!Number.isFinite(numberValue)) {
    return String(value);
  }

  return numberValue.toLocaleString();
}

function getProspectiveModelRows(evaluation) {
  if (!evaluation) {
    return [];
  }

  if (Array.isArray(evaluation.models)) {
    return evaluation.models;
  }

  if (Array.isArray(evaluation.model_results)) {
    return evaluation.model_results;
  }

  if (Array.isArray(evaluation.by_model)) {
    return evaluation.by_model;
  }

  if (evaluation.models && typeof evaluation.models === "object") {
    return Object.entries(evaluation.models).map(([modelName, modelData]) => ({
      model_name: modelName,
      ...(modelData || {}),
    }));
  }

  return [];
}

function getProspectiveRecentRows(evaluation) {
  if (!evaluation) {
    return [];
  }

  if (Array.isArray(evaluation.recent_scored_fights)) {
    return evaluation.recent_scored_fights;
  }

  if (Array.isArray(evaluation.recent_predictions)) {
    return evaluation.recent_predictions;
  }

  if (Array.isArray(evaluation.scored_predictions)) {
    return evaluation.scored_predictions.slice(0, 25);
  }

  return [];
}

function getAccuracyColor(value) {
  const numberValue = Number(value);

  if (!Number.isFinite(numberValue)) {
    return "gray";
  }

  if (numberValue >= 0.6) {
    return "green";
  }

  if (numberValue >= 0.52) {
    return "blue";
  }

  return "yellow";
}

function hasScoredStats(row) {
  return Number(row?.scored_fights ?? row?.fight_count ?? 0) > 0;
}

function getModelKind(modelName = "") {
  const normalized = String(modelName).toLowerCase();

  if (normalized.includes("ensemble")) {
    return "Ensemble";
  }

  if (normalized.includes("elo")) {
    return "Baseline";
  }

  if (normalized.includes("calibrated")) {
    return "Calibrated";
  }

  if (normalized.includes("forest") || normalized.includes("trees") || normalized.includes("boost")) {
    return "Tree model";
  }

  if (normalized.includes("logistic")) {
    return "Linear model";
  }

  return "Model";
}

function getModelKindColor(modelName = "") {
  const kind = getModelKind(modelName);

  if (kind === "Ensemble") {
    return "violet";
  }

  if (kind === "Baseline") {
    return "gray";
  }

  if (kind === "Calibrated") {
    return "blue";
  }

  if (kind === "Tree model") {
    return "green";
  }

  if (kind === "Linear model") {
    return "cyan";
  }

  return "gray";
}

function getModelDescription(modelName = "") {
  const normalized = String(modelName).toLowerCase();

  if (normalized === "elo_baseline") {
    return "Simple Elo-only benchmark. Every advanced model should eventually beat this.";
  }

  if (normalized === "ensemble_average") {
    return "Average of available model probabilities. Useful as a stability check.";
  }

  if (normalized.includes("calibrated")) {
    return "Probability-calibrated version intended to make confidence more trustworthy.";
  }

  if (normalized.includes("hist_gradient")) {
    return "Gradient boosting model for tabular matchup features.";
  }

  if (normalized.includes("extra_trees")) {
    return "Randomized tree ensemble used as another tabular model comparison.";
  }

  if (normalized.includes("xgboost")) {
    return "Boosted tree model; often strong on tabular sports features.";
  }

  if (normalized.includes("random_forest")) {
    return "Tree ensemble baseline that can capture nonlinear feature interactions.";
  }

  if (normalized.includes("logistic")) {
    return "Regularized linear model. Simple, stable, and useful as a sanity check.";
  }

  return "Tracked prospective model for future-fight prediction comparison.";
}

function sortProspectiveModelRows(rows = []) {
  return [...rows].sort((a, b) => {
    const aScored = hasScoredStats(a) ? 0 : 1;
    const bScored = hasScoredStats(b) ? 0 : 1;

    if (aScored !== bScored) {
      return aScored - bScored;
    }

    const aBrier = Number(a.brier_score);
    const bBrier = Number(b.brier_score);

    if (Number.isFinite(aBrier) && Number.isFinite(bBrier) && aBrier !== bBrier) {
      return aBrier - bBrier;
    }

    const aAccuracy = Number(a.accuracy);
    const bAccuracy = Number(b.accuracy);

    if (Number.isFinite(aAccuracy) && Number.isFinite(bAccuracy) && aAccuracy !== bAccuracy) {
      return bAccuracy - aAccuracy;
    }

    return formatModelName(a.model_name).localeCompare(formatModelName(b.model_name));
  });
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

function MethodMetricCard({ title, note, metrics }) {
  if (!metrics) {
    return null;
  }

  return (
    <Card withBorder radius="xl" shadow="sm" p="xl">
      <Text size="xs" c="blue" fw={900} tt="uppercase" lts="0.08em">
        Manner of ending
      </Text>
      <Title order={3} mt={4}>{title}</Title>
      <Text c="dimmed" size="sm" mt={4}>{note}</Text>

      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md" mt="lg">
        <MetricCard label="Best model" value={formatModelName(metrics.best_model_name)} icon={<IconChartBar size={16} />} />
        <MetricCard label="Accuracy" value={formatMetricPercent(metrics.best_metrics?.accuracy)} icon={<IconTarget size={16} />} />
        <MetricCard label="Log loss" value={formatMetricDecimal(metrics.best_metrics?.log_loss)} icon={<IconChartBar size={16} />} />
        <MetricCard label="Top-2 accuracy" value={formatMetricPercent(metrics.best_metrics?.top_2_accuracy)} icon={<IconTrendingUp size={16} />} />
        <MetricCard label="Top-3 accuracy" value={formatMetricPercent(metrics.best_metrics?.top_3_accuracy)} icon={<IconTrendingUp size={16} />} />
      </SimpleGrid>
    </Card>
  );
}

function ThresholdCard({ rows = [] }) {
  return (
    <Card withBorder radius="xl" shadow="sm" p="xl">
      <Title order={3}>Favorite threshold performance</Title>
      <Text c="dimmed" size="sm" mt={4}>
        Cumulative accuracy for fights where the model favorite reached at least this confidence level.
      </Text>

      <Stack gap="sm" mt="md">
        {rows.map((row) => (
          <Paper withBorder radius="lg" p="md" key={row.name}>
            <Group justify="space-between" align="center" gap="md">
              <div>
                <Text fw={850}>{row.name}</Text>
                <Text c="dimmed" size="sm">
                  {row.fight_count} fights • avg confidence {row.average_confidence_percentage || "N/A"}
                </Text>
              </div>
              <div style={{ textAlign: "right" }}>
                <Text fw={950} c="blue">{row.accuracy_percentage || "N/A"}</Text>
                <Text c="dimmed" size="sm">{row.correct_count} correct / {row.wrong_count} wrong</Text>
              </div>
            </Group>
          </Paper>
        ))}
      </Stack>
    </Card>
  );
}

function CalibrationCard({ rows = [] }) {
  return (
    <Card withBorder radius="xl" shadow="sm" p="xl">
      <Title order={3}>By confidence bucket</Title>
      <Text c="dimmed" size="sm" mt={4}>
        Calibration gap compares actual accuracy against average model confidence. Near 0 is better.
      </Text>

      <Stack gap="sm" mt="md">
        {rows.map((row) => {
          const calibrationColor = getCalibrationClass(row);
          const sampleColor = getSampleSizeClass(row.fight_count);

          return (
            <Paper withBorder radius="lg" p="md" key={row.name}>
              <Group justify="space-between" align="flex-start" gap="md">
                <div>
                  <Text fw={850}>{row.name}</Text>
                  <Text c="dimmed" size="sm">
                    {row.fight_count} fights • avg confidence {row.average_confidence_percentage || "N/A"}
                  </Text>
                </div>

                <Group gap="xs">
                  <Badge color={calibrationColor} variant="light">Gap {formatCalibrationGap(row)}</Badge>
                  <Badge color={sampleColor} variant="light">{getSampleSizeLabel(row.fight_count)}</Badge>
                </Group>
              </Group>

              <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm" mt="md">
                <MetricCard label="Accuracy" value={row.accuracy_percentage || "N/A"} />
                <MetricCard label="Average confidence" value={row.average_confidence_percentage || "N/A"} />
              </SimpleGrid>
            </Paper>
          );
        })}
      </Stack>
    </Card>
  );
}

function SimpleBreakdownCard({ title, rows = [] }) {
  return (
    <Card withBorder radius="xl" shadow="sm" p="xl">
      <Title order={3}>{title}</Title>
      <Stack gap="sm" mt="md">
        {rows.map((row) => {
          const sampleColor = getSampleSizeClass(row.fight_count);
          return (
            <Paper withBorder radius="lg" p="md" key={row.name || "Unknown"}>
              <Group justify="space-between" align="center">
                <div>
                  <Text fw={850}>{row.name || "Unknown"}</Text>
                  <Text c="dimmed" size="sm">{row.fight_count} fights</Text>
                </div>
                <Group gap="xs">
                  <Text fw={950} c="blue">{row.accuracy_percentage || "N/A"}</Text>
                  <Badge color={sampleColor} variant="light">{getSampleSizeLabel(row.fight_count)}</Badge>
                </Group>
              </Group>
            </Paper>
          );
        })}
      </Stack>
    </Card>
  );
}

function PredictionReviewCard({ title, predictions = [], color = "green" }) {
  return (
    <Card withBorder radius="xl" shadow="sm" p="xl">
      <Title order={3}>{title}</Title>
      {predictions.length === 0 ? (
        <Text c="dimmed" mt="md">No predictions in this bucket yet.</Text>
      ) : (
        <Stack gap="sm" mt="md">
          {predictions.map((prediction, index) => (
            <Paper
              withBorder
              radius="lg"
              p="md"
              key={`${title}-${prediction.event_date}-${prediction.fighter_a}-${prediction.fighter_b}-${index}`}
            >
              <Group justify="space-between" align="flex-start" gap="md">
                <div>
                  <Text fw={850}>{prediction.fighter_a} vs {prediction.fighter_b}</Text>
                  <Text c="dimmed" size="sm">{prediction.event_date} • {prediction.weight_class}</Text>
                </div>
                <Badge color={color} variant="light">{prediction.confidence_percentage}</Badge>
              </Group>
              <Text mt="sm" size="sm">
                Predicted <Text span fw={850}>{prediction.predicted_winner}</Text>
              </Text>
            </Paper>
          ))}
        </Stack>
      )}
    </Card>
  );
}

function ModelSnapshotCard({ row, index }) {
  const scoredFights = Number(row.scored_fights ?? row.fight_count ?? 0);
  const savedRows = row.saved_prediction_rows ?? row.saved_rows ?? row.prediction_rows;
  const savedFights = row.saved_unique_fights ?? row.saved_fights;
  const pendingFights = row.pending_fights;
  const hasStats = scoredFights > 0;
  const rankLabel = hasStats ? `#${index + 1}` : "Waiting";

  return (
    <Card withBorder radius="xl" shadow="sm" p="lg" className="prospective-model-card">
      <Group justify="space-between" align="flex-start" gap="md" wrap="nowrap">
        <div>
          <Group gap="xs" align="center">
            <Badge
              color={hasStats ? getAccuracyColor(row.accuracy) : "gray"}
              variant={hasStats ? "filled" : "light"}
              radius="xl"
            >
              {rankLabel}
            </Badge>
            <Badge color={getModelKindColor(row.model_name)} variant="light" radius="xl">
              {getModelKind(row.model_name)}
            </Badge>
            {row.is_current_best_model && (
              <Badge color="blue" variant="light" radius="xl">
                Current app model
              </Badge>
            )}
          </Group>

          <Title order={3} mt="sm">
            {formatModelName(row.model_name)}
          </Title>
          <Text c="dimmed" size="sm" mt={4} lh={1.5}>
            {getModelDescription(row.model_name)}
          </Text>
        </div>
      </Group>

      <SimpleGrid cols={{ base: 2, sm: 3 }} spacing="sm" mt="lg">
        <MetricCard
          label="Accuracy"
          value={row.accuracy_percentage || formatMetricPercent(row.accuracy)}
          icon={<IconTarget size={16} />}
        />
        <MetricCard
          label="Scored"
          value={formatInteger(scoredFights)}
          icon={<IconChartBar size={16} />}
        />
        <MetricCard
          label="Avg confidence"
          value={row.average_confidence_percentage || formatMetricPercent(row.average_confidence)}
          icon={<IconTrendingUp size={16} />}
        />
        <MetricCard
          label="Brier"
          value={formatMetricDecimal(row.brier_score)}
          icon={<IconChartBar size={16} />}
        />
        <MetricCard
          label="Log loss"
          value={formatMetricDecimal(row.log_loss)}
          icon={<IconChartBar size={16} />}
        />
        <MetricCard
          label="Calibration"
          value={row.calibration_gap_percentage_points || formatCalibrationGap(row)}
          icon={<IconTrendingUp size={16} />}
        />
      </SimpleGrid>

      <Group gap="xs" mt="md">
        <Badge color="green" variant="light">
          {formatInteger(row.correct_predictions)} correct
        </Badge>
        <Badge color="red" variant="light">
          {formatInteger(row.wrong_predictions)} wrong
        </Badge>
        <Badge color="gray" variant="light">
          {formatInteger(savedRows)} saved rows
        </Badge>
        {savedFights !== undefined && (
          <Badge color="gray" variant="light">
            {formatInteger(savedFights)} saved fights
          </Badge>
        )}
        {pendingFights !== undefined && pendingFights !== null && (
          <Badge color="yellow" variant="light">
            {formatInteger(pendingFights)} pending
          </Badge>
        )}
      </Group>

      {!hasStats && (
        <Alert color="yellow" variant="light" radius="lg" mt="md">
          This model is being tracked, but none of its saved predictions have completed results yet.
        </Alert>
      )}
    </Card>
  );
}

function ProspectiveModelEvaluationCard({
  evaluation,
  loading = false,
  error = "",
  onReload,
}) {
  const modelRows = sortProspectiveModelRows(getProspectiveModelRows(evaluation));
  const recentRows = getProspectiveRecentRows(evaluation);
  const scoredModelRows = modelRows.filter(hasScoredStats);
  const waitingModelRows = modelRows.filter((row) => !hasScoredStats(row));
  const leadingModel = scoredModelRows[0];

  return (
    <Card withBorder radius="xl" shadow="sm" p="xl">
      <Group justify="space-between" align="flex-start" gap="lg">
        <div>
          <Text size="xs" c="blue" fw={900} tt="uppercase" lts="0.08em">
            Prospective performance
          </Text>
          <Title order={3} mt={4}>All-model prediction snapshots</Title>
          <Text c="dimmed" size="sm" mt={4} maw={850} lh={1.55}>
            Each model gets its own card here. These stats use predictions saved before fights happened, so this is the long-term test for which model actually predicts future cards best.
          </Text>
        </div>

        <Button
          radius="lg"
          variant="light"
          leftSection={<IconRefresh size={17} />}
          onClick={onReload}
          loading={loading}
        >
          Reload snapshots
        </Button>
      </Group>

      {error && <Alert color="red" radius="lg" mt="md">{error}</Alert>}

      {evaluation?.message && (
        <Alert color={modelRows.length ? "blue" : "yellow"} radius="lg" mt="md">
          {evaluation.message}
        </Alert>
      )}

      {evaluation && (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md" mt="lg">
          <MetricCard
            label="Saved rows"
            value={formatInteger(evaluation.prediction_rows)}
            icon={<IconChartBar size={16} />}
          />
          <MetricCard
            label="Scored predictions"
            value={formatInteger(evaluation.scored_fights)}
            icon={<IconTarget size={16} />}
          />
          <MetricCard
            label="Models tracked"
            value={formatInteger(evaluation.model_count ?? modelRows.length)}
            icon={<IconTrendingUp size={16} />}
          />
          <MetricCard
            label="Current leader"
            value={leadingModel ? formatModelName(leadingModel.model_name) : "Waiting"}
            icon={<IconTrendingUp size={16} />}
          />
        </SimpleGrid>
      )}

      {modelRows.length > 0 ? (
        <>
          <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="lg" mt="xl">
            {modelRows.map((row, index) => (
              <ModelSnapshotCard
                key={row.model_name || `model-${index}`}
                row={row}
                index={index}
              />
            ))}
          </SimpleGrid>

          <Stack gap="sm" mt="xl">
            <Group justify="space-between" align="center">
              <Title order={4}>Compact model leaderboard</Title>
              <Group gap="xs">
                {scoredModelRows.length > 0 && (
                  <Badge color="green" variant="light">
                    {scoredModelRows.length} scored
                  </Badge>
                )}
                {waitingModelRows.length > 0 && (
                  <Badge color="yellow" variant="light">
                    {waitingModelRows.length} waiting
                  </Badge>
                )}
              </Group>
            </Group>

            <ScrollArea scrollbarSize={7}>
              <Table striped highlightOnHover withTableBorder verticalSpacing="sm" miw={920}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Model</Table.Th>
                    <Table.Th>Saved</Table.Th>
                    <Table.Th>Scored</Table.Th>
                    <Table.Th>Accuracy</Table.Th>
                    <Table.Th>Brier</Table.Th>
                    <Table.Th>Log loss</Table.Th>
                    <Table.Th>Avg confidence</Table.Th>
                    <Table.Th>Calibration</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {modelRows.map((row) => (
                    <Table.Tr key={row.model_name}>
                      <Table.Td>
                        <Group gap="xs">
                          <Text fw={850}>{formatModelName(row.model_name)}</Text>
                          <Badge color={getModelKindColor(row.model_name)} variant="light">
                            {getModelKind(row.model_name)}
                          </Badge>
                        </Group>
                      </Table.Td>
                      <Table.Td>{formatInteger(row.saved_unique_fights ?? row.saved_prediction_rows)}</Table.Td>
                      <Table.Td>{formatInteger(row.scored_fights ?? row.fight_count)}</Table.Td>
                      <Table.Td>
                        <Badge color={getAccuracyColor(row.accuracy)} variant="light">
                          {row.accuracy_percentage || formatMetricPercent(row.accuracy)}
                        </Badge>
                      </Table.Td>
                      <Table.Td>{formatMetricDecimal(row.brier_score)}</Table.Td>
                      <Table.Td>{formatMetricDecimal(row.log_loss)}</Table.Td>
                      <Table.Td>
                        {row.average_confidence_percentage || formatMetricPercent(row.average_confidence)}
                      </Table.Td>
                      <Table.Td>
                        {row.calibration_gap_percentage_points || formatCalibrationGap(row)}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </ScrollArea>
          </Stack>
        </>
      ) : (
        <Text c="dimmed" mt="lg">
          No all-model snapshots are available yet. Run the incremental update to save future-card model predictions.
        </Text>
      )}

      {recentRows.length > 0 && (
        <Stack gap="sm" mt="xl">
          <Title order={4}>Recent scored snapshot fights</Title>
          {recentRows.slice(0, 8).map((fight, index) => (
            <Paper
              key={`${fight.fight_url || fight.event_name}-${fight.model_name}-${index}`}
              withBorder
              radius="lg"
              p="md"
            >
              <Group justify="space-between" align="flex-start" gap="md">
                <div>
                  <Text fw={850}>
                    {fight.fighter_1} vs {fight.fighter_2}
                  </Text>
                  <Text c="dimmed" size="sm">
                    {fight.event_date} • {fight.weight_class} • {formatModelName(fight.model_name)}
                  </Text>
                </div>
                <Badge color={fight.prediction_correct ? "green" : "red"} variant="light">
                  {fight.prediction_correct ? "Correct" : "Wrong"}
                </Badge>
              </Group>
              <Text size="sm" mt="sm">
                Predicted <Text span fw={850}>{fight.predicted_winner}</Text>; actual winner{" "}
                <Text span fw={850}>{fight.actual_winner}</Text>.
              </Text>
            </Paper>
          ))}
        </Stack>
      )}
    </Card>
  );
}

export default function EvaluationTab({
  modelEvaluation,
  modelEvaluationLoading = false,
  modelEvaluationError = "",
  loadModelEvaluation,
  modelMarketEvaluation,
  modelMarketEvaluationLoading = false,
  modelMarketEvaluationError = "",
  loadModelMarketEvaluation,
  modelSnapshotEvaluation,
  modelSnapshotEvaluationLoading = false,
  modelSnapshotEvaluationError = "",
  loadModelSnapshotEvaluation,
  methodModelMetrics,
  methodModelMetricsError = "",
  evaluationTestFraction,
  setEvaluationTestFraction,
  evaluationRecentLimit,
  setEvaluationRecentLimit,
}) {
  return (
    <Stack gap="lg" className="mantine-evaluation-page">
      <Card withBorder radius="xl" shadow="sm" p="xl">
        <Group justify="space-between" align="flex-start" gap="lg">
          <div>
            <Text size="xs" c="blue" fw={900} tt="uppercase" lts="0.08em">
              Model performance
            </Text>
            <Title order={2} mt={4}>Model evaluation</Title>
            <Text c="dimmed" size="sm" mt="xs" maw={780} lh={1.55}>
              Evaluate the currently saved model against a chronological holdout set. This helps show where the model is strong, weak, and whether confidence is calibrated.
            </Text>
          </div>

          <Button
            radius="lg"
            leftSection={<IconRefresh size={17} />}
            onClick={loadModelEvaluation}
            loading={modelEvaluationLoading}
          >
            Load evaluation
          </Button>
        </Group>

        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md" mt="xl">
          <NumberInput
            label="Test fraction"
            min={0.05}
            max={0.5}
            step={0.05}
            value={evaluationTestFraction}
            onChange={(value) => setEvaluationTestFraction(Number(value) || 0.2)}
            radius="lg"
          />
          <NumberInput
            label="Recent prediction limit"
            min={5}
            max={100}
            value={evaluationRecentLimit}
            onChange={(value) => setEvaluationRecentLimit(Number(value) || 25)}
            radius="lg"
          />
        </SimpleGrid>

        {modelEvaluationError && <Alert color="red" radius="lg" mt="md">{modelEvaluationError}</Alert>}
      </Card>

      {modelEvaluation?.overall && (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 5 }} spacing="md">
          <MetricCard label="Accuracy" value={modelEvaluation.overall.accuracy_percentage || "N/A"} icon={<IconTarget size={16} />} />
          <MetricCard label="Avg confidence" value={modelEvaluation.overall.average_confidence_percentage || "N/A"} icon={<IconTrendingUp size={16} />} />
          <MetricCard label="Brier score" value={modelEvaluation.overall.brier_score !== null ? Number(modelEvaluation.overall.brier_score).toFixed(4) : "N/A"} icon={<IconChartBar size={16} />} />
          <MetricCard label="Log loss" value={modelEvaluation.overall.log_loss !== null ? Number(modelEvaluation.overall.log_loss).toFixed(4) : "N/A"} icon={<IconChartBar size={16} />} />
          <MetricCard label="ROC AUC" value={modelEvaluation.overall.roc_auc !== null ? Number(modelEvaluation.overall.roc_auc).toFixed(4) : "N/A"} icon={<IconChartBar size={16} />} />
        </SimpleGrid>
      )}

      <ModelVsMarketEvaluationPanel
        evaluation={modelMarketEvaluation}
        loading={modelMarketEvaluationLoading}
        error={modelMarketEvaluationError}
        onReload={loadModelMarketEvaluation}
      />

      <ProspectiveModelEvaluationCard
        evaluation={modelSnapshotEvaluation}
        loading={modelSnapshotEvaluationLoading}
        error={modelSnapshotEvaluationError}
        onReload={loadModelSnapshotEvaluation}
      />

      {methodModelMetricsError && <Alert color="red" radius="lg">{methodModelMetricsError}</Alert>}

      {methodModelMetrics?.available && methodModelMetrics.metrics && (
        <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
          <MethodMetricCard
            title="Broad method model"
            note="Predicts Decision vs KO/TKO vs Submission vs Other."
            metrics={methodModelMetrics.metrics.broad}
          />
          <MethodMetricCard
            title="Detailed method model"
            note="Predicts detailed method flavor. Treat this as directional, not exact."
            metrics={methodModelMetrics.metrics.detailed}
          />
        </SimpleGrid>
      )}

      {modelEvaluation && (
        <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="lg">
          <ThresholdCard rows={modelEvaluation.by_favorite_threshold ?? []} />
          <CalibrationCard rows={modelEvaluation.by_confidence_bucket ?? []} />
          <SimpleBreakdownCard title="By weight class" rows={modelEvaluation.by_weight_class ?? []} />
          <SimpleBreakdownCard title="By year" rows={modelEvaluation.by_year ?? []} />
        </SimpleGrid>
      )}

      {modelEvaluation && (
        <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="lg">
          <PredictionReviewCard
            title="Most confident correct picks"
            predictions={modelEvaluation.most_confident_correct ?? []}
            color="green"
          />
          <PredictionReviewCard
            title="Most confident wrong picks"
            predictions={modelEvaluation.most_confident_wrong ?? []}
            color="red"
          />
        </SimpleGrid>
      )}
    </Stack>
  );
}
