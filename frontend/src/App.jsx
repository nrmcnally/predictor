import { useEffect, useMemo, useState } from "react";
import "./App.css";

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

function formatEdgeDifference(edge) {
  if (edge.difference === null || edge.difference === undefined) {
    return "Unknown";
  }

  const sign = edge.difference > 0 ? "+" : "";
  const value = Number(edge.difference).toFixed(2);

  return edge.unit ? `${sign}${value} ${edge.unit}` : `${sign}${value}`;
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

function PredictionDetails({ prediction, showBasicEdges = false }) {
  const winnerSide = useMemo(() => {
    if (!prediction) {
      return null;
    }

    if (prediction.predicted_winner === prediction.fighter_a) {
      return "fighter_a";
    }

    if (prediction.predicted_winner === prediction.fighter_b) {
      return "fighter_b";
    }

    return null;
  }, [prediction]);

  if (!prediction) {
    return (
      <div className="empty-state">
        <h2>No fight selected</h2>
        <p>Select or run a fight prediction to see details.</p>
      </div>
    );
  }

  const insights = prediction.matchup_insights;

  const predictedInsightKey =
    prediction.predicted_winner === prediction.fighter_a ? "fighter_a" : "fighter_b";

  const opponentInsightKey =
    predictedInsightKey === "fighter_a" ? "fighter_b" : "fighter_a";

  const predictedFighterInsights = insights?.[predictedInsightKey];
  const opponentFighterInsights = insights?.[opponentInsightKey];

  const predictedConcernEdgeLabels = new Set(
    predictedFighterInsights?.concerns?.map((item) => item.edge_label) ?? []
  );

  const uniqueOpponentPaths =
    opponentFighterInsights?.strengths?.filter(
      (item) => !predictedConcernEdgeLabels.has(item.edge_label)
    ) ?? [];

  return (
    <>
      <div className="winner-card">
        <p className="eyebrow">Predicted winner</p>
        <h2>{prediction.predicted_winner}</h2>
        <p>{prediction.confidence_label}</p>
        <strong>{prediction.confidence_percentage}</strong>
      </div>

      <div className="probability-grid">
        <div className={`fighter-result ${winnerSide === "fighter_a" ? "winner" : ""}`}>
          <div className="fighter-result-header">
            <h3>{prediction.fighter_a}</h3>
            <strong>{prediction.fighter_a_percentage}</strong>
          </div>
          <div className="probability-bar">
            <div
              className="probability-fill"
              style={{
                width: getProbabilityWidth(prediction.fighter_a_probability),
              }}
            />
          </div>
        </div>

        <div className={`fighter-result ${winnerSide === "fighter_b" ? "winner" : ""}`}>
          <div className="fighter-result-header">
            <h3>{prediction.fighter_b}</h3>
            <strong>{prediction.fighter_b_percentage}</strong>
          </div>
          <div className="probability-bar">
            <div
              className="probability-fill"
              style={{
                width: getProbabilityWidth(prediction.fighter_b_probability),
              }}
            />
          </div>
        </div>
      </div>

      {insights && predictedFighterInsights && opponentFighterInsights && (
        <div className="insights-card">
          <h2>Why this prediction?</h2>

          <div className="insight-summary-list">
            {insights.summary?.map((item, index) => (
              <div className={`insight-summary ${item.type}`} key={`${item.type}-${index}`}>
                {item.text}
              </div>
            ))}
          </div>

          <div className="explanation-layout">
            <div className="explanation-section">
              <h3>Support for {prediction.predicted_winner}</h3>

              {predictedFighterInsights.strengths.length === 0 && (
                <p>No major rule-based support edges found.</p>
              )}

              {predictedFighterInsights.strengths.map((item, index) => (
                <div className={`insight-item ${item.severity}`} key={`pick-strength-${index}`}>
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                </div>
              ))}
            </div>

            <div className="explanation-section">
              <h3>Reasons to be cautious</h3>

              {predictedFighterInsights.concerns.length === 0 && (
                <p>No major rule-based concerns found for the pick.</p>
              )}

              {predictedFighterInsights.concerns.map((item, index) => (
                <div
                  className={`insight-item concern ${item.severity}`}
                  key={`pick-concern-${index}`}
                >
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                </div>
              ))}
            </div>

            <div className="explanation-section full-width">
              <h3>Opponent’s unique path</h3>

              {uniqueOpponentPaths.length === 0 && (
                <p>
                  The opponent’s biggest edges are already covered in the caution section.
                </p>
              )}

              {uniqueOpponentPaths.map((item, index) => (
                <div className={`insight-item ${item.severity}`} key={`opponent-path-${index}`}>
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

            {showBasicEdges && (
        <div className="edges-card">
          <h2>Basic matchup edges</h2>

          <div className="edges-list">
            {prediction.basic_matchup_edges.map((edge) => (
              <div className="edge-row" key={edge.label}>
                <div>
                  <strong>{edge.label}</strong>
                  <span>
                    {prediction.fighter_a} vs {prediction.fighter_b}
                  </span>
                </div>
                <strong>{formatEdgeDifference(edge)}</strong>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function MethodPredictionDetails({
  methodPrediction,
  loading = false,
  error = "",
}) {
  if (loading) {
    return (
      <div className="method-card">
        <p className="eyebrow">Manner of ending</p>
        <h2>Loading method probabilities...</h2>
      </div>
    );
  }

  if (error) {
    return (
      <div className="method-card">
        <p className="eyebrow">Manner of ending</p>
        <h2>Method prediction unavailable</h2>
        <p className="method-note">{error}</p>
      </div>
    );
  }

  if (!methodPrediction) {
    return null;
  }

  return (
    <div className="method-card">
      <div className="method-header">
        <div>
          <p className="eyebrow">Manner of ending</p>
          <h2>
            Most likely: {methodPrediction.predicted_broad_method}{" "}
            <span>{methodPrediction.predicted_broad_method_percentage}</span>
          </h2>
          <p>
            Detailed lean: {methodPrediction.predicted_detailed_method}{" "}
            {methodPrediction.predicted_detailed_method_percentage}
          </p>
        </div>
      </div>

      <div className="method-grid">
        <div className="method-section">
          <h3>Broad method</h3>

          <div className="method-probability-list">
            {methodPrediction.broad_method_probabilities?.map((row) => (
              <div className="method-probability-row" key={row.label}>
                <div className="method-row-label">
                  <strong>{row.label}</strong>
                  <span>{row.percentage}</span>
                </div>

                <div className="method-bar-track">
                  <div
                    className="method-bar-fill"
                    style={{ width: getProbabilityWidth(row.probability) }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="method-section">
          <h3>Detailed method</h3>

          <div className="method-probability-list detailed">
            {methodPrediction.detailed_method_probabilities?.map((row) => (
              <div className="method-probability-row" key={row.label}>
                <div className="method-row-label">
                  <strong>{row.label}</strong>
                  <span>{row.percentage}</span>
                </div>

                <div className="method-bar-track">
                  <div
                    className="method-bar-fill"
                    style={{ width: getProbabilityWidth(row.probability) }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <p className="method-note">{methodPrediction.model_note}</p>
    </div>
  );
}

function FightOddsComparison({ fight, odds }) {
  if (!odds || !odds.odds_available) {
    return (
      <div className="odds-comparison muted">
        <span>Market odds unavailable</span>
      </div>
    );
  }

  const fighter1Name = fight?.fighter_1 || "Fighter 1";
  const fighter2Name = fight?.fighter_2 || "Fighter 2";

  return (
    <div className="odds-comparison">
      <div>
        <span>Market favorite</span>
        <strong>
          {odds.market_favorite || "Unknown"}{" "}
          {odds.market_favorite_percentage || ""}
        </strong>
      </div>

      <div>
        <span>{fighter1Name}</span>
        <strong>
          {formatAmericanOdds(odds.fighter_1_odds_american)} •{" "}
          {odds.fighter_1_market_percentage || "N/A"}
        </strong>
      </div>

      <div>
        <span>{fighter2Name}</span>
        <strong>
          {formatAmericanOdds(odds.fighter_2_odds_american)} •{" "}
          {odds.fighter_2_market_percentage || "N/A"}
        </strong>
      </div>

      <small>
      {odds.odds_bookmaker
        ? `${odds.odds_bookmaker}${odds.bookmakers_matched ? ` • ${odds.bookmakers_matched} books` : ""}`
        : "Market odds source unavailable"}
    </small>

    <small className="odds-comparison-note">
      Market odds are shown for comparison only and are not used as model features.
    </small>
    </div>
  );
}

function RecentFightDetails({ fight }) {
  if (!fight) {
    return (
      <div className="empty-state">
        <h2>No recent fight selected</h2>
        <p>Select a saved fight prediction to see the result comparison.</p>
      </div>
    );
  }

  const fighter1Probability = parsePercentageText(fight.fighter_1_percentage);
  const fighter2Probability = parsePercentageText(fight.fighter_2_percentage);

  const resultClass = getRecentFightResultClass(fight);

  return (
    <>
      <div className={`recent-result-card ${resultClass}`}>
        <p className="eyebrow">Prediction result</p>

        <h2>
          {resultClass === "correct"
            ? "Correct prediction"
            : resultClass === "incorrect"
              ? "Incorrect prediction"
              : resultClass === "no-prediction"
                ? "No saved prediction"
                : "Waiting for results"}
        </h2>

        {fight.prediction_available ? (
          <p>
            Predicted <strong>{fight.predicted_winner}</strong> at{" "}
            <strong>{fight.confidence_percentage}</strong> confidence.
          </p>
        ) : (
          <p>No saved prediction was available for this fight.</p>
        )}

        {fight.actual_result_available && (
          <p>
            Actual winner: <strong>{fight.actual_winner}</strong>
            {fight.actual_method && (
              <>
                {" "}
                by {fight.actual_method}
                {fight.actual_round && `, Round ${fight.actual_round}`}
                {fight.actual_time && ` at ${fight.actual_time}`}
              </>
            )}
          </p>
        )}
      </div>

      <div className="probability-grid">
        <div
          className={`fighter-result ${
            fight.predicted_winner === fight.fighter_1 ? "winner" : ""
          }`}
        >
          <div className="fighter-result-header">
            <h3>{fight.fighter_1}</h3>
            <strong>{fight.fighter_1_percentage || "N/A"}</strong>
          </div>
          <div className="probability-bar">
            <div
              className="probability-fill"
              style={{
                width: getProbabilityWidth(fighter1Probability ?? 0),
              }}
            />
          </div>
        </div>

        <div
          className={`fighter-result ${
            fight.predicted_winner === fight.fighter_2 ? "winner" : ""
          }`}
        >
          <div className="fighter-result-header">
            <h3>{fight.fighter_2}</h3>
            <strong>{fight.fighter_2_percentage || "N/A"}</strong>
          </div>
          <div className="probability-bar">
            <div
              className="probability-fill"
              style={{
                width: getProbabilityWidth(fighter2Probability ?? 0),
              }}
            />
          </div>
        </div>
      </div>

      <FightOddsComparison fight={fight} odds={fight} />

      <div className="edges-card">
        <h2>Saved prediction details</h2>

        <div className="edges-list">
          <div className="edge-row">
            <div>
              <strong>Predicted winner</strong>
              <span>Model pick before the card result was known</span>
            </div>
            <strong>{fight.predicted_winner || "Unavailable"}</strong>
          </div>

          <div className="edge-row">
            <div>
              <strong>Actual winner</strong>
              <span>Filled once the completed event is scraped</span>
            </div>
            <strong>{fight.actual_winner || "Waiting"}</strong>
          </div>

          <div className="edge-row">
            <div>
              <strong>Confidence label</strong>
              <span>Saved model confidence bucket</span>
            </div>
            <strong>{fight.confidence_label || "Unavailable"}</strong>
          </div>

          <div className="edge-row">
            <div>
              <strong>Model</strong>
              <span>Model used when the prediction was saved</span>
            </div>
            <strong>{fight.model_name || "Unknown"}</strong>
          </div>

          <div className="edge-row">
            <div>
              <strong>Market favorite</strong>
              <span>Saved sportsbook consensus/representative odds snapshot</span>
            </div>
            <strong>
              {fight.odds_available
                ? `${fight.market_favorite || "Unknown"} ${
                    fight.market_favorite_percentage || ""
                  }`
                : "Unavailable"}
            </strong>
          </div>

          <div className="edge-row">
            <div>
              <strong>Market result</strong>
              <span>Whether the saved market favorite matched the actual winner</span>
            </div>
            <strong>
              {fight.market_correct === true
                ? "Correct"
                : fight.market_correct === false
                  ? "Wrong"
                  : "N/A"}
            </strong>
          </div>

          <div className="edge-row">
            <div>
              <strong>Saved at</strong>
              <span>When this prediction snapshot was saved</span>
            </div>
            <strong>{fight.saved_at || "Unknown"}</strong>
          </div>
        </div>
      </div>
    </>
  );
}

function App() {
  const [activeView, setActiveView] = useState("single");

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
    loadMethodModelMetrics();
    loadFutureFightOdds();
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

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">UFC fight predictor</p>
          <h1>Predict fight win probabilities</h1>
          <p className="hero-copy">
            Uses scraped UFCStats data, Elo-style features, physical profile data,
            historical fight stats, and a calibrated model.
          </p>
        </div>

        <div className="status-card">
          <span className="status-dot" />
          Backend connected to local API
        </div>
      </section>

      <nav className="view-tabs">
        <button
          type="button"
          className={activeView === "single" ? "active" : ""}
          onClick={() => setActiveView("single")}
        >
          Single fight
        </button>

        <button
          type="button"
          className={activeView === "cards" ? "active" : ""}
          onClick={() => setActiveView("cards")}
        >
          Future cards
        </button>

        <button
          type="button"
          className={activeView === "recent" ? "active" : ""}
          onClick={() => setActiveView("recent")}
        >
          Recent cards
        </button>

        <button
          type="button"
          className={activeView === "leaderboards" ? "active" : ""}
          onClick={() => setActiveView("leaderboards")}
        >
          Leaderboards
        </button>

        <button
          type="button"
          className={activeView === "update" ? "active" : ""}
          onClick={() => setActiveView("update")}
        >
          Update data
        </button>

        <button
          type="button"
          className={activeView === "evaluation" ? "active" : ""}
          onClick={() => setActiveView("evaluation")}
        >
          Evaluation
        </button>
      </nav>

      <section className="compact-dashboard">
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
</section>

      {activeView === "single" && (
        <section className="layout">
          <form className="predict-card single-fight-card" onSubmit={handlePredict}>
            <div className="single-form-header">
              <div>
                <p className="eyebrow">Single matchup</p>
                <h2>Single fight prediction</h2>
                <p>
                  Enter two fighters and a weight class to generate win probabilities,
                  matchup insights, and basic statistical edges.
                </p>
              </div>
            </div>

            <div className="example-fight-row">
              <button
                type="button"
                onClick={() =>
                  loadExampleFight("Khamzat Chimaev", "Sean Strickland", "Middleweight")
                }
              >
                Khamzat vs Strickland
              </button>

              <button
                type="button"
                onClick={() =>
                  loadExampleFight("Islam Makhachev", "Max Holloway", "Lightweight")
                }
              >
                Islam vs Holloway
              </button>
            </div>

            <label>
              Fighter A
              <input
                value={fighterA}
                onChange={(event) => {
                  setFighterA(event.target.value);
                  searchFighters(event.target.value, setFighterASearchResults);
                }}
                placeholder="Example: Khamzat Chimaev"
              />
            </label>

            {fighterASearchResults.length > 0 && (
              <div className="suggestions">
                {fighterASearchResults.map((name) => (
                  <button
                    type="button"
                    key={name}
                    onClick={() => {
                      setFighterA(name);
                      setFighterASearchResults([]);
                    }}
                  >
                    {name}
                  </button>
                ))}
              </div>
            )}

            <label>
              Fighter B
              <input
                value={fighterB}
                onChange={(event) => {
                  setFighterB(event.target.value);
                  searchFighters(event.target.value, setFighterBSearchResults);
                }}
                placeholder="Example: Sean Strickland"
              />
            </label>

            {fighterBSearchResults.length > 0 && (
              <div className="suggestions">
                {fighterBSearchResults.map((name) => (
                  <button
                    type="button"
                    key={name}
                    onClick={() => {
                      setFighterB(name);
                      setFighterBSearchResults([]);
                    }}
                  >
                    {name}
                  </button>
                ))}
              </div>
            )}

            <label>
              Weight class
              <select
                value={weightClass}
                onChange={(event) => setWeightClass(event.target.value)}
              >
                {weightClasses.map((weightClassOption) => (
                  <option key={weightClassOption} value={weightClassOption}>
                    {weightClassOption}
                  </option>
                ))}
              </select>
            </label>

            <div className="single-form-actions">
              <button className="primary-button" type="submit" disabled={loading}>
                {loading ? "Predicting..." : "Predict fight"}
              </button>

              <button
                className="secondary-button"
                type="button"
                onClick={swapSingleFightFighters}
                disabled={!fighterA && !fighterB}
              >
                Swap fighters
              </button>

              <button
                className="secondary-button"
                type="button"
                onClick={clearSingleFightForm}
              >
                Clear
              </button>
            </div>

            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={showSingleFightEdges}
                onChange={(event) => setShowSingleFightEdges(event.target.checked)}
              />
              Show basic matchup edges
            </label>

            {error && <pre className="error-box">{error}</pre>}
          </form>

          <section className="results-panel">
            <PredictionDetails
              prediction={singlePrediction}
              showBasicEdges={showSingleFightEdges}
            />

            <MethodPredictionDetails
              methodPrediction={singleMethodPrediction}
              loading={methodPredictionLoading}
              error={methodPredictionError}
            />
          </section>
        </section>
      )}

      {activeView === "cards" && (
        <section className="cards-layout">
          <aside className="cards-sidebar">
            <div className="cards-sidebar-header">
              <h2>Future cards</h2>
              <button type="button" onClick={refreshFutureCards} disabled={cardsLoading}>
                {cardsLoading ? "Refreshing..." : "Refresh"}
              </button>
            </div>

            {cardsError && <pre className="error-box">{cardsError}</pre>}
            {futureFightOddsError && <pre className="error-box">{futureFightOddsError}</pre>}

            <div className="card-list">
              {futureCards.map((card) => (
                <button
                  type="button"
                  key={card.event_id}
                  className={selectedCardId === card.event_id ? "event-card active" : "event-card"}
                  onClick={() => {
                    setSelectedCardId(card.event_id);
                    setSelectedFightPrediction(null);
                  }}
                >
                  <strong>{card.event_name}</strong>
                  <span>{card.event_date}</span>
                  <span>{card.event_location}</span>
                  <em>{card.fight_count} known fights</em>
                </button>
              ))}
            </div>
          </aside>

          <section className="card-fights-panel">
            {!selectedCard && (
              <div className="empty-state">
                <h2>{cardPredictionsLoading ? "Loading card..." : "Select a card"}</h2>
                <p>Pick an upcoming card to see scheduled fight predictions.</p>
              </div>
            )}

            {selectedCard && (
              <>
                <div className="selected-card-header">
            <div>
              <p className="eyebrow">Selected card</p>
              <h2>{selectedCard.event_name}</h2>
              <p>
                {selectedCard.event_date} • {selectedCard.event_location}
              </p>
            </div>

            <button
              type="button"
              onClick={() => loadCardPredictions(selectedCard.event_id)}
              disabled={cardPredictionsLoading}
            >
              {cardPredictionsLoading ? "Loading..." : "Reload predictions"}
            </button>
          </div>

          <div className="future-card-summary-grid">
            <div>
              <span>Total fights</span>
              <strong>{selectedFutureCardSummary.totalFights}</strong>
            </div>

            <div>
              <span>Predictions available</span>
              <strong>{selectedFutureCardSummary.predictionAvailableCount}</strong>
            </div>

            <div>
              <span>No prediction</span>
              <strong>{selectedFutureCardSummary.predictionUnavailableCount}</strong>
            </div>

            <div>
              <span>Strong/high leans</span>
              <strong>{selectedFutureCardSummary.highConfidenceCount}</strong>
            </div>

            <div>
              <span>Moderate leans</span>
              <strong>{selectedFutureCardSummary.moderateConfidenceCount}</strong>
            </div>

            <div>
              <span>Close fights</span>
              <strong>{selectedFutureCardSummary.closeFightCount}</strong>
            </div>
          </div>

                <div className="fight-list">
                  {selectedCard.fights.map((fight) => (
                    <button
                      type="button"
                      key={fight.fight_id}
                      className={
                        selectedFightPrediction &&
                        fight.prediction?.fighter_a === selectedFightPrediction.fighter_a &&
                        fight.prediction?.fighter_b === selectedFightPrediction.fighter_b
                          ? "fight-row active"
                          : "fight-row"
                      }
                      onClick={() => {
                        if (fight.prediction_available) {
                          setSelectedFightPrediction(fight.prediction);
                        }
                      }}
                    >
                      <div>
                        <strong>
                          {fight.fighter_1} vs {fight.fighter_2}
                        </strong>
                        <span>{fight.weight_class}</span>
                      </div>

                      {fight.prediction_available ? (
                        <div className="fight-pick">
                          <strong>{fight.prediction.predicted_winner}</strong>
                          <span>{fight.prediction.confidence_percentage}</span>
                        </div>
                      ) : (
                        <div className="fight-unavailable">
                          <strong>No prediction</strong>
                          <span>{fight.error?.message ?? "Missing fighter data"}</span>
                        </div>
                      )}

                      <FightOddsComparison
                        fight={fight}
                        odds={getOddsForFight(futureFightOdds, fight.fight_url)}
                      />
                    </button>
                  ))}
                </div>
              </>
            )}
          </section>

          <section className="results-panel">
            <PredictionDetails prediction={selectedFightPrediction} />
          </section>
        </section>
      )}

      {activeView === "recent" && (
        <section className="cards-layout">
          <aside className="cards-sidebar">
            <div className="cards-sidebar-header">
              <h2>Recent cards</h2>

              <div className="sidebar-button-group">
                <button type="button" onClick={loadRecentCards} disabled={recentLoading}>
                  {recentLoading ? "Loading..." : "Reload"}
                </button>
              </div>
            </div>

            {recentError && <pre className="error-box">{recentError}</pre>}

            <div className="card-list">
              {recentCards.length === 0 && (
                <div className="mini-empty-state">
                  <strong>No saved cards yet</strong>
                  <span>
                    Save future-card predictions first, then this tab can compare them
                    against actual results later.
                  </span>
                </div>
              )}

              {recentCards.map((card) => {
                const statusClass = getRecentCardStatusClass(card.status);

                return (
                  <button
                    type="button"
                    key={card.event_id}
                    className={
                      selectedRecentCardId === card.event_id
                        ? "event-card active"
                        : "event-card"
                    }
                    onClick={() => {
                      setSelectedRecentCardId(card.event_id);
                      setSelectedRecentFight(null);
                    }}
                  >
                    <div className="event-card-title-row">
                      <strong>{card.event_name}</strong>
                      <span className={`status-badge ${statusClass}`}>
                        {card.status === "completed"
                          ? "Completed"
                          : card.status === "partially_completed"
                            ? "Partial"
                            : "Waiting"}
                      </span>
                    </div>

                    <span>{card.event_date}</span>
                    <span>{card.event_location}</span>

                    <em>
                      {card.status === "completed"
                        ? `${card.accuracy_percentage || "N/A"} accuracy`
                        : card.status === "partially_completed"
                          ? `${card.actual_result_count} of ${card.fight_count} results in`
                          : `${card.fight_count} saved predictions`}
                    </em>
                  </button>
                );
              })}
            </div>
          </aside>

          <section className="card-fights-panel">
            {!selectedRecentCard && (
              <div className="empty-state">
                <h2>{recentLoading ? "Loading card..." : "Select a recent card"}</h2>
                <p>
                  Pick a saved card to compare pre-fight predictions against actual
                  results.
                </p>
              </div>
            )}

            {selectedRecentCard && (
              <>
                <div className="selected-card-header">
                  <div>
                    <p className="eyebrow">Saved card</p>
                    <h2>{selectedRecentCard.event_name}</h2>
                    <p>
                      {selectedRecentCard.event_date} • {selectedRecentCard.event_location}
                    </p>
                  </div>

                  <div className="recent-card-summary improved">
                    <span className={`status-badge ${getRecentCardStatusClass(selectedRecentCard.status)}`}>
                      {selectedRecentCard.status === "completed"
                        ? "Completed"
                        : selectedRecentCard.status === "partially_completed"
                          ? "Partially completed"
                          : "Waiting for results"}
                    </span>

                    <strong>{selectedRecentCardSummary.accuracyPercentage}</strong>
                    <span>
                      {selectedRecentCardSummary.correctCount} correct of{" "}
                      {selectedRecentCardSummary.predictedCompletedCount} scored predictions
                    </span>
                    <span>
                      Market: {selectedRecentCardSummary.marketAccuracyPercentage} over{" "}
                      {selectedRecentCardSummary.marketCompletedCount} scored fights
                    </span>
                  </div>
                </div>

                <div className="recent-card-summary-grid">
                  <div>
                    <span>Total fights</span>
                    <strong>{selectedRecentCardSummary.totalFights}</strong>
                  </div>

                  <div>
                    <span>Results in</span>
                    <strong>{selectedRecentCardSummary.actualResultCount}</strong>
                  </div>

                  <div>
                    <span>Correct</span>
                    <strong>{selectedRecentCardSummary.correctCount}</strong>
                  </div>

                  <div>
                    <span>Wrong</span>
                    <strong>{selectedRecentCardSummary.wrongCount}</strong>
                  </div>

                  <div>
                    <span>Waiting</span>
                    <strong>{selectedRecentCardSummary.waitingCount}</strong>
                  </div>

                  <div>
                    <span>Accuracy</span>
                    <strong>{selectedRecentCardSummary.accuracyPercentage}</strong>
                  </div>

                  <div>
                    <span>Market accuracy</span>
                    <strong>{selectedRecentCardSummary.marketAccuracyPercentage}</strong>
                  </div>

                  <div>
                    <span>Market scored</span>
                    <strong>{selectedRecentCardSummary.marketCompletedCount}</strong>
                  </div>
                </div>

                {selectedRecentCard.status === "waiting_for_results" && (
                  <div className="recent-info-box">
                    This card is waiting for completed fight results. After the event happens, run
                    the Update Data pipeline to scrape results and score the saved predictions.
                  </div>
                )}

                <div className="fight-list">
                  {selectedRecentCard.fights.map((fight) => {
                    const resultClass = getRecentFightResultClass(fight);

                    return (
                      <button
                        type="button"
                        key={fight.fight_id}
                        className={
                          selectedRecentFight?.fight_id === fight.fight_id
                            ? "fight-row active"
                            : "fight-row"
                        }
                        onClick={() => setSelectedRecentFight(fight)}
                      >
                        <div>
                          <strong>
                            {fight.fighter_1} vs {fight.fighter_2}
                          </strong>
                          <span>{fight.weight_class}</span>

                          <div className="recent-fight-subline">
                            <span>Predicted: {fight.predicted_winner || "N/A"}</span>
                            {fight.confidence_percentage && (
                              <span>{fight.confidence_percentage} confidence</span>
                            )}
                            {fight.odds_available && (
                              <span>
                                Market: {fight.market_favorite || "N/A"}{" "}
                                {fight.market_favorite_percentage || ""}
                              </span>
                            )}
                          </div>
                        </div>

                        <div className={`fight-result-pill improved ${resultClass}`}>
                        <span className={`status-badge ${resultClass}`}>
                          {resultClass === "correct"
                            ? "Correct"
                            : resultClass === "incorrect"
                              ? "Wrong"
                              : resultClass === "no-prediction"
                                ? "No prediction"
                                : "Waiting"}
                        </span>

                        {fight.actual_result_available ? (
                          <>
                            <strong>{fight.actual_winner}</strong>
                            <span>
                              {!fight.prediction_available
                                ? "No saved prediction"
                                : fight.actual_method
                                  ? `${fight.actual_method}${fight.actual_round ? ` • R${fight.actual_round}` : ""}`
                                  : "Actual winner"}
                            </span>
                          </>
                        ) : (
                            <>
                              <strong>{fight.predicted_winner || "No prediction"}</strong>
                              <span>Awaiting result</span>
                            </>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </section>

          <section className="results-panel">
            <RecentFightDetails fight={selectedRecentFight} />
          </section>
        </section>
      )}

      {activeView === "leaderboards" && (
  <section className="leaderboards-layout">
    <section className="leaderboard-controls-card">
      <div>
        <p className="eyebrow">Fighter analysis</p>
        <h2>Leaderboards</h2>
        <p>
          Rank fighters by category using the current feature dataset. Composite
          categories are for analysis and depend on the feature weights in the backend.
        </p>
      </div>

      <div className="leaderboard-controls-grid">
        <label>
          Scope
          <select
            value={leaderboardScope}
            onChange={(event) => setLeaderboardScope(event.target.value)}
          >
            <option value="overall">Overall</option>
            <option value="weight_class">By weight class</option>
          </select>
        </label>

        <label>
          Weight class
          <select
            value={leaderboardWeightClass}
            onChange={(event) => setLeaderboardWeightClass(event.target.value)}
            disabled={leaderboardScope === "overall"}
          >
            {leaderboardWeightClassOptions.map((weightClassOption) => (
              <option key={weightClassOption} value={weightClassOption}>
                {weightClassOption}
              </option>
            ))}
          </select>
        </label>

        <label>
          Category
          <select
            value={leaderboardCategory}
            onChange={(event) => setLeaderboardCategory(event.target.value)}
          >
            {leaderboardCategoryOptions.map((categoryOption) => (
              <option key={categoryOption.value} value={categoryOption.value}>
                {categoryOption.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Direction
          <select
            value={leaderboardDirection}
            onChange={(event) => setLeaderboardDirection(event.target.value)}
          >
            <option value="best">Best</option>
            <option value="worst">Worst</option>
          </select>
        </label>

        <label>
          Top
          <input
            type="number"
            min="1"
            max="25"
            value={leaderboardTop}
            onChange={(event) => setLeaderboardTop(Number(event.target.value))}
          />
        </label>

        <label>
          Minimum fights
          <input
            type="number"
            min="0"
            value={leaderboardMinFights}
            onChange={(event) =>
              setLeaderboardMinFights(Number(event.target.value))
            }
          />
        </label>

        <label>
          Max inactive days
          <input
            type="number"
            min="0"
            value={leaderboardMaxInactiveDays}
            onChange={(event) =>
              setLeaderboardMaxInactiveDays(Number(event.target.value))
            }
          />
        </label>

        <button
          type="button"
          className="primary-button leaderboard-load-button"
          onClick={loadLeaderboards}
          disabled={leaderboardsLoading}
        >
          {leaderboardsLoading ? "Loading..." : "Load leaderboards"}
        </button>
      </div>

      {leaderboardsError && <pre className="error-box">{leaderboardsError}</pre>}

      {leaderboards?.metadata && (
        <div className="leaderboard-meta-box">
          <span>
            Fighters after filters:{" "}
            <strong>{formatNumber(leaderboards.metadata.fighter_rows_after_filters)}</strong>
          </span>
          <span>
            Min fights: <strong>{leaderboards.metadata.min_fights}</strong>
          </span>
          <span>
            Activity filter:{" "}
            <strong>
              {leaderboards.metadata.max_inactive_days ?? "Disabled"}
            </strong>
          </span>
        </div>
      )}
    </section>

    <section className="leaderboard-results-card">
      <div className="leaderboard-results-header">
        <div>
          <p className="eyebrow">
            {leaderboardDirection === "best" ? "Best" : "Worst"} category ranking
          </p>
          <h2>
            {leaderboardScope === "overall"
              ? "Overall"
              : leaderboardWeightClass}{" "}
            •{" "}
            {
              leaderboardCategoryOptions.find(
                (category) => category.value === leaderboardCategory
              )?.label
            }
          </h2>
        </div>
      </div>

      {displayedLeaderboardRows.length === 0 && (
        <div className="empty-state compact">
          <h2>No leaderboard rows</h2>
          <p>
            Try lowering minimum fights, disabling the inactivity filter with 0,
            or choosing another category.
          </p>
        </div>
      )}

      <div className="leaderboard-row-list">
        {displayedLeaderboardRows.map((row) => (
          <div className="leaderboard-row" key={`${row.rank}-${row.fighter}`}>
            <div className="leaderboard-rank">
              #{row.rank}
            </div>

            <div className="leaderboard-main">
              <h3>{row.fighter}</h3>
              <span>
                {row.weight_class} • {row.prior_fights} UFC fights
              </span>
            </div>

            <div className="leaderboard-score">
              <span>Score</span>
              <strong>{row.score}</strong>
            </div>

            <div className="leaderboard-supporting-stats">
              {Object.entries(row.supporting_stats ?? {}).map(([key, value]) => (
                <div key={key}>
                  <span>{formatStatLabel(key)}</span>
                  <strong>{formatLeaderboardStatValue(key, value)}</strong>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  </section>
)}

{activeView === "evaluation" && (
  <section className="evaluation-layout">
    <section className="evaluation-controls-card">
      <div>
        <p className="eyebrow">Model performance</p>
        <h2>Model evaluation</h2>
        <p>
          Evaluate the currently saved model against a chronological holdout set.
          This helps show where the model is strong, weak, and whether confidence
          levels are reliable.
        </p>
      </div>

      <div className="evaluation-controls-grid">
        <label>
          Test fraction
          <input
            type="number"
            min="0.05"
            max="0.5"
            step="0.05"
            value={evaluationTestFraction}
            onChange={(event) =>
              setEvaluationTestFraction(Number(event.target.value))
            }
          />
        </label>

        <label>
          Recent prediction rows
          <input
            type="number"
            min="5"
            max="100"
            value={evaluationRecentLimit}
            onChange={(event) =>
              setEvaluationRecentLimit(Number(event.target.value))
            }
          />
        </label>

        <button
          type="button"
          className="primary-button evaluation-load-button"
          onClick={loadModelEvaluation}
          disabled={modelEvaluationLoading}
        >
          {modelEvaluationLoading ? "Loading..." : "Reload evaluation"}
        </button>
      </div>

      {modelEvaluationError && <pre className="error-box">{modelEvaluationError}</pre>}

      {modelEvaluation?.metadata && (
        <div className="leaderboard-meta-box">
          <span>
            Test fights:{" "}
            <strong>{formatNumber(modelEvaluation.metadata.test_fights)}</strong>
          </span>
          <span>
            Test range:{" "}
            <strong>
              {modelEvaluation.metadata.test_date_min || "N/A"} →{" "}
              {modelEvaluation.metadata.test_date_max || "N/A"}
            </strong>
          </span>
          <span>
            Model:{" "}
            <strong>
              {formatModelName(modelEvaluation.metadata.saved_best_model_name)}
            </strong>
          </span>
        </div>
      )}
    </section>

    {modelEvaluation?.overall && (
      <section className="evaluation-summary-grid">
        <div>
          <span>Accuracy</span>
          <strong>{modelEvaluation.overall.accuracy_percentage || "N/A"}</strong>
        </div>

        <div>
          <span>Average confidence</span>
          <strong>
            {modelEvaluation.overall.average_confidence_percentage || "N/A"}
          </strong>
        </div>

        <div>
          <span>Brier score</span>
          <strong>
            {modelEvaluation.overall.brier_score !== null
              ? Number(modelEvaluation.overall.brier_score).toFixed(4)
              : "N/A"}
          </strong>
        </div>

        <div>
          <span>Log loss</span>
          <strong>
            {modelEvaluation.overall.log_loss !== null
              ? Number(modelEvaluation.overall.log_loss).toFixed(4)
              : "N/A"}
          </strong>
        </div>

        <div>
          <span>ROC AUC</span>
          <strong>
            {modelEvaluation.overall.roc_auc !== null
              ? Number(modelEvaluation.overall.roc_auc).toFixed(4)
              : "N/A"}
          </strong>
        </div>
      </section>
    )}

    {methodModelMetricsError && (
  <pre className="error-box">{methodModelMetricsError}</pre>
)}

{methodModelMetrics?.available && methodModelMetrics.metrics && (
  <section className="method-evaluation-grid">
    <div className="evaluation-card">
      <p className="eyebrow">Manner of ending</p>
      <h2>Broad method model</h2>
      <p className="evaluation-card-note">
        Predicts Decision vs KO/TKO vs Submission vs Other.
      </p>

      <div className="method-metric-grid">
        <div>
          <span>Best model</span>
          <strong>
            {formatModelName(methodModelMetrics.metrics.broad.best_model_name)}
          </strong>
        </div>

        <div>
          <span>Accuracy</span>
          <strong>
            {formatMetricPercent(
              methodModelMetrics.metrics.broad.best_metrics?.accuracy
            )}
          </strong>
        </div>

        <div>
          <span>Log loss</span>
          <strong>
            {formatMetricDecimal(
              methodModelMetrics.metrics.broad.best_metrics?.log_loss
            )}
          </strong>
        </div>

        <div>
          <span>Top-2 accuracy</span>
          <strong>
            {formatMetricPercent(
              methodModelMetrics.metrics.broad.best_metrics?.top_2_accuracy
            )}
          </strong>
        </div>

        <div>
          <span>Top-3 accuracy</span>
          <strong>
            {formatMetricPercent(
              methodModelMetrics.metrics.broad.best_metrics?.top_3_accuracy
            )}
          </strong>
        </div>
      </div>
    </div>

    <div className="evaluation-card">
      <p className="eyebrow">Manner of ending</p>
      <h2>Detailed method model</h2>
      <p className="evaluation-card-note">
        Predicts detailed method flavor. Treat this as directional, not exact.
      </p>

      <div className="method-metric-grid">
        <div>
          <span>Best model</span>
          <strong>
            {formatModelName(methodModelMetrics.metrics.detailed.best_model_name)}
          </strong>
        </div>

        <div>
          <span>Accuracy</span>
          <strong>
            {formatMetricPercent(
              methodModelMetrics.metrics.detailed.best_metrics?.accuracy
            )}
          </strong>
        </div>

        <div>
          <span>Log loss</span>
          <strong>
            {formatMetricDecimal(
              methodModelMetrics.metrics.detailed.best_metrics?.log_loss
            )}
          </strong>
        </div>

        <div>
          <span>Top-2 accuracy</span>
          <strong>
            {formatMetricPercent(
              methodModelMetrics.metrics.detailed.best_metrics?.top_2_accuracy
            )}
          </strong>
        </div>

        <div>
          <span>Top-3 accuracy</span>
          <strong>
            {formatMetricPercent(
              methodModelMetrics.metrics.detailed.best_metrics?.top_3_accuracy
            )}
          </strong>
        </div>
      </div>
    </div>
  </section>
)}

    {modelEvaluation && (
      <section className="evaluation-grid">
        <div className="evaluation-card">
  <h2>Favorite threshold performance</h2>
  <p className="evaluation-card-note">
    Cumulative accuracy for fights where the model favorite reached at least this
    confidence level.
  </p>

  <div className="evaluation-table">
    {modelEvaluation.by_favorite_threshold?.map((row) => (
      <div className="evaluation-threshold-row" key={row.name}>
        <div>
          <strong>{row.name}</strong>
          <span>
            {row.fight_count} fights • avg confidence{" "}
            {row.average_confidence_percentage || "N/A"}
          </span>
        </div>

        <div className="threshold-record">
          <strong>{row.accuracy_percentage || "N/A"}</strong>
          <span>
            {row.correct_count} correct / {row.wrong_count} wrong
          </span>
        </div>
      </div>
    ))}
  </div>
</div>
        <div className="evaluation-card">
  <h2>By confidence bucket</h2>
  <p className="evaluation-card-note">
    Calibration gap compares actual accuracy against average model confidence.
    Near 0 is better.
  </p>

  <div className="evaluation-calibration-list">
    {modelEvaluation.by_confidence_bucket?.map((row) => {
      const calibrationClass = getCalibrationClass(row);
      const sampleClass = getSampleSizeClass(row.fight_count);

      return (
        <div className="evaluation-calibration-row" key={row.name}>
          <div>
            <strong>{row.name}</strong>
            <span>
              {row.fight_count} fights • avg confidence{" "}
              {row.average_confidence_percentage || "N/A"}
            </span>
          </div>

          <div>
            <span>Accuracy</span>
            <strong>{row.accuracy_percentage || "N/A"}</strong>
          </div>

          <div>
            <span>Calibration gap</span>
            <strong className={`calibration-gap ${calibrationClass}`}>
              {formatCalibrationGap(row)}
            </strong>
          </div>

          <span className={`sample-badge ${sampleClass}`}>
            {getSampleSizeLabel(row.fight_count)}
          </span>
        </div>
      );
    })}
  </div>
</div>

<div className="evaluation-card">
  <h2>By weight class</h2>

  <div className="evaluation-table">
    {modelEvaluation.by_weight_class?.map((row) => {
      const sampleClass = getSampleSizeClass(row.fight_count);

      return (
        <div className="evaluation-table-row improved" key={row.name}>
          <div>
            <strong>{row.name || "Unknown"}</strong>
            <span>{row.fight_count} fights</span>
          </div>

          <div className="evaluation-mini-result">
            <strong>{row.accuracy_percentage || "N/A"}</strong>
            <span className={`sample-badge ${sampleClass}`}>
              {getSampleSizeLabel(row.fight_count)}
            </span>
          </div>
        </div>
      );
    })}
  </div>
</div>

        <div className="evaluation-card">
  <h2>By year</h2>

  <div className="evaluation-table">
    {modelEvaluation.by_year?.map((row) => {
      const sampleClass = getSampleSizeClass(row.fight_count);

      return (
        <div className="evaluation-table-row improved" key={row.name}>
          <div>
            <strong>{row.name || "Unknown"}</strong>
            <span>{row.fight_count} fights</span>
          </div>

          <div className="evaluation-mini-result">
            <strong>{row.accuracy_percentage || "N/A"}</strong>
            <span className={`sample-badge ${sampleClass}`}>
              {getSampleSizeLabel(row.fight_count)}
            </span>
          </div>
        </div>
      );
    })}
  </div>
</div>
      </section>
    )}

{modelEvaluation && (
  <section className="evaluation-confidence-review-grid">
    <div className="evaluation-card">
      <h2>Most confident correct picks</h2>

      <div className="evaluation-compact-prediction-list">
        {modelEvaluation.most_confident_correct?.map((prediction, index) => (
          <div
            className="evaluation-compact-prediction-row correct"
            key={`correct-${prediction.event_date}-${prediction.fighter_a}-${prediction.fighter_b}-${index}`}
          >
            <div>
              <strong>
                {prediction.fighter_a} vs {prediction.fighter_b}
              </strong>
              <span>
                {prediction.event_date} • {prediction.weight_class}
              </span>
            </div>

            <div>
              <span>Predicted</span>
              <strong>{prediction.predicted_winner}</strong>
            </div>

            <div>
              <span>Confidence</span>
              <strong>{prediction.confidence_percentage}</strong>
            </div>
          </div>
        ))}
      </div>
    </div>

    <div className="evaluation-card">
      <h2>Most confident wrong picks</h2>

      <div className="evaluation-compact-prediction-list">
        {modelEvaluation.most_confident_wrong?.map((prediction, index) => (
          <div
            className="evaluation-compact-prediction-row incorrect"
            key={`wrong-${prediction.event_date}-${prediction.fighter_a}-${prediction.fighter_b}-${index}`}
          >
            <div>
              <strong>
                {prediction.fighter_a} vs {prediction.fighter_b}
              </strong>
              <span>
                {prediction.event_date} • {prediction.weight_class}
              </span>
            </div>

            <div>
              <span>Predicted</span>
              <strong>{prediction.predicted_winner}</strong>
            </div>

            <div>
              <span>Actual</span>
              <strong>{prediction.actual_winner}</strong>
            </div>

            <div>
              <span>Confidence</span>
              <strong>{prediction.confidence_percentage}</strong>
            </div>
          </div>
        ))}
      </div>
    </div>
  </section>
)}

    {modelEvaluation?.recent_predictions && (
      <section className="evaluation-card">
        <h2>Recent tested predictions</h2>

        <div className="evaluation-prediction-list">
          {modelEvaluation.recent_predictions.map((prediction, index) => (
            <div
              className={
                prediction.prediction_correct
                  ? "evaluation-prediction-row correct"
                  : "evaluation-prediction-row incorrect"
              }
              key={`${prediction.event_date}-${prediction.fighter_a}-${prediction.fighter_b}-${index}`}
            >
              <div>
                <strong>
                  {prediction.fighter_a} vs {prediction.fighter_b}
                </strong>
                <span>
                  {prediction.event_date} • {prediction.weight_class}
                </span>
              </div>

              <div>
                <span>Predicted</span>
                <strong>{prediction.predicted_winner}</strong>
              </div>

              <div>
                <span>Actual</span>
                <strong>{prediction.actual_winner}</strong>
              </div>

              <div>
                <span>Confidence</span>
                <strong>{prediction.confidence_percentage}</strong>
              </div>

              <span
                className={
                  prediction.prediction_correct
                    ? "status-badge correct"
                    : "status-badge incorrect"
                }
              >
                {prediction.prediction_correct ? "Correct" : "Wrong"}
              </span>
            </div>
          ))}
        </div>
      </section>
    )}
  </section>
)}

      {activeView === "update" && (
        <section className="update-layout">
          <section className="update-card warning-card">
            <p className="eyebrow">Incremental update</p>
            <h2>Update data and retrain model</h2>
            <p>
              This updates completed events, scrapes only missing fight details,
              rebuilds features, retrains the calibrated model, rebuilds current fighter
              features, refreshes future cards, and saves future-card predictions.
            </p>
            <p>
              Most updates should be much faster than a full rebuild, but it can still
              take several minutes if new fights are available.
            </p>

            <button
              className="primary-button"
              type="button"
              onClick={startIncrementalUpdate}
              disabled={updateLoading || updateStatus?.running}
            >
              {updateStatus?.running ? "Update running..." : "Start incremental update"}
            </button>

            {updateError && <pre className="error-box">{updateError}</pre>}
          </section>

          <section className="update-card">
            <h2>Update progress</h2>

            <div className="progress-header">
              <strong>{updateStatus?.progress_percent ?? 0}%</strong>
              <span>
                Stage {updateStatus?.current_stage_index ?? 0} of{" "}
                {updateStatus?.total_stages ?? 12}
              </span>
            </div>

            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{
                  width: `${updateStatus?.progress_percent ?? 0}%`,
                }}
              />
            </div>

            <div className="update-status-grid">
              <div>
                <span>Status</span>
                <strong>{updateStatus?.running ? "Running" : "Idle"}</strong>
              </div>

              <div>
                <span>Current stage</span>
                <strong>{updateStatus?.current_stage ?? "None"}</strong>
              </div>

              <div>
                <span>Message</span>
                <strong>{updateStatus?.message ?? "No status yet."}</strong>
              </div>

              <div>
                <span>Last result</span>
                <strong>
                  {updateStatus?.success === true
                    ? "Success"
                    : updateStatus?.success === false
                      ? "Failed"
                      : "Not finished"}
                </strong>
              </div>
            </div>
          </section>

          <section className="update-card report-card">
  <div className="report-header">
    <div>
      <p className="eyebrow">Last update report</p>
      <h2>Update summary</h2>
    </div>

    <button type="button" onClick={loadLatestReport}>
      Reload report
    </button>
  </div>

  {!latestReport?.available && (
    <div className="empty-state compact">
      <h2>No report yet</h2>
      <p>{latestReport?.message ?? "Run an update to generate a report."}</p>
    </div>
  )}

  {latestReport?.available && latestReportSummary && (
    <>
      <div
        className={
          latestReportSummary.success
            ? "update-result-banner success"
            : "update-result-banner failed"
        }
      >
        <div>
          <strong>
            {latestReportSummary.success
              ? "Latest update completed successfully"
              : "Latest update finished with failures"}
          </strong>

          <span>
            Started {latestReportStartedAt || "N/A"} • Finished{" "}
            {latestReportFinishedAt || "N/A"} • Duration{" "}
            {formatDuration(latestReportDuration)}
          </span>
        </div>
      </div>

      <div className="update-summary-grid">
        <div>
          <span>Completed events</span>
          <strong>{formatNumber(latestReportSummary.completed_events_rows)}</strong>
        </div>

        <div>
          <span>Event fights</span>
          <strong>{formatNumber(latestReportSummary.event_fights_rows)}</strong>
        </div>

        <div>
          <span>Fight stat rows</span>
          <strong>{formatNumber(latestReportSummary.fight_stats_rows)}</strong>
        </div>

        <div>
          <span>Current fighters</span>
          <strong>{formatNumber(latestReportSummary.current_fighter_features_rows)}</strong>
        </div>

        <div>
          <span>Upcoming events</span>
          <strong>{formatNumber(latestReportSummary.upcoming_events_rows)}</strong>
        </div>

        <div>
          <span>Upcoming fights</span>
          <strong>{formatNumber(latestReportSummary.upcoming_fights_rows)}</strong>
        </div>

        <div>
          <span>Saved predictions</span>
          <strong>{formatNumber(latestReportSummary.saved_card_predictions_rows)}</strong>
        </div>

        <div>
          <span>Training rows</span>
          <strong>{formatNumber(latestReportSummary.training_matchups_rows)}</strong>
        </div>
      </div>

      <div className="update-detail-grid">
        <div className="update-detail-card">
          <h3>Fight stats update</h3>

          <div className="detail-row">
            <span>Missing fights checked</span>
            <strong>{formatNumber(fightStatsUpdateDetails.missing_fights_checked)}</strong>
          </div>

          <div className="detail-row">
            <span>Fights scraped</span>
            <strong>{formatNumber(fightStatsUpdateDetails.missing_fights_scraped)}</strong>
          </div>

          <div className="detail-row">
            <span>Skipped fights</span>
            <strong>{formatNumber(fightStatsUpdateDetails.skipped_fight_count)}</strong>
          </div>

          <div className="detail-row">
            <span>New stat rows</span>
            <strong>{formatNumber(fightStatsUpdateDetails.new_fighter_stat_rows)}</strong>
          </div>
        </div>

        <div className="update-detail-card">
          <h3>Model training</h3>

          <div className="detail-row">
            <span>Best model</span>
            <strong>{trainModelDetails.best_model_name || "N/A"}</strong>
          </div>

          <div className="detail-row">
            <span>Fight accuracy</span>
            <strong>
              {trainModelDetails.best_model_metrics?.accuracy !== undefined
                ? `${(trainModelDetails.best_model_metrics.accuracy * 100).toFixed(1)}%`
                : "N/A"}
            </strong>
          </div>

          <div className="detail-row">
            <span>Brier score</span>
            <strong>
              {trainModelDetails.best_model_metrics?.brier_score !== undefined
                ? Number(trainModelDetails.best_model_metrics.brier_score).toFixed(4)
                : "N/A"}
            </strong>
          </div>

          <div className="detail-row">
            <span>Log loss</span>
            <strong>
              {trainModelDetails.best_model_metrics?.log_loss !== undefined
                ? Number(trainModelDetails.best_model_metrics.log_loss).toFixed(4)
                : "N/A"}
            </strong>
          </div>
        </div>

        <div className="update-detail-card">
          <h3>Future cards</h3>

          <div className="detail-row">
            <span>Upcoming events</span>
            <strong>{formatNumber(refreshFutureCardsDetails.events)}</strong>
          </div>

          <div className="detail-row">
            <span>Upcoming fights</span>
            <strong>{formatNumber(refreshFutureCardsDetails.fights)}</strong>
          </div>

          <div className="detail-row">
            <span>Cards saved</span>
            <strong>{formatNumber(saveFuturePredictionsDetails.cards_saved)}</strong>
          </div>

          <div className="detail-row">
            <span>Prediction rows saved</span>
            <strong>{formatNumber(saveFuturePredictionsDetails.total_rows)}</strong>
          </div>
        </div>
      </div>

      {fightStatsUpdateDetails.skipped_fights?.length > 0 && (
        <div className="skipped-fights-card">
          <h3>Skipped fights</h3>
          <p>
            These fights were detected but skipped because complete stat tables were
            unavailable.
          </p>

          <div className="skipped-fight-list">
            {fightStatsUpdateDetails.skipped_fights.slice(0, 8).map((fight, index) => (
              <div key={`${fight.fight_url}-${index}`}>
                <strong>
                  {fight.fighter_1} vs {fight.fighter_2}
                </strong>
                <span>{fight.reason}</span>
              </div>
            ))}
          </div>

          {fightStatsUpdateDetails.skipped_fights.length > 8 && (
            <p>
              Showing 8 of {fightStatsUpdateDetails.skipped_fights.length} skipped
              fights.
            </p>
          )}
        </div>
      )}

      {latestReportSummary.failed_stages?.length > 0 && (
        <pre className="error-box">
          Failed stages: {latestReportSummary.failed_stages.join(", ")}
        </pre>
      )}
    </>
  )}
</section>
        </section>
      )}
    </main>
  );
}

export default App;