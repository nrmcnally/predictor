import { useContext, useEffect, useMemo, useRef, useState } from "react";
import { AppContext } from "../AppContext.js";
import { FighterAvatar } from "../components/FighterDisplay.jsx";
import InteractionScene from "../three/interactions/InteractionScene.jsx";
import { Tag } from "../components/ui.jsx";

const PHASES = ["idle", "lock", "scan", "evidence-0", "evidence-1", "evidence-2", "result"];

const SCENARIOS = [
  {
    id: "moderate",
    label: "Moderate Lean",
    corner: "red",
    pick: "Khamzat Chimaev",
    opponent: "Sean Strickland",
    probability: 64.5,
    confidence: "Moderate lean",
    market: "Market agrees",
    method: "Decision",
    finishType: "decision",
    note: "The normal reveal: useful evidence, a clear favorite, but not a blowout.",
  },
  {
    id: "close",
    label: "Close Fight",
    corner: "red",
    pick: "Khamzat Chimaev",
    opponent: "Sean Strickland",
    probability: 51.8,
    confidence: "Close lean",
    market: "Market agrees",
    method: "Split decision",
    finishType: "decision",
    note: "A tense reveal: the winner card should land softly because this is nearly even.",
  },
  {
    id: "strong",
    label: "Strong Lean",
    corner: "red",
    pick: "Khamzat Chimaev",
    opponent: "Sean Strickland",
    probability: 78.2,
    confidence: "High confidence",
    market: "Market agrees",
    method: "Submission",
    finishType: "submission",
    note: "A decisive reveal: the winner should claim center and the method cue should feel like pressure closing in.",
  },
  {
    id: "split",
    label: "Market Split",
    corner: "red",
    pick: "Khamzat Chimaev",
    opponent: "Sean Strickland",
    probability: 57.4,
    confidence: "Review flag",
    market: "Market disagrees",
    method: "KO/TKO",
    finishType: "ko",
    note: "A caution reveal: amber interruption tells the user this result deserves review, while the method cue hits harder.",
  },
];

const EVIDENCE = [
  {
    id: "striking",
    label: "Striking differential",
    value: "+38.6 sig str/15",
    tone: "red",
    phase: "evidence-0",
    copy: "Red-corner output is the first driver. It gives the reveal a reason to start moving toward Khamzat.",
  },
  {
    id: "grappling",
    label: "Grappling pressure",
    value: "+4.70 TD/15",
    tone: "green",
    phase: "evidence-1",
    copy: "The second pulse shows a second path to win: takedowns, control, and pressure.",
  },
  {
    id: "form",
    label: "Opponent-adjusted form",
    value: "-12 Elo",
    tone: "amber",
    phase: "evidence-2",
    copy: "The final pulse is the counterweight. It keeps the reveal from feeling like empty hype.",
  },
];

function getPhaseIndex(phase) {
  return Math.max(0, PHASES.indexOf(phase));
}

function isPhaseAtLeast(phase, target) {
  return getPhaseIndex(phase) >= getPhaseIndex(target);
}

function getActiveEvidence(phase) {
  if (phase === "evidence-0") {
    return EVIDENCE[0];
  }

  if (phase === "evidence-1") {
    return EVIDENCE[1];
  }

  if (phase === "evidence-2" || phase === "result") {
    return EVIDENCE[2];
  }

  return null;
}

function getEvidenceIndex(phase) {
  const active = getActiveEvidence(phase);
  return active ? EVIDENCE.findIndex((item) => item.id === active.id) : -1;
}

function getProbabilityLabels(scenario) {
  const left = scenario.corner === "red" ? scenario.probability : 100 - scenario.probability;
  const right = 100 - left;
  return { left, right };
}

