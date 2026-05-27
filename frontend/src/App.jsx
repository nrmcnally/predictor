import { useEffect, useMemo, useState } from "react";
import {
  ActionIcon,
  AppShell,
  Badge,
  Box,
  Burger,
  Divider,
  Group,
  NavLink,
  Paper,
  ScrollArea,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
  useComputedColorScheme,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconActivity,
  IconCalendarStats,
  IconChartBar,
  IconDatabase,
  IconHistory,
  IconMoon,
  IconRefresh,
  IconSwords,
  IconSun,
  IconTrophy,
  IconUserSearch,
} from "@tabler/icons-react";
import "./App.css";
import { normalizeFighterName } from "./components/FighterDisplay";
import FighterProfileTab from "./components/FighterProfileTab";
import SingleFightTab from "./components/SingleFightTab";
import FutureCardsTab from "./components/FutureCardsTab";
import RecentCardsTab from "./components/RecentCardsTab";
import LeaderboardsTab from "./components/LeaderboardsTab";
import EvaluationTab from "./components/EvaluationTab";
import UpdateDataTab from "./components/UpdateDataTab";

const API_BASE_URL = "http://127.0.0.1:8000";

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

function formatAmericanOdds(value) {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  const numberValue = Number(value);

  if (!Number.isFinite(numberValue)) {
    return String(value);
  }

  return numberValue > 0 ? `+${numberValue}` : `${numberValue}`;
}

function normalizeFightUrl(value) {
  return String(value || "")
    .replace("https://www.", "https://")
    .replace("http://www.", "http://")
    .replace(/\/$/, "");
}

function getOddsForFight(oddsRows, fightUrl) {
  if (!Array.isArray(oddsRows) || !fightUrl) {
    return null;
  }

  const normalizedFightUrl = normalizeFightUrl(fightUrl);

  return (
    oddsRows.find((row) => normalizeFightUrl(row.fight_url) === normalizedFightUrl) ||
    null
  );
}


function getCalibrationClass(row) {
  if (
    row?.accuracy === null ||
    row?.accuracy === undefined ||
    row?.average_confidence === null ||
    row?.average_confidence === undefined
  ) {
    return "unknown";
  }

  const gap = Math.abs(Number(row.accuracy) - Number(row.average_confidence));

  if (!Number.isFinite(gap)) {
    return "unknown";
  }

  if (gap <= 0.05) {
    return "good";
  }

  if (gap <= 0.10) {
    return "warning";
  }

  return "bad";
}

function getSampleSizeClass(fightCount) {
  const count = Number(fightCount);

  if (!Number.isFinite(count)) {
    return "unknown";
  }

  if (count < 20) {
    return "low";
  }

  if (count < 50) {
    return "medium";
  }

  return "good";
}

function getSampleSizeLabel(fightCount) {
  const sampleClass = getSampleSizeClass(fightCount);

  if (sampleClass === "low") {
    return "Low sample";
  }

  if (sampleClass === "medium") {
    return "Moderate sample";
  }

  if (sampleClass === "good") {
    return "Good sample";
  }

  return "Unknown sample";
}

function formatModelName(modelName = "") {
  const names = {
    calibrated_logistic_regression: "Calibrated Logistic",
    calibrated_random_forest: "Calibrated Random Forest",
    calibrated_xgboost: "Calibrated XGBoost",
    logistic_regression: "Logistic Regression",
    random_forest: "Random Forest",
    xgboost: "XGBoost",
  };

  return names[modelName] ?? modelName.replaceAll("_", " ");
}

function getProbabilityWidth(probability) {
  if (!Number.isFinite(probability)) {
    return "0%";
  }

  return `${Math.max(0, Math.min(100, probability * 100))}%`;
}

function getConfidenceClass(label = "") {
  const lowerLabel = String(label).toLowerCase();

  if (lowerLabel.includes("high")) {
    return "high";
  }

  if (lowerLabel.includes("strong")) {
    return "strong";
  }

  if (lowerLabel.includes("moderate")) {
    return "moderate";
  }

  if (lowerLabel.includes("slight") || lowerLabel.includes("very close")) {
    return "close";
  }

  return "unknown";
}

function summarizeFutureCard(card) {
  const fights = card?.fights ?? [];

  const predictionAvailableFights = fights.filter(
    (fight) => fight.prediction_available && fight.prediction
  );

  const predictionUnavailableFights = fights.filter(
    (fight) => !fight.prediction_available || !fight.prediction
  );

  const highConfidenceFights = predictionAvailableFights.filter((fight) => {
    const confidenceClass = getConfidenceClass(fight.prediction.confidence_label);
    return confidenceClass === "high" || confidenceClass === "strong";
  });

  const moderateConfidenceFights = predictionAvailableFights.filter((fight) => {
    const confidenceClass = getConfidenceClass(fight.prediction.confidence_label);
    return confidenceClass === "moderate";
  });

  const closeFights = predictionAvailableFights.filter((fight) => {
    const confidenceClass = getConfidenceClass(fight.prediction.confidence_label);
    return confidenceClass === "close";
  });

  return {
    totalFights: fights.length,
    predictionAvailableCount: predictionAvailableFights.length,
    predictionUnavailableCount: predictionUnavailableFights.length,
    highConfidenceCount: highConfidenceFights.length,
    moderateConfidenceCount: moderateConfidenceFights.length,
    closeFightCount: closeFights.length,
  };
}

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

