import { useEffect, useMemo, useRef, useState } from "react";
import {
  getLatestUpdateReport,
  getUpdateStatus,
  startIncrementalUpdate,
} from "../api/client.js";
import {
  ErrorNote,
  MeterBar,
  SectionCard,
  StatTile,
  Tag,
} from "../components/ui.jsx";
import { formatDuration, formatModelName, formatNumber } from "../lib/format.js";

function getStageGroup(stageName = "") {
  const name = String(stageName).toLowerCase();

  if (name.includes("prediction")) {
    return "Prediction export";
  }

  if (
    name.includes("model") ||
    name.includes("method") ||
    name.includes("matchup")
  ) {
    return "Model training";
  }

  if (
    name.includes("feature") ||
    name.includes("snapshot") ||
    name.includes("dob") ||
    name.includes("elo") ||
    name.includes("age")
  ) {
    return "Feature prep";
  }

  return "Data refresh";
}

function groupStages(stages = []) {
  const groups = [];

  for (const stage of stages) {
    const title = getStageGroup(stage.name);
    let group = groups.find((item) => item.title === title);

    if (!group) {
      group = { title, stages: [] };
      groups.push(group);
    }

    group.stages.push(stage);
  }

  return groups;
}

export default function UpdateData() {
  const [status, setStatus] = useState(null);
  const [latestReport, setLatestReport] = useState(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const pollRef = useRef(0);

  async function loadStatus() {
    try {
      const data = await getUpdateStatus();
      setStatus(data);

      if (!data.running) {
        loadReport();
      }
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function loadReport() {
    try {
      const data = await getLatestUpdateReport();
      setLatestReport(data);
    } catch {
      // The report is optional until the first update has run.
    }
  }

  useEffect(() => {
    async function init() {
      await loadStatus();
      await loadReport();
    }

    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    window.clearInterval(pollRef.current);

    if (status?.running) {
      pollRef.current = window.setInterval(loadStatus, 3000);
    }

    return () => window.clearInterval(pollRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.running]);

  async function handleStart() {
    const confirmed = window.confirm(
      "Run an incremental data/model update?\n\n" +
        "This refreshes completed events, scrapes missing fight details, rebuilds features, retrains the models, and refreshes future cards. " +
        "It can take several minutes if new fights are available.\n\n" +
        "Keep the backend running while it completes."
    );

    if (!confirmed) {
      return;
    }

    setStarting(true);
    setError("");

    try {
      const data = await startIncrementalUpdate();

      if (data.status) {
        setStatus(data.status);
      } else {
        await loadStatus();
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setStarting(false);
    }
  }

  const report = latestReport?.report;
  const summary = report?.summary;
  const running = Boolean(status?.running);

  const trainStage = report?.stages?.find(
    (stage) => stage.name === "Train calibrated model"
  );
  const stageGroups = useMemo(() => groupStages(report?.stages || []), [report]);

  return (
    <div className="view update-data">
      <header className="view-head">
        <div>
          <p className="eyebrow">Data operations</p>
          <h1 className="view-title">Data Ops</h1>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={handleStart}
          disabled={running || starting}
        >
          {running ? "Update running…" : starting ? "Starting…" : "▶ Run incremental update"}
        </button>
      </header>

      <ErrorNote message={error} />

      <SectionCard
        eyebrow="Pipeline status"
        title={running ? "Incremental update in progress" : "Pipeline idle"}
      >
        {running ? (
          <>
            <MeterBar
              value={Number(status.progress_percent) || 0}
              tone="gold"
              label={
                status.current_stage
                  ? `Stage ${status.current_stage_index}/${status.total_stages}: ${status.current_stage}`
                  : "Starting…"
              }
              trail={`${status.progress_percent ?? 0}%`}
            />
            <p className="dim-note">{status.message}</p>
          </>
        ) : (
          <div className="tile-row three">
            <StatTile
              label="Last run"
              value={
                status?.success === true
                  ? "Success"
                  : status?.success === false
                    ? "Failed"
                    : "No run yet"
              }
              tone={
                status?.success === true
                  ? "win"
                  : status?.success === false
                    ? "loss"
                    : "default"
              }
            />
            <StatTile label="Finished" value={status?.finished_at || "N/A"} />
            <StatTile label="Message" value={status?.message || "Idle"} />
          </div>
        )}
      </SectionCard>

      {report && (
        <SectionCard
          eyebrow="Latest report"
          title="Most recent update report"
          description={`Started ${report.started_at || "?"} · finished ${
            report.finished_at || "?"
          }`}
        >
          <div className="tile-row four">
            <StatTile
              label="Result"
              value={summary?.success ? "Success" : "Failed"}
              tone={summary?.success ? "win" : "loss"}
            />
            <StatTile label="Duration" value={formatDuration(report.duration_seconds)} />
            <StatTile
              label="New fights"
              value={formatNumber(summary?.new_fights_added)}
            />
            <StatTile
              label="Saved prediction rows"
              value={formatNumber(summary?.saved_card_predictions_rows)}
              hint="used by Recent Cards"
            />
          </div>

          {trainStage?.details?.best_model_name && (
            <p className="dim-note">
              Current model:{" "}
              <strong>{formatModelName(trainStage.details.best_model_name)}</strong>
              {trainStage.details.best_model_metrics?.accuracy !== undefined &&
                ` — ${(trainStage.details.best_model_metrics.accuracy * 100).toFixed(1)}% test accuracy`}
            </p>
          )}

          <div className="stage-group-list">
            {stageGroups.map((group) => (
              <section className="stage-group" key={group.title}>
                <header className="stage-group-head">
                  <h3>{group.title}</h3>
                  <span>{group.stages.length} stages</span>
                </header>
                <div className="stage-list">
                  {group.stages.map((stage) => (
                    <div className="stage-row" key={stage.name}>
                      <Tag
                        tone={
                          String(stage.status || "").toLowerCase().includes("fail")
                            ? "loss"
                            : "win"
                        }
                      >
                        {stage.status || "done"}
                      </Tag>
                      <span className="stage-name">{stage.name}</span>
                      <span className="muted mono">
                        {formatDuration(stage.duration_seconds)}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </SectionCard>
      )}

      {!report && (
        <SectionCard eyebrow="Latest report" title="No update report yet">
          <p className="dim-note">
            {latestReport?.message ||
              "Run the incremental update to generate the first report."}
          </p>
        </SectionCard>
      )}
    </div>
  );
}
