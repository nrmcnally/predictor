import { useEffect, useState } from "react";
import {
  getMethodModelMetrics,
  getModelEvaluation,
  getModelMarketEvaluation,
  getModelSnapshotEvaluation,
} from "../api/client.js";
import {
  ErrorNote,
  MeterBar,
  SectionCard,
  Spinner,
  StatTile,
  Tag,
} from "../components/ui.jsx";
import {
  clampProbability,
  formatDecimal,
  formatModelName,
  formatNumber,
  formatPercent,
} from "../lib/format.js";

function calibrationGap(row) {
  if (
    row?.accuracy === null ||
    row?.accuracy === undefined ||
    row?.average_confidence === null ||
    row?.average_confidence === undefined
  ) {
    return null;
  }

  const gap = Number(row.accuracy) - Number(row.average_confidence);

  return Number.isFinite(gap) ? gap : null;
}

function gapTone(gap) {
  if (gap === null) {
    return "neutral";
  }

  const absolute = Math.abs(gap);

  if (absolute <= 0.05) {
    return "win";
  }

  if (absolute <= 0.1) {
    return "warn";
  }

  return "loss";
}

function SummaryTable({ rows, nameLabel = "Group" }) {
  if (!rows?.length) {
    return <p className="dim-note">No data available.</p>;
  }

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>{nameLabel}</th>
          <th>Fights</th>
          <th>Accuracy</th>
          <th>Avg confidence</th>
          <th>Gap</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const gap = calibrationGap(row);

          return (
            <tr key={row.name}>
              <td>{row.name}</td>
              <td className="mono">{formatNumber(row.fight_count)}</td>
              <td className="mono">{row.accuracy_percentage || "N/A"}</td>
              <td className="mono">{row.average_confidence_percentage || "N/A"}</td>
              <td>
                <Tag tone={gapTone(gap)}>
                  {gap === null ? "N/A" : `${gap >= 0 ? "+" : ""}${(gap * 100).toFixed(1)} pts`}
                </Tag>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function PredictionList({ rows }) {
  if (!rows?.length) {
    return <p className="dim-note">No predictions available.</p>;
  }

  return (
    <div className="prediction-list">
      {rows.map((row, index) => (
        <div
          className={`prediction-item ${row.prediction_correct ? "correct" : "incorrect"}`}
          key={`${row.event_date}-${row.fighter_a}-${index}`}
        >
          <div>
            <strong>
              {row.fighter_a} vs {row.fighter_b}
            </strong>
            <span className="muted">
              {row.event_date} · {row.weight_class}
            </span>
          </div>
          <div className="prediction-item-right">
            <span>
              Pick: <strong>{row.predicted_winner}</strong> ·{" "}
              {row.confidence_percentage}
            </span>
            <Tag tone={row.prediction_correct ? "win" : "loss"}>
              {row.prediction_correct ? "Correct" : "Wrong"}
            </Tag>
          </div>
        </div>
      ))}
    </div>
  );
}

function modelRows(evaluation) {
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

function ModelComparisonTable({ evaluation }) {
  const rows = modelRows(evaluation);

  if (!rows.length) {
    return <p className="dim-note">{evaluation?.message || "No comparison data yet."}</p>;
  }

  return (
    <>
      {evaluation?.message && <p className="dim-note">{evaluation.message}</p>}
      <table className="data-table">
        <thead>
          <tr>
            <th>Model</th>
            <th>Scored fights</th>
            <th>Accuracy</th>
            <th>Brier</th>
            <th>Log loss</th>
            <th>Avg conf</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.model_name}>
              <td>
                {formatModelName(row.model_name)}{" "}
                {row.is_current_best_model && <Tag tone="gold">current</Tag>}
              </td>
              <td className="mono">
                {formatNumber(row.scored_fights ?? row.fight_count)}
              </td>
              <td className="mono">
                {row.accuracy_percentage || formatPercent(row.accuracy)}
              </td>
              <td className="mono">{formatDecimal(row.brier_score)}</td>
              <td className="mono">{formatDecimal(row.log_loss)}</td>
              <td className="mono">
                {row.average_confidence_percentage ||
                  formatPercent(row.average_confidence)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function MethodMetricsCard({ payload }) {
  if (!payload?.available || !payload?.metrics) {
    return (
      <p className="dim-note">
        {payload?.message || "Method model metrics are not available yet."}
      </p>
    );
  }

  const sections = [
    ["Broad method model", payload.metrics.broad],
    ["Detailed method model", payload.metrics.detailed],
  ];

  return (
    <div className="two-col">
      {sections.map(([title, section]) => (
        <div className="subcard" key={title}>
          <h3 className="mini-heading">{title}</h3>
          {!section && <p className="dim-note">Not available.</p>}
          {section && (
            <>
              <p className="muted">
                Best model: <strong>{formatModelName(section.best_model_name)}</strong>
              </p>
              <div className="kv-grid">
                {Object.entries(section.best_metrics || {}).map(([key, value]) => (
                  <div className="kv-row" key={key}>
                    <span>{key.replaceAll("_", " ")}</span>
                    <strong className="mono">
                      {key.includes("accuracy") || key.includes("f1")
                        ? formatPercent(value)
                        : formatDecimal(value, 3)}
                    </strong>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
}

export default function Evaluation() {
  const [testFraction, setTestFraction] = useState(0.2);
  const [recentLimit, setRecentLimit] = useState(25);

  const [evaluation, setEvaluation] = useState(null);
  const [methodMetrics, setMethodMetrics] = useState(null);
  const [marketEvaluation, setMarketEvaluation] = useState(null);
  const [snapshotEvaluation, setSnapshotEvaluation] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadEvaluation() {
    setLoading(true);
    setError("");

    try {
      const data = await getModelEvaluation({ testFraction, recentLimit });
      setEvaluation(data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    async function init() {
      await loadEvaluation();
    }

    init();
    getMethodModelMetrics().then(setMethodMetrics).catch(() => {});
    getModelMarketEvaluation().then(setMarketEvaluation).catch(() => {});
    getModelSnapshotEvaluation().then(setSnapshotEvaluation).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const overall = evaluation?.overall;
  const metadata = evaluation?.metadata;

  return (
    <div className="view evaluation">
      <header className="view-head">
        <div>
          <p className="eyebrow">Model review</p>
          <h1 className="view-title">Evaluation</h1>
        </div>

        <div className="eval-controls">
          <div className="control small">
            <label htmlFor="eval-fraction">Test fraction</label>
            <input
              id="eval-fraction"
              type="number"
              step="0.05"
              min="0.05"
              max="0.5"
              value={testFraction}
              onChange={(event) => setTestFraction(Number(event.target.value) || 0.2)}
            />
          </div>
          <div className="control small">
            <label htmlFor="eval-limit">Recent limit</label>
            <input
              id="eval-limit"
              type="number"
              min="5"
              max="100"
              value={recentLimit}
              onChange={(event) => setRecentLimit(Number(event.target.value) || 25)}
            />
          </div>
          <button
            type="button"
            className="btn btn-primary"
            onClick={loadEvaluation}
            disabled={loading}
          >
            {loading ? "Evaluating…" : "Re-run"}
          </button>
        </div>
      </header>

      <ErrorNote message={error} />

      {loading && !evaluation && <Spinner label="Scoring the holdout set…" />}

      {overall && (
        <>
          <div className="tile-row six">
            <StatTile
              label="Fight accuracy"
              value={overall.accuracy_percentage || "N/A"}
              tone="gold"
              hint={`${formatNumber(overall.fight_count)} holdout fights`}
            />
            <StatTile
              label="Avg confidence"
              value={overall.average_confidence_percentage || "N/A"}
            />
            <StatTile label="Brier score" value={formatDecimal(overall.brier_score)} />
            <StatTile label="Log loss" value={formatDecimal(overall.log_loss)} />
            <StatTile label="ROC AUC" value={formatDecimal(overall.roc_auc)} />
            <StatTile
              label="Holdout window"
              value={metadata?.test_date_min ? "Chronological" : "N/A"}
              hint={
                metadata?.test_date_min
                  ? `${metadata.test_date_min} → ${metadata.test_date_max}`
                  : undefined
              }
            />
          </div>

          {metadata?.metric_note && <p className="dim-note">{metadata.metric_note}</p>}

          <SectionCard
            eyebrow="Calibration"
            title="Accuracy by confidence bucket"
            description="A calibrated model's accuracy should track its stated confidence in each bucket."
          >
            <div className="calibration-list">
              {evaluation.by_confidence_bucket?.map((row) => {
                const gap = calibrationGap(row);

                return (
                  <div className="calibration-row" key={row.name}>
                    <div className="calibration-head">
                      <strong>{row.name}</strong>
                      <span className="muted">
                        {formatNumber(row.fight_count)} fights
                      </span>
                      <Tag tone={gapTone(gap)}>
                        {gap === null
                          ? "N/A"
                          : `${gap >= 0 ? "+" : ""}${(gap * 100).toFixed(1)} pts`}
                      </Tag>
                    </div>
                    <MeterBar
                      value={clampProbability(row.accuracy)}
                      tone="gold"
                      label="Accuracy"
                      trail={row.accuracy_percentage || "N/A"}
                    />
                    <MeterBar
                      value={clampProbability(row.average_confidence)}
                      tone="violet"
                      label="Stated confidence"
                      trail={row.average_confidence_percentage || "N/A"}
                    />
                  </div>
                );
              })}
            </div>
          </SectionCard>

          <div className="two-col">
            <SectionCard eyebrow="Segments" title="By weight class">
              <SummaryTable rows={evaluation.by_weight_class} nameLabel="Weight class" />
            </SectionCard>

            <SectionCard eyebrow="Segments" title="By year">
              <SummaryTable rows={evaluation.by_year} nameLabel="Year" />
            </SectionCard>
          </div>

          <SectionCard eyebrow="Favorites" title="Favorite-threshold performance">
            <SummaryTable rows={evaluation.by_favorite_threshold} nameLabel="Threshold" />
          </SectionCard>

          <div className="two-col">
            <SectionCard eyebrow="Highlights" title="Most confident correct">
              <PredictionList rows={evaluation.most_confident_correct} />
            </SectionCard>

            <SectionCard eyebrow="Lowlights" title="Most confident wrong">
              <PredictionList rows={evaluation.most_confident_wrong} />
            </SectionCard>
          </div>
        </>
      )}

      <SectionCard
        eyebrow="Manner of ending"
        title="Method model metrics"
        description="The method models are directional and less accurate than the winner model."
      >
        <MethodMetricsCard payload={methodMetrics} />
      </SectionCard>

      <SectionCard
        eyebrow="Market comparison"
        title="Model vs market"
        description="Only fights with locally saved pre-event odds snapshots are compared."
      >
        <ModelComparisonTable evaluation={marketEvaluation} />
      </SectionCard>

      <SectionCard
        eyebrow="Prospective tracking"
        title="Saved snapshot evaluation"
        description="Scores saved pre-fight predictions once results arrive — a forward test, not a backtest."
      >
        <ModelComparisonTable evaluation={snapshotEvaluation} />
      </SectionCard>
    </div>
  );
}