function summarizeRecentCard(card) {
  const fights = card?.fights ?? [];

  const actualResultCount = fights.filter((fight) => fight.actual_result_available).length;

  const predictedCompletedFights = fights.filter(
    (fight) => fight.actual_result_available && fight.prediction_available
  );

  const correctCount = predictedCompletedFights.filter(
    (fight) => fight.prediction_correct
  ).length;

  const wrongCount = predictedCompletedFights.filter(
    (fight) => fight.prediction_correct === false
  ).length;

  const waitingCount = fights.filter((fight) => !fight.actual_result_available).length;

  const marketCompletedFights = fights.filter(
    (fight) =>
      fight.actual_result_available &&
      fight.odds_available &&
      fight.market_correct !== null &&
      fight.market_correct !== undefined
  );

  const marketCorrectCount = marketCompletedFights.filter(
    (fight) => fight.market_correct === true
  ).length;

  const accuracy =
    predictedCompletedFights.length > 0
      ? correctCount / predictedCompletedFights.length
      : null;

  const marketAccuracy =
    marketCompletedFights.length > 0
      ? marketCorrectCount / marketCompletedFights.length
      : null;

  return {
    totalFights: fights.length,
    actualResultCount,
    predictedCompletedCount: predictedCompletedFights.length,
    correctCount,
    wrongCount,
    waitingCount,
    accuracy,
    accuracyPercentage: accuracy !== null ? `${(accuracy * 100).toFixed(1)}%` : "N/A",
    marketCompletedCount: marketCompletedFights.length,
    marketCorrectCount,
    marketAccuracy,
    marketAccuracyPercentage:
      marketAccuracy !== null ? `${(marketAccuracy * 100).toFixed(1)}%` : "N/A",
  };
}

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

  if (
    key.includes("rate") ||
    key.includes("accuracy") ||
    key.includes("defense")
  ) {
    return `${(numberValue * 100).toFixed(1)}%`;
  }

  if (key.includes("height") || key.includes("reach")) {
    return `${numberValue.toFixed(1)} in`;
  }

  return numberValue.toFixed(2);
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

function buildStageLookup(report) {
  const lookup = {};

  for (const stage of report?.stages ?? []) {
    lookup[stage.name] = stage;
  }

  return lookup;
}

function getStageDetails(stageLookup, stageName) {
  return stageLookup?.[stageName]?.details ?? {};
}

function parsePercentageText(value) {
  if (!value) {
    return null;
  }

  const parsed = Number(String(value).replace("%", ""));

  if (!Number.isFinite(parsed)) {
    return null;
  }

  return parsed / 100;
}

