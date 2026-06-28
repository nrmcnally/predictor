import { clampProbability } from "../lib/format.js";
import { FighterName } from "./FighterDisplay.jsx";
import { SectionCard, SplitBar, Tag, MeterBar } from "./ui.jsx";

function riskTone(severity = "") {
  if (severity === "high") {
    return "loss";
  }

  if (severity === "medium") {
    return "warn";
  }

  return "neutral";
}

function formatEdgeDifference(edge) {
  if (edge.difference === null || edge.difference === undefined) {
    return "Unknown";
  }

  const sign = edge.difference > 0 ? "+" : "";
  const value = Number(edge.difference).toFixed(2);

  return edge.unit ? `${sign}${value} ${edge.unit}` : `${sign}${value}`;
}

export function VerdictCard({ prediction, imageLookup = {}, onFighterClick }) {
  if (!prediction) {
    return null;
  }

  const winnerIsA = prediction.predicted_winner === prediction.fighter_a;

  return (
    <SectionCard className="verdict-card" eyebrow="Model verdict" title={null}>
      <div className="verdict-winner">
        <p className="eyebrow">Predicted winner</p>
        <h2 className={`verdict-name ${winnerIsA ? "corner-red" : "corner-blue"}`}>
          <FighterName
            name={prediction.predicted_winner}
            imageLookup={imageLookup}
            size="lg"
            corner={winnerIsA ? "red" : "blue"}
            onClick={onFighterClick}
          />
        </h2>
        <div className="verdict-confidence">
          <strong className="big-number">{prediction.confidence_percentage}</strong>
          <Tag tone="confidence">{prediction.confidence_label}</Tag>
          {prediction.data_reliability &&
            prediction.data_reliability.level !== "ok" && (
              <Tag
                tone={
                  prediction.data_reliability.level === "very_limited" ? "loss" : "warn"
                }
              >
                {prediction.data_reliability.label}
              </Tag>
            )}
        </div>
      </div>

      <SplitBar
        left={clampProbability(prediction.fighter_a_probability)}
        leftLabel={`${prediction.fighter_a} · ${prediction.fighter_a_percentage}`}
        rightLabel={`${prediction.fighter_b_percentage} · ${prediction.fighter_b}`}
      />

      {prediction.data_reliability?.note && (
        <p className="dim-note verdict-data-note">{prediction.data_reliability.note}</p>
      )}
    </SectionCard>
  );
}