function useRevealTimeline(setPhase) {
  const timeoutRef = useRef([]);

  useEffect(() => {
    return () => {
      timeoutRef.current.forEach((timeoutId) => window.clearTimeout(timeoutId));
    };
  }, []);

  function clearTimeline() {
    timeoutRef.current.forEach((timeoutId) => window.clearTimeout(timeoutId));
    timeoutRef.current = [];
  }

  function play() {
    clearTimeline();
    setPhase("lock");
    timeoutRef.current = [
      window.setTimeout(() => setPhase("scan"), 650),
      window.setTimeout(() => setPhase("evidence-0"), 1250),
      window.setTimeout(() => setPhase("evidence-1"), 2050),
      window.setTimeout(() => setPhase("evidence-2"), 2850),
      window.setTimeout(() => setPhase("result"), 3800),
    ];
  }

  function reset() {
    clearTimeline();
    setPhase("idle");
  }

  function skip() {
    clearTimeline();
    setPhase("result");
  }

  return { play, reset, skip };
}

function ScenarioPicker({ activeScenario, onSelect }) {
  return (
    <div className="reveal-scenario-picker" aria-label="Reveal scenario">
      {SCENARIOS.map((scenario) => (
        <button
          key={scenario.id}
          type="button"
          className={activeScenario.id === scenario.id ? "active" : ""}
          onClick={() => onSelect(scenario.id)}
        >
          <span>{scenario.label}</span>
          <strong>{scenario.probability.toFixed(1)}%</strong>
          <em>{scenario.method}</em>
        </button>
      ))}
    </div>
  );
}

function EvidenceRail({ phase }) {
  return (
    <div className="reveal-evidence-rail">
      {EVIDENCE.map((item) => {
        const active = getActiveEvidence(phase)?.id === item.id;
        const revealed = isPhaseAtLeast(phase, item.phase);

        return (
          <article
            key={item.id}
            className={`reveal-evidence-card tone-${item.tone} ${active ? "active" : ""} ${
              revealed ? "revealed" : ""
            }`}
          >
            <span>{item.label}</span>
            <strong>{revealed ? item.value : "Waiting"}</strong>
            <p>{revealed ? item.copy : "This driver appears during the model scan."}</p>
          </article>
        );
      })}
    </div>
  );
}

function RevealTimeline({ phase }) {
  const steps = [
    ["lock", "Matchup locks"],
    ["scan", "Model scan"],
    ["evidence-0", "Evidence 1"],
    ["evidence-1", "Evidence 2"],
    ["evidence-2", "Method cue"],
    ["result", "Result lands"],
  ];

  return (
    <div className="transition-timeline reveal-timeline-expanded">
      {steps.map(([step, label]) => (
        <span key={step} className={isPhaseAtLeast(phase, step) ? "active" : ""}>
          {label}
        </span>
      ))}
    </div>
  );
}

function RevealFighterCard({ name, corner, meta, role, className }) {
  const { imageLookup } = useContext(AppContext);

  return (
    <div className={`reveal-fighter ${corner} ${className}`}>
      <FighterAvatar name={name} imageLookup={imageLookup} size="xl" corner={corner} />
      <div>
        <span>{role}</span>
        <strong>{name}</strong>
        <em>{meta}</em>
      </div>
    </div>
  );
}