function App() {
  const [activeView, setActiveView] = useState("single");
  const [mobileOpened, { toggle: toggleMobile, close: closeMobile }] =
    useDisclosure(false);
  const [desktopOpened, { toggle: toggleDesktop }] = useDisclosure(true);
  const { setColorScheme } = useMantineColorScheme();
  const computedColorScheme = useComputedColorScheme("light", {
    getInitialValueInEffect: true,
  });

  const isDarkMode = computedColorScheme === "dark";

  const [showDashboardDetails, setShowDashboardDetails] = useState(false);

  const [leaderboardOptions, setLeaderboardOptions] = useState(null);
  const [leaderboards, setLeaderboards] = useState(null);

  const [leaderboardScope, setLeaderboardScope] = useState("overall");
  const [leaderboardWeightClass, setLeaderboardWeightClass] = useState("Lightweight");
  const [leaderboardCategory, setLeaderboardCategory] = useState("overall");
  const [leaderboardDirection, setLeaderboardDirection] = useState("best");
  const [leaderboardTop, setLeaderboardTop] = useState(5);
  const [leaderboardMinFights, setLeaderboardMinFights] = useState(5);
  const [leaderboardMaxInactiveDays, setLeaderboardMaxInactiveDays] = useState(1095);

  const [leaderboardsLoading, setLeaderboardsLoading] = useState(false);
  const [leaderboardsError, setLeaderboardsError] = useState("");

  const [modelEvaluation, setModelEvaluation] = useState(null);
  const [modelEvaluationLoading, setModelEvaluationLoading] = useState(false);
  const [modelEvaluationError, setModelEvaluationError] = useState("");

  const [modelMarketEvaluation, setModelMarketEvaluation] = useState(null);
  const [modelMarketEvaluationLoading, setModelMarketEvaluationLoading] = useState(false);
  const [modelMarketEvaluationError, setModelMarketEvaluationError] = useState("");

  const [evaluationTestFraction, setEvaluationTestFraction] = useState(0.2);
  const [evaluationRecentLimit, setEvaluationRecentLimit] = useState(25);

  const [fighterA, setFighterA] = useState("Khamzat Chimaev");
  const [fighterB, setFighterB] = useState("Sean Strickland");
  const [weightClass, setWeightClass] = useState("Middleweight");

  const [weightClasses, setWeightClasses] = useState([]);
  const [singlePrediction, setSinglePrediction] = useState(null);
  const [showSingleFightEdges, setShowSingleFightEdges] = useState(true);

  const [fighterASearchResults, setFighterASearchResults] = useState([]);
  const [fighterBSearchResults, setFighterBSearchResults] = useState([]);

  const [futureCards, setFutureCards] = useState([]);
  const [selectedCardId, setSelectedCardId] = useState("");
  const [selectedCard, setSelectedCard] = useState(null);
  const [selectedFightPrediction, setSelectedFightPrediction] = useState(null);

  const [recentCards, setRecentCards] = useState([]);
  const [selectedRecentCardId, setSelectedRecentCardId] = useState("");
  const [selectedRecentCard, setSelectedRecentCard] = useState(null);
  const [selectedRecentFight, setSelectedRecentFight] = useState(null);

  const [updateStatus, setUpdateStatus] = useState(null);
  const [latestReport, setLatestReport] = useState(null);

  const [loading, setLoading] = useState(false);
  const [cardsLoading, setCardsLoading] = useState(false);
  const [cardPredictionsLoading, setCardPredictionsLoading] = useState(false);
  const [recentLoading, setRecentLoading] = useState(false);
  const [updateLoading, setUpdateLoading] = useState(false);

  const [error, setError] = useState("");
  const [cardsError, setCardsError] = useState("");
  const [recentError, setRecentError] = useState("");
  const [updateError, setUpdateError] = useState("");

  const [singleMethodPrediction, setSingleMethodPrediction] = useState(null);
  const [methodPredictionLoading, setMethodPredictionLoading] = useState(false);
  const [methodPredictionError, setMethodPredictionError] = useState("");

  const [methodModelMetrics, setMethodModelMetrics] = useState(null);
  const [methodModelMetricsError, setMethodModelMetricsError] = useState("");

  const [futureFightOdds, setFutureFightOdds] = useState([]);
  const [futureFightOddsError, setFutureFightOddsError] = useState("");

  const [fighterImageLookup, setFighterImageLookup] = useState({});
  const [fighterImagesError, setFighterImagesError] = useState("");

  const [profileFighter, setProfileFighter] = useState("Khamzat Chimaev");
  const [profileSearchResults, setProfileSearchResults] = useState([]);
  const [fighterProfile, setFighterProfile] = useState(null);
  const [fighterProfileLoading, setFighterProfileLoading] = useState(false);
  const [fighterProfileError, setFighterProfileError] = useState("");

  useEffect(() => {
    document.documentElement.dataset.theme = computedColorScheme;
    document.documentElement.style.colorScheme = computedColorScheme;
  }, [computedColorScheme]);

  useEffect(() => {
    async function loadWeightClasses() {
      try {
        const response = await fetch(`${API_BASE_URL}/weight-classes`);

        if (!response.ok) {
          throw new Error("Failed to load weight classes.");
        }

        const data = await response.json();
        setWeightClasses(data.weight_classes ?? []);
      } catch (requestError) {
        console.error(requestError);
        setWeightClasses([
          "Flyweight",
          "Bantamweight",
          "Featherweight",
          "Lightweight",
          "Welterweight",
          "Middleweight",
          "Light Heavyweight",
          "Heavyweight",
        ]);
      }
    }

    loadWeightClasses();
    loadFutureCards();
    loadRecentCards();
    loadUpdateStatus();
    loadLatestReport();
    loadLeaderboardOptions();
    loadLeaderboards();
    loadModelEvaluation();
    loadModelMarketEvaluation();
    loadMethodModelMetrics();
    loadFutureFightOdds();
    loadFighterImages();
    loadFighterProfile("Khamzat Chimaev");
  }, []);

  useEffect(() => {
    if (activeView !== "update") {
      return;
    }

    const intervalId = window.setInterval(() => {
      loadUpdateStatus();
    }, 3000);

    return () => window.clearInterval(intervalId);
  }, [activeView]);

  useEffect(() => {
    if (!updateStatus?.running) {
      return;
    }

    const intervalId = window.setInterval(() => {
      loadUpdateStatus();
    }, 3000);

    return () => window.clearInterval(intervalId);
  }, [updateStatus?.running]);

  useEffect(() => {
    if (activeView === "cards" && selectedCardId) {
      loadCardPredictions(selectedCardId);
    }
  }, [activeView, selectedCardId]);

  useEffect(() => {
    if (activeView === "recent" && selectedRecentCardId) {
      loadRecentCardDetail(selectedRecentCardId);
    }
  }, [activeView, selectedRecentCardId]);

  async function searchFighters(query, setResults) {
    if (!query.trim()) {
      setResults([]);
      return;
    }

    try {
      const params = new URLSearchParams({
        query,
        limit: "8",
      });

      const response = await fetch(`${API_BASE_URL}/fighters/search?${params}`);

      if (!response.ok) {
        throw new Error("Fighter search failed.");
      }

      const data = await response.json();
      setResults(data.fighters ?? []);
    } catch (requestError) {
      console.error(requestError);
      setResults([]);
    }
  }

async function loadMethodModelMetrics() {
  setMethodModelMetricsError("");

  try {
    const response = await fetch(`${API_BASE_URL}/method-model-metrics`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail?.message ||
          data?.detail?.error ||
          "Failed to load method model metrics."
      );
    }

    setMethodModelMetrics(data);
  } catch (requestError) {
    setMethodModelMetricsError(requestError.message);
  }
}

async function loadFutureFightOdds() {
  setFutureFightOddsError("");

  try {
    const response = await fetch(`${API_BASE_URL}/future-fight-odds`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail?.message ||
          data?.detail?.error ||
          "Failed to load future fight odds."
      );
    }

    setFutureFightOdds(data.odds || []);
  } catch (requestError) {
    setFutureFightOddsError(requestError.message);
  }
}

async function loadFighterImages() {
  setFighterImagesError("");

  try {
    const response = await fetch(`${API_BASE_URL}/fighter-images`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail?.message ||
          data?.detail?.error ||
          "Failed to load fighter images."
      );
    }

    const lookup = {};

    for (const imageData of data.images || []) {
      const fighter = imageData.fighter || imageData.name;

      if (!fighter) {
        continue;
      }

      lookup[normalizeFighterName(fighter)] = imageData;
    }

    setFighterImageLookup(lookup);
  } catch (requestError) {
    setFighterImagesError(requestError.message);
    setFighterImageLookup({});
  }
}


