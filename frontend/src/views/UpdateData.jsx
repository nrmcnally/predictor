import { useEffect, useMemo, useRef, useState } from "react";
import {
  checkHealth,
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

export default function UpdateData() {
  const [status, setStatus] = useState(null);
  const [latestReport, setLatestReport] = useState(null);
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
          <h1 className="view-title">Data Ops</h1>
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
