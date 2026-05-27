import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Group,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import {
  IconAlertCircle,
  IconArrowsExchange,
  IconEraser,
  IconSparkles,
  IconSwords,
} from "@tabler/icons-react";
import PredictionDetails from "./PredictionDetails";
import MethodPredictionDetails from "./MethodPredictionDetails";

function FighterSuggestions({ results = [], onSelect }) {
  if (!results.length) {
    return null;
  }

  return (
    <div className="mantine-suggestions">
      {results.map((name) => (
        <button
          type="button"
          key={name}
          onClick={() => onSelect(name)}
        >
          {name}
        </button>
      ))}
    </div>
  );
}

export default function SingleFightTab({
  fighterA,
  setFighterA,
  fighterB,
  setFighterB,
  weightClass,
  setWeightClass,
  weightClasses = [],
  fighterASearchResults = [],
  setFighterASearchResults,
  fighterBSearchResults = [],
  setFighterBSearchResults,
  searchFighters,
  handlePredict,
  loading = false,
  error = "",
  singlePrediction,
  showSingleFightEdges = true,
  setShowSingleFightEdges,
  fighterImageLookup = {},
  singleMethodPrediction,
  methodPredictionLoading = false,
  methodPredictionError = "",
  loadExampleFight,
  swapSingleFightFighters,
  clearSingleFightForm,
}) {
  return (
    <SimpleGrid
      cols={{ base: 1, lg: 2 }}
      spacing="xl"
      className="single-fight-command-grid"
    >
      <Paper
        component="form"
        onSubmit={handlePredict}
        withBorder
        radius="xl"
        p="xl"
        shadow="sm"
        className="mantine-command-card mantine-single-form"
      >
        <Stack gap="lg">
          <Group justify="space-between" align="flex-start" gap="md">
            <div>
              <Badge variant="light" leftSection={<IconSwords size={13} />}>
                Single matchup
              </Badge>
              <Title order={2} mt="sm">
                Build a fight prediction
              </Title>
              <Text c="dimmed" size="sm" mt={6} maw={440}>
                Enter two fighters and a weight class to generate win probabilities,
                model reasoning, method probabilities, and matchup edges.
              </Text>
            </div>
          </Group>

          <Group gap="xs" wrap="wrap">
            <Button
              type="button"
              variant="light"
              size="xs"
              leftSection={<IconSparkles size={14} />}
              onClick={() =>
                loadExampleFight("Khamzat Chimaev", "Sean Strickland", "Middleweight")
              }
            >
              Khamzat vs Strickland
            </Button>

            <Button
              type="button"
              variant="light"
              size="xs"
              leftSection={<IconSparkles size={14} />}
              onClick={() =>
                loadExampleFight("Islam Makhachev", "Max Holloway", "Lightweight")
              }
            >
              Islam vs Holloway
            </Button>
          </Group>

          <Stack gap="sm">
            <div>
              <TextInput
                label="Fighter A"
                placeholder="Example: Khamzat Chimaev"
                value={fighterA}
                onChange={(event) => {
                  setFighterA(event.currentTarget.value);
                  searchFighters(event.currentTarget.value, setFighterASearchResults);
                }}
                radius="md"
              />
              <FighterSuggestions
                results={fighterASearchResults}
                onSelect={(name) => {
                  setFighterA(name);
                  setFighterASearchResults([]);
                }}
              />
            </div>

            <div>
              <TextInput
                label="Fighter B"
                placeholder="Example: Sean Strickland"
                value={fighterB}
                onChange={(event) => {
                  setFighterB(event.currentTarget.value);
                  searchFighters(event.currentTarget.value, setFighterBSearchResults);
                }}
                radius="md"
              />
              <FighterSuggestions
                results={fighterBSearchResults}
                onSelect={(name) => {
                  setFighterB(name);
                  setFighterBSearchResults([]);
                }}
              />
            </div>

            <Select
              label="Weight class"
              value={weightClass}
              onChange={(value) => setWeightClass(value || "")}
              data={weightClasses}
              radius="md"
              searchable
              nothingFoundMessage="No weight class found"
            />
          </Stack>

          <Group grow align="stretch">
            <Button
              type="submit"
              loading={loading}
              leftSection={<IconSwords size={18} />}
              size="md"
              radius="md"
            >
              Predict fight
            </Button>

            <Button
              type="button"
              variant="default"
              onClick={swapSingleFightFighters}
              disabled={!fighterA && !fighterB}
              leftSection={<IconArrowsExchange size={18} />}
              radius="md"
            >
              Swap
            </Button>

            <Button
              type="button"
              variant="subtle"
              color="gray"
              onClick={clearSingleFightForm}
              leftSection={<IconEraser size={18} />}
              radius="md"
            >
              Clear
            </Button>
          </Group>

          <Checkbox
            checked={showSingleFightEdges}
            onChange={(event) => setShowSingleFightEdges(event.currentTarget.checked)}
            label="Show basic matchup edges"
          />

          {error && (
            <Alert
              color="red"
              variant="light"
              radius="md"
              icon={<IconAlertCircle size={18} />}
              title="Prediction failed"
            >
              <Text component="pre" className="mantine-error-pre">
                {error}
              </Text>
            </Alert>
          )}
        </Stack>
      </Paper>

      <Stack gap="lg" className="single-fight-results-stack">
        <PredictionDetails
          prediction={singlePrediction}
          showBasicEdges={showSingleFightEdges}
          fighterImageLookup={fighterImageLookup}
        />

        <MethodPredictionDetails
          methodPrediction={singleMethodPrediction}
          loading={methodPredictionLoading}
          error={methodPredictionError}
        />
      </Stack>
    </SimpleGrid>
  );
}
