import { FighterName } from "./FighterDisplay";
import FightOddsComparison from "./FightOddsComparison";

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

function getProbabilityWidth(probability) {
  if (!Number.isFinite(probability)) {
    return "0%";
  }

  return `${Math.max(0, Math.min(100, probability * 100))}%`;
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

export default function RecentFightDetails({ fight, fighterImageLookup = {} }) {
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
            <h3>
              <FighterName
                name={fight.fighter_1}
                imageLookup={fighterImageLookup}
                size="xl"
              />
            </h3>
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
            <h3>
              <FighterName
                name={fight.fighter_2}
                imageLookup={fighterImageLookup}
                size="xl"
              />
            </h3>
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
