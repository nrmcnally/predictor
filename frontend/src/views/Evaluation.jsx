import { useEffect, useState } from "react";
import {
  getClvEvaluation,
  getDataQualitySummary,
  getMethodModelMetrics,
  getModelEvaluation,
  getModelMarketEvaluation,
  getModelSnapshotEvaluation,
  getWalkForwardEvaluation,
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

  if (evaluation.summary?.scored_fights) {
    const summary = evaluation.summary;

    return [
      {
        model_name: "model",
        display_name: "Model",
        scored_fights: summary.scored_fights,
        accuracy: summary.model_accuracy,
        accuracy_percentage: summary.model_accuracy_percentage,
        average_confidence: summary.average_model_confidence,
      },
      {
        model_name: "market_favorite",
        display_name: "Market favorite",
        scored_fights: summary.scored_fights,
        accuracy: summary.market_accuracy,
        accuracy_percentage: summary.market_accuracy_percentage,
        average_confidence: summary.average_market_confidence,
      },
    ];
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

function isExperimentalModel(row) {
  return String(row?.model_name || "").startsWith("shadow_");
}

function formatCountWithPercent(count, percent) {
  const countText = formatNumber(count);

  if (!percent || percent === "N/A") {
    return countText;
  }

  return `${countText} (${percent})`;
}

function MarketCoverageNote({ evaluation }) {
  const summary = evaluation?.summary || {};
  const allScored = Number(summary.all_scored_prediction_fights);
  const withOdds = Number(summary.scored_with_market_odds ?? summary.scored_fights);
  const excluded = Number(summary.excluded_without_market_odds);

  if (!Number.isFinite(allScored) || !Number.isFinite(withOdds)) {
    return null;
  }

  if (!Number.isFinite(excluded) || excluded <= 0) {
    return (
      <p className="dim-note">
        This market table uses saved Recent Cards predictions. All{" "}
        {formatNumber(withOdds)} completed Recent Cards predictions have saved
        odds snapshots.
      </p>
    );
  }

  return (
    <p className="dim-note">
      This market table uses saved Recent Cards predictions. It scores{" "}
      {formatNumber(withOdds)} of {formatNumber(allScored)} completed Recent
      Cards predictions;{" "}
      {formatNumber(excluded)} {excluded === 1 ? "fight is" : "fights are"} excluded
      because no market odds snapshot was saved.
    </p>
  );
}

function ModelComparisonTable({
  evaluation,
  scoredColumnLabel = "Scored fights",
  showExperimental = true,
  children,
}) {
  const allRows = modelRows(evaluation);
  const hiddenExperimentalCount = allRows.filter(isExperimentalModel).length;
  const rows = showExperimental
    ? allRows
    : allRows.filter((row) => !isExperimentalModel(row));

  if (!allRows.length) {
    return <p className="dim-note">{evaluation?.message || "No comparison data yet."}</p>;
  }

  return (
    <>
      {evaluation?.message && <p className="dim-note">{evaluation.message}</p>}
      {children}
      {!showExperimental && hiddenExperimentalCount > 0 && (
        <p className="dim-note">
          Hiding {formatNumber(hiddenExperimentalCount)} experimental model{" "}
          {hiddenExperimentalCount === 1 ? "row" : "rows"}.
        </p>
      )}
      {!rows.length && (
        <p className="dim-note">Only experimental model rows are available.</p>
      )}
      <table className="data-table">
        <thead>
          <tr>
            <th>Model</th>
            <th>{scoredColumnLabel}</th>
            <th>Accuracy</th>
            <th>Brier</th>
            <th>Log loss</th>
            <th>Avg conf</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isExperimental = isExperimentalModel(row);

            return (
              <tr key={row.model_name}>
                <td>
                  {row.display_name || formatModelName(row.model_name)}{" "}
                  {row.is_current_best_model && <Tag tone="gold">current</Tag>}
                  {isExperimental && <Tag tone="neutral">experimental</Tag>}
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
            );
          })}
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

function DataQualityCard({ summary }) {
  if (!summary) {
    return <p className="dim-note">Loading data quality summary...</p>;
  }

  if (!summary.available) {
    return (
      <p className="dim-note">
        {summary.message || "Data quality summary is not available yet."}
      </p>
    );
  }

  const fighters = summary.fighters || {};
  const futureCards = summary.future_cards || {};
  const saved = summary.saved_predictions || {};
  const historical = summary.historical_results || {};
  const missingFighters = saved.top_unavailable_fighters || [];

  return (
    <div className="quality-stack">
      <div className="tile-row four">
        <StatTile
          label="Current fighters"
          value={formatNumber(fighters.total)}
          hint={`${formatNumber(fighters.missing_reach)} missing reach`}
        />
        <StatTile
          label="Thin UFC samples"
          value={formatCountWithPercent(
            fighters.low_sample_under_5_fights,
            fighters.low_sample_under_5_fights_percentage
          )}
          tone="warn"
          hint="Under 5 prior UFC fights"
        />
        <StatTile
          label="Saved predictions"
          value={saved.prediction_coverage_percentage || "N/A"}
          tone="gold"
          hint={`${formatNumber(saved.prediction_available)} of ${formatNumber(
            saved.saved_card_rows
          )} rows available`}
        />
        <StatTile
          label="Saved odds"
          value={saved.odds_coverage_percentage || "N/A"}
          hint={`${formatNumber(saved.odds_available)} saved prediction rows`}
        />
      </div>

      <div className="quality-grid">
        <div className="subcard">
          <h3 className="mini-heading">Prediction availability</h3>
          <div className="kv-grid">
            <div className="kv-row">
              <span>Unavailable predictions</span>
              <strong className="mono">{formatNumber(saved.prediction_unavailable)}</strong>
            </div>
            <div className="kv-row">
              <span>Upcoming fights</span>
              <strong className="mono">{formatNumber(futureCards.upcoming_fights)}</strong>
            </div>
            <div className="kv-row">
              <span>Future odds coverage</span>
              <strong className="mono">
                {futureCards.odds_coverage_percentage || "N/A"}
              </strong>
            </div>
          </div>
          {missingFighters.length > 0 && (
            <div className="quality-list">
              {missingFighters.map((item) => (
                <Tag key={item.fighter} tone="warn">
                  {item.fighter} x{formatNumber(item.count)}
                </Tag>
              ))}
            </div>
          )}
        </div>

        <div className="subcard">
          <h3 className="mini-heading">Result edge cases</h3>
          <div className="kv-grid">
            <div className="kv-row">
              <span>Historical fights</span>
              <strong className="mono">{formatNumber(historical.event_fights)}</strong>
            </div>
            <div className="kv-row">
              <span>Clear win/loss rows</span>
              <strong className="mono">{formatNumber(historical.clear_win_loss)}</strong>
            </div>
            <div className="kv-row">
              <span>Draws / no contests</span>
              <strong className="mono">
                {formatNumber(
                  Number(historical.draws || 0) + Number(historical.no_contests || 0)
                )}
              </strong>
            </div>
            <div className="kv-row">
              <span>DQ or overturned methods</span>
              <strong className="mono">{formatNumber(historical.dq_or_overturned)}</strong>
            </div>
          </div>
        </div>
      </div>

      <p className="dim-note">
        These diagnostics do not change predictions. They flag thin UFC samples,
        stale fighter profiles, missing fighters, sparse odds, and result quirks that
        can make evaluation or confidence less trustworthy.
      </p>
    </div>
  );
}

function meanWithCi(stat, asPercent = true) {
  if (!stat || stat.mean === null || stat.mean === undefined) {
    return "N/A";
  }

  if (asPercent) {
    const mean = (Number(stat.mean) * 100).toFixed(1);
    const ci = stat.ci95 ? ` ±${(Number(stat.ci95) * 100).toFixed(1)}` : "";
    return `${mean}%${ci}`;
  }

  const mean = Number(stat.mean).toFixed(3);
  const ci = stat.ci95 ? ` ±${Number(stat.ci95).toFixed(3)}` : "";
  return `${mean}${ci}`;
}

function signedPoints(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "N/A";
  }
  const points = Number(value) * 100;
  return `${points >= 0 ? "+" : ""}${points.toFixed(1)} pts`;
}