async function loadFighterProfile(fighterName = profileFighter) {
  const cleanedName = String(fighterName || "").trim();

  if (!cleanedName) {
    return;
  }

  setFighterProfileLoading(true);
  setFighterProfileError("");

  try {
    const params = new URLSearchParams({
      fighter: cleanedName,
    });

    const response = await fetch(`${API_BASE_URL}/fighter-profile?${params}`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail?.message ||
          data?.detail?.error ||
          "Failed to load fighter profile."
      );
    }

    setFighterProfile(data);
    setProfileFighter(data.fighter || cleanedName);
  } catch (requestError) {
    setFighterProfileError(requestError.message);
  } finally {
    setFighterProfileLoading(false);
  }
}




function openFighterProfile(fighterName) {
  const cleanedName = String(fighterName || "").trim();

  if (!cleanedName) {
    return;
  }

  setProfileFighter(cleanedName);
  setProfileSearchResults([]);
  setActiveView("profile");
  loadFighterProfile(cleanedName);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function loadMethodPrediction(nextFighterA, nextFighterB, nextWeightClass) {
  setMethodPredictionLoading(true);
  setMethodPredictionError("");
  setSingleMethodPrediction(null);

  try {
    const response = await fetch(`${API_BASE_URL}/predict-method`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        fighter_a: nextFighterA,
        fighter_b: nextFighterB,
        weight_class: nextWeightClass,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail?.message ||
          data?.detail?.error ||
          "Failed to predict method of ending."
      );
    }

    setSingleMethodPrediction(data);
  } catch (requestError) {
    setMethodPredictionError(requestError.message);
  } finally {
    setMethodPredictionLoading(false);
  }
}

  async function handlePredict(event) {
    event.preventDefault();

    setLoading(true);
    setError("");
    setSinglePrediction(null);
    setSingleMethodPrediction(null);
    setMethodPredictionError("");

    try {
      const response = await fetch(`${API_BASE_URL}/predict`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          fighter_a: fighterA,
          fighter_b: fighterB,
          weight_class: weightClass,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        if (data.detail?.suggestions?.length) {
          throw new Error(
            `${data.detail.message}\nSuggestions: ${data.detail.suggestions.join(", ")}`
          );
        }

        throw new Error(data.detail?.message ?? "Prediction failed.");
      }

      setSinglePrediction(data);
      await loadMethodPrediction(data.fighter_a, data.fighter_b, data.weight_class);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadModelEvaluation() {
  setModelEvaluationLoading(true);
  setModelEvaluationError("");

  try {
    const params = new URLSearchParams({
      test_fraction: String(evaluationTestFraction),
      recent_prediction_limit: String(evaluationRecentLimit),
    });

    const response = await fetch(`${API_BASE_URL}/model-evaluation?${params}`);

    if (!response.ok) {
      throw new Error("Failed to load model evaluation.");
    }

    const data = await response.json();
    setModelEvaluation(data);
  } catch (requestError) {
    setModelEvaluationError(requestError.message);
  } finally {
    setModelEvaluationLoading(false);
  }
}

async function loadModelMarketEvaluation() {
  setModelMarketEvaluationLoading(true);
  setModelMarketEvaluationError("");

  try {
    const response = await fetch(`${API_BASE_URL}/model-vs-market-evaluation`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail?.message ||
          data?.detail?.error ||
          "Failed to load model-vs-market evaluation."
      );
    }

    setModelMarketEvaluation(data);
  } catch (requestError) {
    setModelMarketEvaluationError(requestError.message);
  } finally {
    setModelMarketEvaluationLoading(false);
  }
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

  function swapSingleFightFighters() {
  setFighterA(fighterB);
  setFighterB(fighterA);
  setFighterASearchResults([]);
  setFighterBSearchResults([]);
  setSinglePrediction(null);
  setError("");
  setSingleMethodPrediction(null);
  setMethodPredictionError("");
}

function clearSingleFightForm() {
  setFighterA("");
  setFighterB("");
  setWeightClass("Middleweight");
  setFighterASearchResults([]);
  setFighterBSearchResults([]);
  setSinglePrediction(null);
  setError("");
  setSingleMethodPrediction(null);
  setMethodPredictionError("");
}

function loadExampleFight(exampleFighterA, exampleFighterB, exampleWeightClass) {
  setFighterA(exampleFighterA);
  setFighterB(exampleFighterB);
  setWeightClass(exampleWeightClass);
  setFighterASearchResults([]);
  setFighterBSearchResults([]);
  setSinglePrediction(null);
  setSingleMethodPrediction(null);
  setMethodPredictionError("");
  setError("");
  setSingleMethodPrediction(null);
  setMethodPredictionError("");
}

  async function loadFutureCards() {
    setCardsLoading(true);
    setCardsError("");

    try {
      const response = await fetch(`${API_BASE_URL}/future-cards`);

      if (!response.ok) {
        throw new Error("Failed to load future cards.");
      }

      const data = await response.json();
      const cards = data.cards ?? [];

      setFutureCards(cards);

      if (cards.length > 0 && !selectedCardId) {
        setSelectedCardId(cards[0].event_id);
      }
    } catch (requestError) {
      setCardsError(requestError.message);
    } finally {
      setCardsLoading(false);
    }
  }

  async function loadLeaderboardOptions() {
  try {
    const response = await fetch(`${API_BASE_URL}/leaderboards/options`);

    if (!response.ok) {
      throw new Error("Failed to load leaderboard options.");
    }

    const data = await response.json();
    setLeaderboardOptions(data);

    if (data.weight_classes?.length && !leaderboardWeightClass) {
      setLeaderboardWeightClass(data.weight_classes[0]);
    }
  } catch (requestError) {
    console.error(requestError);
  }
}

async function loadLeaderboards() {
  setLeaderboardsLoading(true);
  setLeaderboardsError("");

  try {
    const params = new URLSearchParams({
      top: String(leaderboardTop),
      min_fights: String(leaderboardMinFights),
      max_inactive_days: String(leaderboardMaxInactiveDays),
    });

    const response = await fetch(`${API_BASE_URL}/leaderboards?${params}`);

    if (!response.ok) {
      throw new Error("Failed to load leaderboards.");
    }

    const data = await response.json();
    setLeaderboards(data);
  } catch (requestError) {
    setLeaderboardsError(requestError.message);
  } finally {
    setLeaderboardsLoading(false);
  }
}

  async function refreshFutureCards() {
    setCardsLoading(true);
    setCardsError("");

    try {
      const response = await fetch(`${API_BASE_URL}/future-cards/refresh`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error("Failed to refresh future cards.");
      }

      await loadFutureCards();
      await loadFutureFightOdds();
    } catch (requestError) {
      setCardsError(requestError.message);
    } finally {
      setCardsLoading(false);
    }
  }

  async function loadCardPredictions(eventId) {
    if (!eventId) {
      return;
    }

    setCardPredictionsLoading(true);
    setCardsError("");
    setSelectedCard(null);
    setSelectedFightPrediction(null);

    try {
      const response = await fetch(`${API_BASE_URL}/future-cards/${eventId}/predictions`);

      if (!response.ok) {
        throw new Error("Failed to load card predictions.");
      }

      const data = await response.json();

      setSelectedCard(data);

      const firstAvailablePrediction = data.fights?.find(
        (fight) => fight.prediction_available && fight.prediction
      );

      if (firstAvailablePrediction) {
        setSelectedFightPrediction(firstAvailablePrediction.prediction);
      }
    } catch (requestError) {
      setCardsError(requestError.message);
    } finally {
      setCardPredictionsLoading(false);
    }
  }

  async function loadRecentCards() {
    setRecentLoading(true);
    setRecentError("");

    try {
      const response = await fetch(`${API_BASE_URL}/recent-cards?include_waiting=true`);

      if (!response.ok) {
        throw new Error("Failed to load recent cards.");
      }

      const data = await response.json();

      const cards = [...(data.cards ?? [])].sort((a, b) => {
        const dateA = new Date(a.event_date);
        const dateB = new Date(b.event_date);

        return dateA - dateB;
      });

      setRecentCards(cards);

      if (cards.length > 0 && !selectedRecentCardId) {
        setSelectedRecentCardId(cards[0].event_id);
      }
    } catch (requestError) {
      setRecentError(requestError.message);
    } finally {
      setRecentLoading(false);
    }
  }

  async function loadRecentCardDetail(eventId) {
    if (!eventId) {
      return;
    }

    setRecentLoading(true);
    setRecentError("");
    setSelectedRecentCard(null);
    setSelectedRecentFight(null);

    try {
      const response = await fetch(`${API_BASE_URL}/recent-cards/${eventId}`);

      if (!response.ok) {
        throw new Error("Failed to load recent card details.");
      }

      const data = await response.json();

      setSelectedRecentCard(data);

      if (data.fights?.length > 0) {
        setSelectedRecentFight(data.fights[0]);
      }
    } catch (requestError) {
      setRecentError(requestError.message);
    } finally {
      setRecentLoading(false);
    }
  }

  async function loadUpdateStatus() {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/update/status`);

      if (!response.ok) {
        throw new Error("Failed to load update status.");
      }

      const data = await response.json();
      setUpdateStatus(data);

      if (!data.running) {
        loadLatestReport();
        loadFighterImages();
      }
    } catch (requestError) {
      setUpdateError(requestError.message);
    }
  }

  async function loadLatestReport() {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/update/latest-report`);

      if (!response.ok) {
        throw new Error("Failed to load latest update report.");
      }

      const data = await response.json();
      setLatestReport(data);
    } catch (requestError) {
      setUpdateError(requestError.message);
    }
  }

  async function startIncrementalUpdate() {
    const confirmed = window.confirm(
      "This will run an incremental data/model update.\n\n" +
        "It refreshes completed events, scrapes only missing fight details, rebuilds features, retrains the model, refreshes future cards, and saves future-card predictions.\n\n" +
        "Most updates should be much faster than a full rebuild, but it can still take several minutes if new fights are available.\n\n" +
        "Keep the backend running while this completes.\n\n" +
        "Continue?"
    );

    if (!confirmed) {
      return;
    }

    setUpdateLoading(true);
    setUpdateError("");

    try {
      const response = await fetch(`${API_BASE_URL}/admin/update/start`, {
        method: "POST",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail?.message ?? "Failed to start update.");
      }

      setUpdateStatus(data.status);
    } catch (requestError) {
      setUpdateError(requestError.message);
    } finally {
      setUpdateLoading(false);
    }
  }

  const latestReportObject = latestReport?.report;
  const latestReportSummary = latestReportObject?.summary;
  const latestReportStartedAt = latestReportObject?.started_at;
  const latestReportFinishedAt = latestReportObject?.finished_at;
  const latestReportDuration = latestReportObject?.duration_seconds;

  const latestStageLookup = useMemo(
    () => buildStageLookup(latestReportObject),
    [latestReportObject]
  );

  const fightStatsUpdateDetails = getStageDetails(
    latestStageLookup,
    "Update fight stats incrementally"
  );

  const trainModelDetails = getStageDetails(
    latestStageLookup,
    "Train calibrated model"
  );

  const refreshFutureCardsDetails = getStageDetails(
    latestStageLookup,
    "Refresh future cards"
  );

  const saveFuturePredictionsDetails = getStageDetails(
    latestStageLookup,
    "Save future-card predictions"
  );

  const selectedFutureCardSummary = useMemo(
    () => summarizeFutureCard(selectedCard),
    [selectedCard]
  );

  const selectedRecentCardSummary = useMemo(
  () => summarizeRecentCard(selectedRecentCard),
  [selectedRecentCard]
);

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