function PredictionRevealPrototype({ scenario, phase, setPhase }) {
  const { play, reset, skip } = useRevealTimeline(setPhase);
  const { imageLookup } = useContext(AppContext);
  const activeEvidence = getActiveEvidence(phase);
  const evidenceIndex = getEvidenceIndex(phase);
  const resultVisible = phase === "result";
  const scanning = phase !== "idle" && phase !== "result";
  const warningVisible = scenario.id === "split" && isPhaseAtLeast(phase, "evidence-2");
  const scanStatusVisible = scanning && !warningVisible;
  const scanDetail =
    phase === "evidence-2"
      ? `${activeEvidence?.value || "Checking finish"} - ${scenario.method} cue`
      : activeEvidence?.value || "Preparing fighter profile and market context.";
  const { left, right } = getProbabilityLabels(scenario);

  useEffect(() => {
    setPhase("idle");
  }, [scenario.id, setPhase]);

  return (
    <div
      className={`interaction-prototype reveal-prototype phase-${phase} scenario-${scenario.id} method-${scenario.finishType}`}
    >
      <div className="interaction-command-bar reveal-command-bar">
        <div>
          <span>Fight Lab loading transition</span>
          <strong>{scenario.pick} vs {scenario.opponent}</strong>
        </div>
        <div className="interaction-actions">
          <button type="button" className="btn btn-ghost" onClick={reset}>
            Reset
          </button>
          <button type="button" className="btn btn-ghost" onClick={skip}>
            Show instantly
          </button>
          <button type="button" className="btn btn-primary" onClick={play}>
            Predict fight
          </button>
        </div>
      </div>

      <div className="reveal-stage-shell refined-reveal-stage">
        <InteractionScene
          phase={phase}
          confidence={scenario.probability}
          marketSplit={scenario.id === "split"}
          evidenceIndex={evidenceIndex}
          finishType={scenario.finishType}
        />

        <RevealFighterCard
          name="Khamzat Chimaev"
          corner="red"
          role="Red corner"
          meta="Elo 1646 - UFC 9-1"
          className={scenario.corner === "red" ? "winner" : "loser"}
        />

        <RevealFighterCard
          name="Sean Strickland"
          corner="blue"
          role="Blue corner"
          meta="Elo 1658 - UFC 16-7"
          className={scenario.corner === "blue" ? "winner" : "loser"}
        />

        <div className={`scan-status-card ${scanStatusVisible ? "visible" : ""}`}>
          <span>{activeEvidence ? "Scanning evidence" : "Model scan"}</span>
          <strong>{activeEvidence?.label || "Locking matchup"}</strong>
          <p>{scanDetail}</p>
        </div>

        {scenario.id === "split" && (
          <div className={`market-warning ${warningVisible ? "visible" : ""}`}>
            <span>Market split</span>
            <strong>Review before trusting</strong>
          </div>
        )}

        <div className={`reveal-result-card refined-result-card ${resultVisible ? "visible" : ""}`}>
          <div className="result-card-fighter">
            <FighterAvatar
              name={scenario.pick}
              imageLookup={imageLookup}
              size="xl"
              corner={scenario.corner}
            />
            <div>
              <span>Model pick</span>
              <strong>{scenario.pick}</strong>
              <div className="result-card-meta">
                <em>{scenario.confidence}</em>
                <em>{scenario.method}</em>
                <em>{scenario.market}</em>
              </div>
            </div>
          </div>
          <div className="mini-probability">
            <div style={{ width: `${left}%` }} />
          </div>
          <p>
            {left.toFixed(1)}% red corner - {right.toFixed(1)}% blue corner
          </p>
        </div>
      </div>

      <EvidenceRail phase={phase} />
      <RevealTimeline phase={phase} />
    </div>
  );
}

export default function TestLab() {
  const [scenarioId, setScenarioId] = useState(SCENARIOS[0].id);
  const [phase, setPhase] = useState("idle");
  const activeScenario = useMemo(
    () => SCENARIOS.find((scenario) => scenario.id === scenarioId) || SCENARIOS[0],
    [scenarioId]
  );

  return (
    <div className="view test-lab">
      <header className="view-head">
        <div>
          <p className="eyebrow">Interaction prototype</p>
          <h1 className="view-title">Test Lab</h1>
        </div>
      </header>

      <div className="test-lab-layout">
        <section className="test-stage card">
          <div className="test-stage-head">
            <div>
              <p className="eyebrow">Prediction reveal</p>
              <h2>Fight Lab Loading State</h2>
            </div>
            <Tag tone="gold">focused test</Tag>
          </div>

          <ScenarioPicker activeScenario={activeScenario} onSelect={setScenarioId} />
          <PredictionRevealPrototype
            scenario={activeScenario}
            phase={phase}
            setPhase={setPhase}
          />
        </section>

        <aside className="test-lab-notes">
          <section className="test-note-card">
            <span>Prototype signal</span>
            <strong>
              This treats the prediction reveal as the app's useful loading state,
              not a separate 3D destination.
            </strong>
          </section>
          <section className="test-note-card">
            <span>Current scenario</span>
            <strong>{activeScenario.note}</strong>
          </section>
          <section className="test-note-card">
            <span>Likely home</span>
            <strong>
              The existing Fight Lab stage after pressing Predict fight, resolving into
              the normal result cards below it.
            </strong>
          </section>
        </aside>
      </div>
    </div>
  );
}