function WalkForwardCard({ payload, loading, error, hasRun, onRun }) {
  const aggregate = payload?.aggregate;
  const folds = payload?.folds || [];
  const metadata = payload?.metadata;
  const beatsElo = aggregate?.model_minus_elo_accuracy;
  const beatsEloTone =
    beatsElo && beatsElo.mean !== null
      ? beatsElo.mean - (beatsElo.ci95 || 0) > 0
        ? "win"
        : beatsElo.mean > 0
          ? "warn"
          : "loss"
      : "neutral";

  return (
    <>
      {error && <ErrorNote message={error} />}

      {!hasRun && !loading && (
        <p className="dim-note">
          Retrains the production model type ({"“"}
          {metadata?.model_type || "winner model"}
          {"”"}) once per recent year on an expanding window and scores each year
          out-of-sample. This trains throwaway models, so it can take a few seconds.
        </p>
      )}

      <div style={{ marginBottom: "1rem" }}>
        <button type="button" className="btn btn-primary" onClick={onRun} disabled={loading}>
          {loading ? "Backtesting…" : hasRun ? "Re-run backtest" : "Run backtest"}
        </button>
      </div>

      {loading && <Spinner label="Retraining across folds…" />}

      {payload && payload.available === false && (
        <p className="dim-note">{payload.message || "Not enough history for folds yet."}</p>
      )}

      {aggregate && folds.length > 0 && (
        <>
          <div className="tile-row six">
            <StatTile
              label="Mean accuracy"
              value={meanWithCi(aggregate.accuracy)}
              tone="gold"
              hint={`${folds.length} yearly folds, 95% CI`}
            />
            <StatTile label="Mean Brier" value={meanWithCi(aggregate.brier_score, false)} />
            <StatTile label="Mean log loss" value={meanWithCi(aggregate.log_loss, false)} />
            <StatTile label="Mean ROC AUC" value={meanWithCi(aggregate.roc_auc, false)} />
            <StatTile
              label="Beats Elo by"
              value={meanWithCi(beatsElo)}
              tone={beatsEloTone === "win" ? "gold" : undefined}
              hint="Accuracy vs Elo-only baseline"
            />
            <StatTile
              label="Model type"
              value={metadata?.calibration_method && metadata.calibration_method !== "none" ? "Calibrated" : "Raw"}
              hint={formatModelName(metadata?.model_type || "")}
            />
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>Test year</th>
                <th>Train fights</th>
                <th>Test fights</th>
                <th>Accuracy</th>
                <th>Brier</th>
                <th>Log loss</th>
                <th>ROC AUC</th>
                <th>Elo acc</th>
                <th>vs Elo</th>
              </tr>
            </thead>
            <tbody>
              {folds.map((fold) => (
                <tr key={fold.test_year}>
                  <td className="mono">{fold.test_year}</td>
                  <td className="mono">{formatNumber(fold.train_fights)}</td>
                  <td className="mono">{formatNumber(fold.test_fights)}</td>
                  <td className="mono">{formatPercent(fold.accuracy)}</td>
                  <td className="mono">{formatDecimal(fold.brier_score)}</td>
                  <td className="mono">{formatDecimal(fold.log_loss)}</td>
                  <td className="mono">{formatDecimal(fold.roc_auc)}</td>
                  <td className="mono">{formatPercent(fold.elo_baseline_accuracy)}</td>
                  <td>
                    <Tag
                      tone={
                        fold.model_minus_elo_accuracy > 0
                          ? "win"
                          : fold.model_minus_elo_accuracy < 0
                            ? "loss"
                            : "neutral"
                      }
                    >
                      {signedPoints(fold.model_minus_elo_accuracy)}
                    </Tag>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {metadata?.metric_note && <p className="dim-note">{metadata.metric_note}</p>}
        </>
      )}
    </>
  );
}

function ProspectiveCalibration({ evaluation }) {
  const buckets = (evaluation?.prospective_calibration || []).filter((b) => b.count > 0);

  if (!buckets.length) {
    return (
      <p className="dim-note">
        No completed saved predictions to calibrate against yet. This fills in as cards finish.
      </p>
    );
  }

  return (
    <>
      <p className="dim-note">
        Truly out-of-sample reliability for{" "}
        {formatModelName(evaluation.prospective_calibration_model)} on{" "}
        {formatNumber(evaluation.prospective_calibration_fights)} graded saved predictions — the
        most honest calibration check (the model never trained on these), but still a small sample,
        so read it as directional.
      </p>
      <div className="calibration-list">
        {buckets.map((bucket) => {
          const gap =
            bucket.actual != null && bucket.predicted != null
              ? bucket.actual - bucket.predicted
              : null;

          return (
            <div className="calibration-row" key={bucket.bucket}>
              <div className="calibration-head">
                <strong>{bucket.bucket}</strong>
                <span className="muted">{formatNumber(bucket.count)} fights</span>
                <Tag tone={gapTone(gap)}>{bucket.gap_percentage_points}</Tag>
              </div>
              <MeterBar
                value={clampProbability(bucket.actual)}
                tone="gold"
                label="Actually won"
                trail={bucket.actual_percentage}
              />
              <MeterBar
                value={clampProbability(bucket.predicted)}
                tone="violet"
                label="Model said"
                trail={bucket.predicted_percentage}
              />
            </div>
          );
        })}
      </div>
    </>
  );
}

export default function Evaluation() {
  const [recentLimit, setRecentLimit] = useState(25);

  const [evaluation, setEvaluation] = useState(null);
  const [methodMetrics, setMethodMetrics] = useState(null);
  const [marketEvaluation, setMarketEvaluation] = useState(null);
  const [snapshotEvaluation, setSnapshotEvaluation] = useState(null);
  const [clvEvaluation, setClvEvaluation] = useState(null);
  const [dataQuality, setDataQuality] = useState(null);
  const [showExperimentalModels, setShowExperimentalModels] = useState(false);

  const [walkForward, setWalkForward] = useState(null);
  const [walkForwardLoading, setWalkForwardLoading] = useState(false);
  const [walkForwardError, setWalkForwardError] = useState("");
  const [walkForwardHasRun, setWalkForwardHasRun] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadEvaluation() {
    setLoading(true);
    setError("");

    try {
      const data = await getModelEvaluation({ recentLimit });
      setEvaluation(data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadWalkForward() {
    setWalkForwardLoading(true);
    setWalkForwardError("");
    setWalkForwardHasRun(true);

    try {
      const data = await getWalkForwardEvaluation({ nFolds: 8 });
      setWalkForward(data);
    } catch (requestError) {
      setWalkForwardError(requestError.message);
    } finally {
      setWalkForwardLoading(false);
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
    getClvEvaluation().then(setClvEvaluation).catch(() => {});
    getDataQualitySummary().then(setDataQuality).catch(() => {});
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
        eyebrow="Backtest"
        title="Walk-forward evaluation"
        description="Expanding-window backtest: for each recent year, train only on prior fights and score that year out-of-sample. Aggregate metrics include a 95% confidence interval, and each fold is compared to an Elo-only baseline."
      >
        <WalkForwardCard
          payload={walkForward}
          loading={walkForwardLoading}
          error={walkForwardError}
          hasRun={walkForwardHasRun}
          onRun={loadWalkForward}
        />
      </SectionCard>

      <SectionCard
        eyebrow="Data quality"
        title="Coverage and reliability"
        description="A quick audit of the local CSV artifacts that feed predictions and evaluation."
      >
        <DataQualityCard summary={dataQuality} />
      </SectionCard>

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
        description="Compares saved Recent Cards predictions against locally saved pre-event odds snapshots."
      >
        <ModelComparisonTable
          evaluation={marketEvaluation}
          scoredColumnLabel="Scored with odds"
        >
          <MarketCoverageNote evaluation={marketEvaluation} />
        </ModelComparisonTable>
      </SectionCard>

      <SectionCard
        eyebrow="Prospective calibration"
        title="Out-of-sample reliability"
        description="When the model said X% pre-fight, did it actually win ~X%? Computed only on saved predictions that have since completed — so, unlike the holdout above, the model never touched these fights."
      >
        <ProspectiveCalibration evaluation={snapshotEvaluation} />
      </SectionCard>

      <SectionCard
        eyebrow="Closing-line value"
        title="Did the market move toward our picks?"
        description="After the model picks a side, does the betting line drift toward it by close? Beating the closing line is the strongest market-based sign a pick had real value. This accrues only once odds are captured more than once per fight (refresh odds again near fight time)."
      >
        {clvEvaluation?.available && clvEvaluation.scored_clv_fights >= 10 ? (
          <>
            <div className="tile-row four">
              <StatTile
                label="Beat the close"
                value={`${clvEvaluation.beat_close_count}/${clvEvaluation.scored_clv_fights}`}
                hint={clvEvaluation.beat_close_percentage}
                tone={clvEvaluation.beat_close_rate >= 0.5 ? "win" : "loss"}
              />
              <StatTile
                label="Avg CLV"
                value={clvEvaluation.avg_clv_points_display}
                tone={clvEvaluation.avg_clv_points > 0 ? "win" : "loss"}
                hint="line moved toward our pick"
              />
              <StatTile
                label="Fights with movement"
                value={formatNumber(clvEvaluation.scored_clv_fights)}
              />
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Pick</th>
                  <th>Open</th>
                  <th>Close</th>
                  <th>CLV</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {clvEvaluation.fights.map((f) => (
                  <tr key={f.fight_url}>
                    <td>{f.predicted_winner}</td>
                    <td className="mono">{f.opening_percentage}</td>
                    <td className="mono">{f.closing_percentage}</td>
                    <td>
                      <Tag tone={f.beat_close ? "win" : "loss"}>{f.clv_points}</Tag>
                    </td>
                    <td>
                      {f.completed ? (
                        <Tag tone={f.pick_won ? "win" : "loss"}>
                          {f.pick_won ? "Won" : "Lost"}
                        </Tag>
                      ) : (
                        <span className="muted">pending</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="dim-note">
            {clvEvaluation?.available
              ? `CLV needs ${10 - clvEvaluation.scored_clv_fights} more fight${
                  10 - clvEvaluation.scored_clv_fights === 1 ? "" : "s"
                } with line movement before the verdict is meaningful (${
                  clvEvaluation.scored_clv_fights
                }/10 so far).`
              : clvEvaluation?.message || "Loading…"}
          </p>
        )}
      </SectionCard>

      <SectionCard
        eyebrow="Prospective tracking"
        title="Saved snapshot evaluation"
        description="Scores all-model pre-fight snapshots once results arrive; market odds are not required."
        actions={
          <label className="inline-check">
            <input
              type="checkbox"
              checked={showExperimentalModels}
              onChange={(event) => setShowExperimentalModels(event.target.checked)}
            />
            <span>Show experimental models</span>
          </label>
        }
      >
        <ModelComparisonTable
          evaluation={snapshotEvaluation}
          showExperimental={showExperimentalModels}
        >
          <p className="dim-note">
            This table uses all-model snapshot rows, so its scored-fight count
            can differ from the Recent Cards market comparison above.
          </p>
        </ModelComparisonTable>
      </SectionCard>
    </div>
  );
}
