import { useEffect, useMemo, useRef, useState } from "react";
import {
  checkHealth,
  getDataOperationsHealth,
  getLatestUpdateReport,
  getUpdateStatus,
  startIncrementalUpdate,
  uploadDataBundle,
} from "../api/client.js";
import { ConfirmDialog } from "../components/ConfirmDialog.jsx";
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

function formatAgeHours(value) {
  const hours = Number(value);
  if (!Number.isFinite(hours)) return "Unknown";
  if (hours < 1) return "Less than 1 hour ago";
  if (hours < 24) return `${Math.round(hours)} hours ago`;
  const days = hours / 24;
  return `${days.toFixed(days < 3 ? 1 : 0)} days ago`;
}

function healthTone(status) {
  if (status === "healthy") return "win";
  if (status === "attention") return "warn";
  return "loss";
}

export default function UpdateData() {
  const [status, setStatus] = useState(null);
  const [latestReport, setLatestReport] = useState(null);
  const [dataHealth, setDataHealth] = useState(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [hosted, setHosted] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const pollRef = useRef(0);

  const bundleRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);

  async function onBundleFile(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploading(true);
    setUploadResult(null);
    setError("");
    try {
      setUploadResult(await uploadDataBundle(file));
    } catch (uploadError) {
      setError(uploadError.message);
    } finally {
      setUploading(false);
    }
  }

  useEffect(() => {
    let active = true;
    checkHealth()
      .then((data) => active && setHosted(Boolean(data?.hosted)))
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  async function loadStatus() {
    try {
      const data = await getUpdateStatus();
      setStatus(data);

      if (!data.running) {
        loadReport();
        loadHealth();
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

  async function loadHealth() {
    try {
      setDataHealth(await getDataOperationsHealth());
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  useEffect(() => {
    async function init() {
      await loadStatus();
      await loadReport();
      await loadHealth();
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
    setConfirmOpen(false);
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
          <h1 className="view-title">Data ops</h1>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setConfirmOpen(true)}
          disabled={running || starting || hosted}
          title={hosted ? "Data updates run on your PC, not the server" : undefined}
        >
          {running ? "Update running…" : starting ? "Starting…" : "▶ Run incremental update"}
        </button>
      </header>

      <ConfirmDialog
        open={confirmOpen}
        title="Run incremental update?"
        confirmLabel="Run update"
        body={
          "This refreshes completed events, scrapes missing fight details, rebuilds features, retrains the models, and refreshes future cards. " +
          "It can take several minutes if new fights are available.\n\nKeep the backend running while it completes."
        }
        onConfirm={handleStart}
        onCancel={() => setConfirmOpen(false)}
      />

      {hosted && (
        <div className="offline-banner">
          This is the hosted server — the scraper/training pipeline runs on your PC, not
          here. After a local update, build the bundle (
          <code>python deploy/make_bundle.py</code>) and upload it below — no terminal
          login needed.
        </div>
      )}

      <ErrorNote message={error} />

      <SectionCard
        eyebrow="Daily safeguards"
        title="Refresh and totals health"
        description="A persisted heartbeat, current market coverage, append-only totals history, and automatic grading of frozen duration predictions."
        actions={
          dataHealth ? (
            <Tag tone={healthTone(dataHealth.status)}>
              {dataHealth.status === "healthy"
                ? "Healthy"
                : dataHealth.status === "attention"
                  ? "Needs attention"
                  : "Action required"}
            </Tag>
          ) : null
        }
      >
        {!dataHealth ? (
          <p className="dim-note">Loading operational healthâ€¦</p>
        ) : (
          <>
            <div className="tile-row four">
              <StatTile
                label="Last refresh"
                value={formatAgeHours(dataHealth.refresh?.age_hours)}
                hint={dataHealth.refresh?.success ? "completed successfully" : "check alerts"}
                tone={dataHealth.refresh?.success ? "win" : "loss"}
              />
              <StatTile
                label="Odds refresh"
                value={dataHealth.odds?.refresh_available ? "Successful" : "Needs attention"}
                hint={
                  dataHealth.odds?.provider_requests_remaining === null ||
                  dataHealth.odds?.provider_requests_remaining === undefined
                    ? "quota unavailable"
                    : `${formatNumber(dataHealth.odds.provider_requests_remaining)} requests left`
                }
                tone={dataHealth.odds?.refresh_available ? "win" : "warn"}
              />
              <StatTile
                label="Current totals"
                value={`${formatNumber(dataHealth.odds?.totals_coverage?.covered)} / ${formatNumber(
                  dataHealth.odds?.totals_coverage?.total
                )}`}
                hint="upcoming fights with a market O/U"
              />
              <StatTile
                label="Prospective O/U"
                value={`${formatNumber(
                  dataHealth.duration_evaluation?.scored_predictions
                )} settled`}
                hint={`${formatNumber(
                  dataHealth.duration_evaluation?.pending_predictions
                )} pending frozen predictions`}
              />
            </div>

            <MeterBar
              value={(Number(dataHealth.odds?.totals_coverage?.ratio) || 0) * 100}
              tone="gold"
              label="Current totals market coverage"
              trail={dataHealth.odds?.totals_coverage?.percentage || "0.0%"}
            />

            <p className="dim-note">
              Totals history: {formatNumber(dataHealth.totals_history?.snapshot_rows)} quotes
              across {formatNumber(dataHealth.totals_history?.unique_fights)} fights and{" "}
              {formatNumber(dataHealth.totals_history?.bookmakers)} books
              {dataHealth.totals_history?.lines?.length
                ? ` Â· lines ${dataHealth.totals_history.lines.join(", ")}`
                : ""}
              . Market coverage is informational; a fight can legitimately have no posted total yet.
            </p>

            {dataHealth.alerts?.length > 0 && (
              <div className="stage-list" aria-label="Data operations alerts">
                {dataHealth.alerts.map((alert) => (
                  <div className="stage-block" key={alert.code}>
                    <div className="stage-row">
                      <Tag tone={alert.severity === "critical" ? "loss" : "warn"}>
                        {alert.severity}
                      </Tag>
                      <span className="stage-name">{alert.message}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </SectionCard>

      <SectionCard
        eyebrow="Data refresh"
        title="Upload data bundle"
        description="Apply a locally-built deploy bundle (deploy/deploy_bundle.tar.gz). Merges results, cards, odds, and models — accounts, picks, and friendships on this server are never touched."
      >
        <input
          ref={bundleRef}
          type="file"
          accept=".gz,.tar.gz,application/gzip"
          style={{ display: "none" }}
          onChange={onBundleFile}
        />
        <button
          type="button"
          className="btn btn-primary"
          disabled={uploading}
          onClick={() => bundleRef.current?.click()}
        >
          {uploading ? "Uploading + applying… (~44MB, can take a minute)" : "⬆ Choose bundle & apply"}
        </button>
        {uploadResult && (
          <p className="form-ok" style={{ marginTop: 12 }}>
            {uploadResult.message}{" "}
            {uploadResult.db && typeof uploadResult.db === "object"
              ? `· ${Object.entries(uploadResult.db)
                  .map(([table, rows]) => `${table}: ${rows}`)
                  .join(", ")}`
              : ""}
            {` · ${uploadResult.files_updated} files updated`}
          </p>
        )}
      </SectionCard>

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
                  {group.stages.map((stage) => {
                    const warnings = Array.isArray(stage.details?.validation_warnings)
                      ? stage.details.validation_warnings
                      : [];
                    return (
                      <div className="stage-block" key={stage.name}>
                        <div className="stage-row">
                          <Tag
                            tone={
                              String(stage.status || "").toLowerCase().includes("fail")
                                ? "loss"
                                : warnings.length > 0
                                  ? "warn"
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
                        {/* Data-quality warnings (e.g. "results still posting")
                            surface here so a quiet site update has a visible
                            explanation. */}
                        {warnings.map((warning) => (
                          <p className="dim-note stage-warning" key={warning}>
                            {warning}
                          </p>
                        ))}
                      </div>
                    );
                  })}
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