export function RiskFlagsCard({ prediction, compact = false }) {
  const flags = prediction?.risk_flags ?? [];
  const dataQuality = prediction?.data_quality;

  if (!dataQuality && !flags.length) {
    return null;
  }

  if (compact) {
    return (
      <div className="tag-row risk-flag-row">
        {flags.length === 0 && <Tag tone="win">Clean data context</Tag>}
        {flags.slice(0, 3).map((flag) => (
          <Tag key={`${flag.code}-${flag.fighter || flag.label}`} tone={riskTone(flag.severity)}>
            {flag.label}
          </Tag>
        ))}
        {flags.length > 3 && <Tag tone="neutral">+{flags.length - 3} more</Tag>}
      </div>
    );
  }

  return (
    <SectionCard
      eyebrow="Prediction context"
      title={
        flags.length
          ? `${flags.length} caution ${flags.length === 1 ? "flag" : "flags"}`
          : "Clean data context"
      }
      description="These flags do not change the pick; they identify where the prediction may be fragile."
    >
      <div className="risk-summary-grid">
        {dataQuality?.fighters?.map((fighter) => (
          <div className="risk-fighter-summary" key={fighter.fighter}>
            <strong>{fighter.fighter}</strong>
            <span>{fighter.prior_fights} UFC fights</span>
            <span>{fighter.activity_status}</span>
          </div>
        ))}
      </div>

      <div className="risk-flag-list">
        {flags.length === 0 && (
          <p className="dim-note">
            No low-sample, long-layoff, missing-data, or weight-class movement flags
            were found.
          </p>
        )}
        {flags.map((flag) => (
          <div className={`risk-flag-item severity-${flag.severity}`} key={`${flag.code}-${flag.fighter || flag.label}`}>
            <Tag tone={riskTone(flag.severity)}>{flag.label}</Tag>
            <span>{flag.description}</span>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

export function InsightsCard({ prediction }) {
  const insights = prediction?.matchup_insights;

  if (!insights) {
    return null;
  }

  const predictedKey =
    prediction.predicted_winner === prediction.fighter_a ? "fighter_a" : "fighter_b";
  const opponentKey = predictedKey === "fighter_a" ? "fighter_b" : "fighter_a";

  const predicted = insights[predictedKey];
  const opponent = insights[opponentKey];

  if (!predicted || !opponent) {
    return null;
  }

  const predictedConcernLabels = new Set(
    predicted.concerns?.map((item) => item.edge_label) ?? []
  );

  const opponentUniquePaths =
    opponent.strengths?.filter((item) => !predictedConcernLabels.has(item.edge_label)) ?? [];

  return (
    <SectionCard
      eyebrow="Rule-based explanation"
      title="Matchup breakdown"
      description="Built from the same pre-fight edge data the model sees — not the model's literal internals."
    >
      <div className="insight-summary">
        {insights.summary?.map((item, index) => (
          <Tag key={index} tone={item.type === "positive" ? "win" : "warn"}>
            {item.text}
          </Tag>
        ))}
      </div>

      <div className="insight-columns">
        <div className="insight-col">
          <h3 className="insight-heading support">Support for {prediction.predicted_winner}</h3>
          {predicted.strengths?.length === 0 && (
            <p className="dim-note">No major rule-based support edges found.</p>
          )}
          {predicted.strengths?.map((item, index) => (
            <div className={`insight-item severity-${item.severity}`} key={`strength-${index}`}>
              <strong>{item.title}</strong>
              <span>{item.description}</span>
            </div>
          ))}
        </div>

        <div className="insight-col">
          <h3 className="insight-heading caution">Reasons to be cautious</h3>
          {predicted.concerns?.length === 0 && (
            <p className="dim-note">No major rule-based concerns found for the pick.</p>
          )}
          {predicted.concerns?.map((item, index) => (
            <div
              className={`insight-item concern severity-${item.severity}`}
              key={`concern-${index}`}
            >
              <strong>{item.title}</strong>
              <span>{item.description}</span>
            </div>
          ))}
        </div>

        <div className="insight-col">
          <h3 className="insight-heading path">Opponent's unique path</h3>
          {opponentUniquePaths.length === 0 && (
            <p className="dim-note">
              The opponent's biggest edges are already covered by the caution column.
            </p>
          )}
          {opponentUniquePaths.map((item, index) => (
            <div className={`insight-item severity-${item.severity}`} key={`path-${index}`}>
              <strong>{item.title}</strong>
              <span>{item.description}</span>
            </div>
          ))}
        </div>
      </div>
    </SectionCard>
  );
}

export function EdgesCard({ prediction }) {
  const edges = prediction?.basic_matchup_edges;

  if (!edges?.length) {
    return null;
  }

  return (
    <SectionCard
      eyebrow="Tale of the tape"
      title="Basic matchup edges"
      description={`Positive values favor ${prediction.fighter_a}; negative values favor ${prediction.fighter_b}.`}
    >
      <div className="edges-list">
        {edges.map((edge) => {
          const direction =
            edge.difference > 0 ? "red" : edge.difference < 0 ? "blue" : "even";

          return (
            <div className="edge-row" key={edge.label}>
              <span className="edge-label">{edge.label}</span>
              <span className={`edge-value corner-${direction}`}>
                {formatEdgeDifference(edge)}
              </span>
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}

export function MethodCard({ methodPrediction, loading, error }) {
  if (loading) {
    return (
      <SectionCard eyebrow="Manner of ending" title="Method probabilities">
        <p className="dim-note">Loading method probabilities…</p>
      </SectionCard>
    );
  }

  if (error) {
    return (
      <SectionCard eyebrow="Manner of ending" title="Method prediction unavailable">
        <p className="dim-note">{error}</p>
      </SectionCard>
    );
  }

  if (!methodPrediction) {
    return null;
  }

  return (
    <SectionCard
      eyebrow="Manner of ending"
      title={`Most likely: ${methodPrediction.predicted_broad_method} ${methodPrediction.predicted_broad_method_percentage}`}
      description={`Detailed lean: ${methodPrediction.predicted_detailed_method} ${methodPrediction.predicted_detailed_method_percentage}`}
    >
      <div className="method-grid">
        <div>
          <h3 className="mini-heading">Broad method</h3>
          {methodPrediction.broad_method_probabilities?.map((row) => (
            <MeterBar
              key={row.label}
              value={clampProbability(row.probability)}
              tone="gold"
              label={row.label}
              trail={row.percentage}
            />
          ))}
        </div>

        <div>
          <h3 className="mini-heading">Detailed method</h3>
          {methodPrediction.detailed_method_probabilities?.map((row) => (
            <MeterBar
              key={row.label}
              value={clampProbability(row.probability)}
              tone="violet"
              label={row.label}
              trail={row.percentage}
            />
          ))}
        </div>
      </div>

      {methodPrediction.model_note && (
        <p className="dim-note">{methodPrediction.model_note}</p>
      )}
    </SectionCard>
  );
}