const futureFightCount = useMemo(() => {
  return futureCards.reduce((total, card) => {
    return total + Number(card.fight_count ?? 0);
  }, 0);
}, [futureCards]);

const recentStatusCounts = useMemo(() => {
  return recentCards.reduce(
    (counts, card) => {
      if (card.status === "completed") {
        counts.completed += 1;
      } else if (card.status === "partially_completed") {
        counts.partial += 1;
      } else {
        counts.waiting += 1;
      }

      return counts;
    },
    {
      completed: 0,
      partial: 0,
      waiting: 0,
    }
  );
}, [recentCards]);

const latestUpdateWasSuccessful = latestReportSummary?.success === true;
const latestUpdateFailed = latestReportSummary?.success === false;

const dashboardModelName = trainModelDetails.best_model_name || "N/A";

const activeViewDetails = {
  single: {
    eyebrow: "Prediction workspace",
    title: "Single fight prediction",
    description:
      "Compare two fighters, review model confidence, and scan the matchup edges that matter most.",
  },
  profile: {
    eyebrow: "Fighter intelligence",
    title: "Fighter profile",
    description:
      "Open a scouting-style profile with model stats, image data, recent form, Elo movement, and fight history.",
  },
  cards: {
    eyebrow: "Upcoming schedule",
    title: "Future card predictions",
    description:
      "Track upcoming cards, model picks, confidence buckets, and comparison-only market odds snapshots.",
  },
  recent: {
    eyebrow: "Prediction tracking",
    title: "Recent cards",
    description:
      "Review saved predictions against completed results and compare the model against market favorites.",
  },
  leaderboards: {
    eyebrow: "Fighter rankings",
    title: "Leaderboards",
    description:
      "Surface top fighters by Elo, striking, grappling, finishing, defense, reach, and other model-derived stats.",
  },
  update: {
    eyebrow: "Data operations",
    title: "Update data",
    description:
      "Run the incremental pipeline, monitor progress, and inspect the latest data/model update report.",
  },
  evaluation: {
    eyebrow: "Model review",
    title: "Evaluation",
    description:
      "Check model metrics, calibration buckets, recent predictions, method model metrics, and market comparison results.",
  },
}[activeView] ?? {
  eyebrow: "UFC fight predictor",
  title: "Predict fight win probabilities",
  description:
    "Uses scraped UFCStats data, Elo-style features, physical profile data, historical fight stats, and a calibrated model.",
};

