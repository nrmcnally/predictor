import { useMemo } from "react";
import { FighterName } from "./FighterDisplay";

function getProbabilityWidth(probability) {
  if (!Number.isFinite(probability)) {
    return "0%";
  }

  return `${Math.max(0, Math.min(100, probability * 100))}%`;
}

function formatEdgeDifference(edge) {
  if (edge.difference === null || edge.difference === undefined) {
    return "Unknown";
  }

  const sign = edge.difference > 0 ? "+" : "";
  const value = Number(edge.difference).toFixed(2);

  return edge.unit ? `${sign}${value} ${edge.unit}` : `${sign}${value}`;
}

function PredictionDetails({ prediction, showBasicEdges = false, fighterImageLookup = {} }) {
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
        <h2><FighterName name={prediction.predicted_winner} imageLookup={fighterImageLookup} size="lg" /></h2>
        <p>{prediction.confidence_label}</p>
        <strong>{prediction.confidence_percentage}</strong>
      </div>

      <div className="probability-grid">
        <div className={`fighter-result ${winnerSide === "fighter_a" ? "winner" : ""}`}>
          <div className="fighter-result-header">
            <h3><FighterName name={prediction.fighter_a} imageLookup={fighterImageLookup} size="xl" /></h3>
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
            <h3><FighterName name={prediction.fighter_b} imageLookup={fighterImageLookup} size="xl" /></h3>
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

export default PredictionDetails;