const navigationItems = [
  { value: "single", label: "Single fight", icon: IconSwords },
  { value: "profile", label: "Fighter profile", icon: IconUserSearch },
  { value: "cards", label: "Future cards", icon: IconCalendarStats },
  { value: "recent", label: "Recent cards", icon: IconHistory },
  { value: "leaderboards", label: "Leaderboards", icon: IconTrophy },
  { value: "evaluation", label: "Evaluation", icon: IconChartBar },
  { value: "update", label: "Update data", icon: IconDatabase },
];

function selectView(nextView) {
  setActiveView(nextView);
  closeMobile();
}

  return (
    <AppShell
      header={{ height: 72 }}
      navbar={{
        width: 292,
        breakpoint: "md",
        collapsed: { mobile: !mobileOpened, desktop: !desktopOpened },
      }}
      padding="md"
      className="mantine-command-shell"
    >
      <AppShell.Header className="command-header">
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger
              opened={mobileOpened}
              onClick={toggleMobile}
              hiddenFrom="md"
              size="sm"
              aria-label="Toggle navigation"
            />

            <Burger
              opened={desktopOpened}
              onClick={toggleDesktop}
              visibleFrom="md"
              size="sm"
              aria-label="Toggle navigation"
            />

            <ThemeIcon size={42} radius="xl" variant="gradient" gradient={{ from: "blue", to: "cyan" }}>
              <IconActivity size={22} />
            </ThemeIcon>

            <Box>
              <Text size="xs" tt="uppercase" fw={800} c="dimmed" lh={1}>
                Fight predictor
              </Text>
              <Title order={3} className="command-brand-title">
                UFC Predictor
              </Title>
            </Box>
          </Group>

          <Group gap="sm" wrap="nowrap">
            <Badge
              className="api-status-badge"
              leftSection={<span className="status-dot" />}
              variant="light"
              color="green"
              radius="xl"
              visibleFrom="sm"
            >
              Local API connected
            </Badge>

            <Tooltip label={`Switch to ${isDarkMode ? "light" : "dark"} mode`}>
              <ActionIcon
                variant="default"
                size="lg"
                radius="xl"
                aria-label={`Switch to ${isDarkMode ? "light" : "dark"} mode`}
                onClick={() => setColorScheme(isDarkMode ? "light" : "dark")}
              >
                {isDarkMode ? <IconSun size={19} /> : <IconMoon size={19} />}
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar className="command-navbar" p="md">
        <AppShell.Section>
          <Paper className="nav-product-card" p="md" radius="xl" withBorder>
            <Text size="xs" tt="uppercase" fw={800} c="dimmed">
              Command center
            </Text>
            <Text fw={900} size="lg">
              UFC Analytics
            </Text>
            <Text size="sm" c="dimmed" mt={4}>
              Predictions, cards, profiles, and model review.
            </Text>
          </Paper>
        </AppShell.Section>

        <Divider my="md" />

        <AppShell.Section grow component={ScrollArea} scrollbarSize={6}>
          <Stack gap={6}>
            {navigationItems.map((item) => {
              const Icon = item.icon;

              return (
                <NavLink
                  key={item.value}
                  className="command-nav-link"
                  active={activeView === item.value}
                  label={item.label}
                  leftSection={
                    <ThemeIcon
                      size={32}
                      radius="md"
                      variant={activeView === item.value ? "filled" : "light"}
                      color={activeView === item.value ? "blue" : "gray"}
                    >
                      <Icon size={18} />
                    </ThemeIcon>
                  }
                  onClick={() => selectView(item.value)}
                />
              );
            })}
          </Stack>
        </AppShell.Section>

        <AppShell.Section>
          <Paper className="nav-status-card" p="md" radius="xl" withBorder>
            <Group justify="space-between" align="flex-start" gap="xs">
              <Box>
                <Text size="xs" tt="uppercase" fw={800} c="dimmed">
                  Current model
                </Text>
                <Text fw={900}>{formatModelName(dashboardModelName)}</Text>
              </Box>
              <IconRefresh size={18} className="nav-status-icon" />
            </Group>
            <Text size="xs" c="dimmed" mt={8}>
              {latestUpdateWasSuccessful
                ? "Latest update succeeded"
                : latestUpdateFailed
                  ? "Latest update failed"
                  : "No update report loaded"}
            </Text>
          </Paper>
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main className="command-main">
        <Box className="command-main-inner">
          <Paper className="command-page-hero" radius="xl" p="xl" withBorder>
            <Group justify="space-between" align="flex-start" gap="xl">
              <Box className="command-page-copy">
                <Text className="eyebrow">{activeViewDetails.eyebrow}</Text>
                <Title className="command-page-title">{activeViewDetails.title}</Title>
                <Text className="hero-copy">{activeViewDetails.description}</Text>
              </Box>

              <SimpleGrid className="command-hero-metrics" cols={3} spacing="sm">
                <Paper className="hero-metric" p="md" radius="lg" withBorder>
                  <Text size="xs" c="dimmed" fw={800}>
                    Upcoming
                  </Text>
                  <Text fw={900} size="xl">
                    {formatNumber(futureCards.length)}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {formatNumber(futureFightCount)} fights
                  </Text>
                </Paper>

                <Paper className="hero-metric" p="md" radius="lg" withBorder>
                  <Text size="xs" c="dimmed" fw={800}>
                    Saved cards
                  </Text>
                  <Text fw={900} size="xl">
                    {formatNumber(recentCards.length)}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {recentStatusCounts.waiting} waiting
                  </Text>
                </Paper>

                <Paper className="hero-metric" p="md" radius="lg" withBorder>
                  <Text size="xs" c="dimmed" fw={800}>
                    Model
                  </Text>
                  <Text fw={900} size="xl">
                    {formatModelName(dashboardModelName)}
                  </Text>
                  <Text size="xs" c="dimmed">
                    current build
                  </Text>
                </Paper>
              </SimpleGrid>
            </Group>
          </Paper>

          <Paper className="compact-dashboard command-dashboard" radius="xl" withBorder>
            <button
              type="button"
              className="compact-dashboard-toggle"
              onClick={() => setShowDashboardDetails((currentValue) => !currentValue)}
            >
              <div>
                <span className="status-dot" />
                <strong>
                  {latestUpdateWasSuccessful
                    ? "Data/model up to date"
                    : latestUpdateFailed
                      ? "Last update failed"
                      : "Project status"}
                </strong>
                <em>
                  {futureCards.length} upcoming cards • {recentCards.length} saved cards •{" "}
                  {formatModelName(dashboardModelName)}
                </em>
              </div>

              <span className="dashboard-chevron">
                {showDashboardDetails ? "Hide details ▲" : "Show details ▼"}
              </span>
            </button>

            {showDashboardDetails && (
              <div className="dashboard-details-grid">
                <div className="dashboard-card">
                  <span>Upcoming cards</span>
                  <strong>{formatNumber(futureCards.length)}</strong>
                  <em>{formatNumber(futureFightCount)} known fights</em>
                </div>

                <div className="dashboard-card">
                  <span>Recent tracking</span>
                  <strong>{formatNumber(recentCards.length)}</strong>
                  <em>
                    {recentStatusCounts.waiting} waiting • {recentStatusCounts.completed} completed
                  </em>
                </div>

                <div className="dashboard-card">
                  <span>Last update</span>
                  <strong>
                    {latestUpdateWasSuccessful
                      ? "Success"
                      : latestUpdateFailed
                        ? "Failed"
                        : "No report"}
                  </strong>
                  <em>{latestReportFinishedAt || "Run update to generate report"}</em>
                </div>

                <div className="dashboard-card">
                  <span>Current model</span>
                  <strong>{formatModelName(dashboardModelName)}</strong>
                  <em>
                    {trainModelDetails.best_model_metrics?.accuracy !== undefined
                      ? `${(trainModelDetails.best_model_metrics.accuracy * 100).toFixed(1)}% test accuracy`
                      : "Metrics unavailable"}
                  </em>
                </div>

                <div className="dashboard-card">
                  <span>Saved predictions</span>
                  <strong>{formatNumber(latestReportSummary?.saved_card_predictions_rows)}</strong>
                  <em>Used by Recent Cards</em>
                </div>
              </div>
            )}
          </Paper>

          <Box className="command-content">
      {activeView === "single" && (
        <SingleFightTab
          fighterA={fighterA}
          setFighterA={setFighterA}
          fighterB={fighterB}
          setFighterB={setFighterB}
          weightClass={weightClass}
          setWeightClass={setWeightClass}
          weightClasses={weightClasses}
          fighterASearchResults={fighterASearchResults}
          setFighterASearchResults={setFighterASearchResults}
          fighterBSearchResults={fighterBSearchResults}
          setFighterBSearchResults={setFighterBSearchResults}
          searchFighters={searchFighters}
          handlePredict={handlePredict}
          loading={loading}
          error={error}
          singlePrediction={singlePrediction}
          showSingleFightEdges={showSingleFightEdges}
          setShowSingleFightEdges={setShowSingleFightEdges}
          fighterImageLookup={fighterImageLookup}
          singleMethodPrediction={singleMethodPrediction}
          methodPredictionLoading={methodPredictionLoading}
          methodPredictionError={methodPredictionError}
          loadExampleFight={loadExampleFight}
          swapSingleFightFighters={swapSingleFightFighters}
          clearSingleFightForm={clearSingleFightForm}
        />
      )}


      {activeView === "profile" && (
        <FighterProfileTab
          profileFighter={profileFighter}
          setProfileFighter={setProfileFighter}
          profileSearchResults={profileSearchResults}
          setProfileSearchResults={setProfileSearchResults}
          fighterProfile={fighterProfile}
          fighterProfileLoading={fighterProfileLoading}
          fighterProfileError={fighterProfileError}
          searchFighters={searchFighters}
          loadFighterProfile={loadFighterProfile}
          setFighterA={setFighterA}
          setFighterB={setFighterB}
          setActiveView={setActiveView}
          fighterImageLookup={fighterImageLookup}
        />
      )}

      {activeView === "cards" && (
        <FutureCardsTab
          cardsLoading={cardsLoading}
          cardsError={cardsError}
          futureFightOddsError={futureFightOddsError}
          futureCards={futureCards}
          selectedCardId={selectedCardId}
          setSelectedCardId={setSelectedCardId}
          selectedCard={selectedCard}
          cardPredictionsLoading={cardPredictionsLoading}
          selectedFutureCardSummary={selectedFutureCardSummary}
          selectedFightPrediction={selectedFightPrediction}
          setSelectedFightPrediction={setSelectedFightPrediction}
          refreshFutureCards={refreshFutureCards}
          loadCardPredictions={loadCardPredictions}
          fighterImageLookup={fighterImageLookup}
          openFighterProfile={openFighterProfile}
          futureFightOdds={futureFightOdds}
          getOddsForFight={getOddsForFight}
        />
      )}

      {activeView === "recent" && (
        <RecentCardsTab
          recentCards={recentCards}
          recentLoading={recentLoading}
          recentError={recentError}
          loadRecentCards={loadRecentCards}
          selectedRecentCardId={selectedRecentCardId}
          setSelectedRecentCardId={setSelectedRecentCardId}
          selectedRecentCard={selectedRecentCard}
          selectedRecentCardSummary={selectedRecentCardSummary}
          selectedRecentFight={selectedRecentFight}
          setSelectedRecentFight={setSelectedRecentFight}
          fighterImageLookup={fighterImageLookup}
          openFighterProfile={openFighterProfile}
        />
      )}

      {activeView === "leaderboards" && (
        <LeaderboardsTab
          leaderboards={leaderboards}
          leaderboardsLoading={leaderboardsLoading}
          leaderboardsError={leaderboardsError}
          leaderboardOptions={leaderboardOptions}
          leaderboardScope={leaderboardScope}
          setLeaderboardScope={setLeaderboardScope}
          leaderboardWeightClass={leaderboardWeightClass}
          setLeaderboardWeightClass={setLeaderboardWeightClass}
          leaderboardCategory={leaderboardCategory}
          setLeaderboardCategory={setLeaderboardCategory}
          leaderboardDirection={leaderboardDirection}
          setLeaderboardDirection={setLeaderboardDirection}
          leaderboardTop={leaderboardTop}
          setLeaderboardTop={setLeaderboardTop}
          leaderboardMinFights={leaderboardMinFights}
          setLeaderboardMinFights={setLeaderboardMinFights}
          leaderboardMaxInactiveDays={leaderboardMaxInactiveDays}
          setLeaderboardMaxInactiveDays={setLeaderboardMaxInactiveDays}
          loadLeaderboards={loadLeaderboards}
          fighterImageLookup={fighterImageLookup}
          openFighterProfile={openFighterProfile}
        />
      )}

      {activeView === "evaluation" && (
        <EvaluationTab
          modelEvaluation={modelEvaluation}
          modelEvaluationLoading={modelEvaluationLoading}
          modelEvaluationError={modelEvaluationError}
          loadModelEvaluation={loadModelEvaluation}
          modelMarketEvaluation={modelMarketEvaluation}
          modelMarketEvaluationLoading={modelMarketEvaluationLoading}
          modelMarketEvaluationError={modelMarketEvaluationError}
          loadModelMarketEvaluation={loadModelMarketEvaluation}
          methodModelMetrics={methodModelMetrics}
          methodModelMetricsError={methodModelMetricsError}
          evaluationTestFraction={evaluationTestFraction}
          setEvaluationTestFraction={setEvaluationTestFraction}
          evaluationRecentLimit={evaluationRecentLimit}
          setEvaluationRecentLimit={setEvaluationRecentLimit}
        />
      )}
      {activeView === "update" && (
        <UpdateDataTab
          startIncrementalUpdate={startIncrementalUpdate}
          updateLoading={updateLoading}
          updateStatus={updateStatus}
          updateError={updateError}
          latestReport={latestReport}
          latestReportSummary={latestReportSummary}
          latestReportStartedAt={latestReportStartedAt}
          latestReportFinishedAt={latestReportFinishedAt}
          latestReportDuration={latestReportDuration}
          loadLatestReport={loadLatestReport}
          fightStatsUpdateDetails={fightStatsUpdateDetails}
          trainModelDetails={trainModelDetails}
          refreshFutureCardsDetails={refreshFutureCardsDetails}
          saveFuturePredictionsDetails={saveFuturePredictionsDetails}
        />
      )}
          </Box>
        </Box>
      </AppShell.Main>
    </AppShell>
  );
}

export default App;