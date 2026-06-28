import { useContext, useState } from "react";
import { AppContext } from "../AppContext.js";
import { predictFight, predictMethod } from "../api/client.js";
import OctagonScene from "../three/OctagonScene.jsx";
import FighterSearchInput from "../components/FighterSearchInput.jsx";
import { FighterAvatar } from "../components/FighterDisplay.jsx";
import {
  EdgesCard,
  InsightsCard,
  MethodCard,
  RiskFlagsCard,
  VerdictCard,
} from "../components/PredictionBreakdown.jsx";
import { ErrorNote, Spinner } from "../components/ui.jsx";
import { parsePercentageText } from "../lib/format.js";

const EXAMPLE_FIGHTS = [
  ["Khamzat Chimaev", "Sean Strickland", "Middleweight"],
  ["Islam Makhachev", "Belal Muhammad", "Welterweight"],
  ["Merab Dvalishvili", "Sean O'Malley", "Bantamweight"],
];

export default function FightLab() {
  const { imageLookup, weightClasses, openProfile, fightLabPrefill } =
    useContext(AppContext);

  const [fighterA, setFighterA] = useState(fightLabPrefill.a || "Khamzat Chimaev");
  const [fighterB, setFighterB] = useState(fightLabPrefill.b || "Sean Strickland");
  const [weightClass, setWeightClass] = useState("Middleweight");

  const [prediction, setPrediction] = useState(null);
  const [methodPrediction, setMethodPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [methodLoading, setMethodLoading] = useState(false);
  const [error, setError] = useState("");
  const [methodError, setMethodError] = useState("");
  const hasPrediction = Boolean(prediction);

  async function runPrediction(event) {
    event?.preventDefault();

    setLoading(true);
    setError("");
    setPrediction(null);
    setMethodPrediction(null);
    setMethodError("");

    try {
      const data = await predictFight(fighterA, fighterB, weightClass);
      setPrediction(data);

      setMethodLoading(true);

      try {
        const methodData = await predictMethod(
          data.fighter_a,
          data.fighter_b,
          data.weight_class
        );
        setMethodPrediction(methodData);
      } catch (methodRequestError) {
        setMethodError(methodRequestError.message);
      } finally {
        setMethodLoading(false);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  function swapFighters() {
    setFighterA(fighterB);
    setFighterB(fighterA);
    setPrediction(null);
    setMethodPrediction(null);
    setError("");
    setMethodError("");
  }

  function clearForm() {
    setFighterA("");
    setFighterB("");
    setPrediction(null);
    setMethodPrediction(null);
    setError("");
    setMethodError("");
  }

  function loadExample([exampleA, exampleB, exampleWeightClass]) {
    setFighterA(exampleA);
    setFighterB(exampleB);
    setWeightClass(exampleWeightClass);
    setPrediction(null);
    setMethodPrediction(null);
    setError("");
    setMethodError("");
  }

  return (
    <div className={`view fight-lab ${hasPrediction ? "has-results" : ""}`}>
      <div className={`stage ${hasPrediction ? "stage-compact" : ""}`}>
        <OctagonScene className="stage-scene" />
        <div className="stage-overlay" />

        <div className="stage-content">
          <header className="stage-head">
            <p className="eyebrow">Prediction engine</p>
            <h1 className="stage-title">Fight Lab</h1>
            <p className="stage-sub">
              Calibrated win probabilities from Elo, fight history, physical profile,
              and age features.
            </p>
          </header>

          <form className="stage-form" onSubmit={runPrediction}>
            <div className="corner-panel red">
              <div className="corner-head">
                <FighterAvatar
                  name={fighterA}
                  imageLookup={imageLookup}
                  size="xl"
                  corner="red"
                />
                <span className="corner-tag corner-red">Red corner</span>
              </div>
              <FighterSearchInput
                id="fighter-a"
                value={fighterA}
                onChange={setFighterA}
                placeholder="Fighter A"
                corner="red"
              />
            </div>

            <div className="stage-center">
              <span className="vs-mark">VS</span>

              <select
                className="select"
                value={weightClass}
                onChange={(event) => setWeightClass(event.target.value)}
                aria-label="Weight class"
              >
                {weightClasses.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>

              <button
                type="submit"
                className="btn btn-primary btn-lg"
                disabled={loading || !fighterA.trim() || !fighterB.trim()}
              >
                {loading ? "Crunching matchup…" : "Predict fight"}
              </button>

              <div className="stage-tools">
                <button type="button" className="btn btn-ghost" onClick={swapFighters}>
                  ⇄ Swap
                </button>
                <button type="button" className="btn btn-ghost" onClick={clearForm}>
                  Clear
                </button>
              </div>
            </div>

            <div className="corner-panel blue">
              <div className="corner-head">
                <FighterAvatar
                  name={fighterB}
                  imageLookup={imageLookup}
                  size="xl"
                  corner="blue"
                />
                <span className="corner-tag corner-blue">Blue corner</span>
              </div>
              <FighterSearchInput
                id="fighter-b"
                value={fighterB}
                onChange={setFighterB}
                placeholder="Fighter B"
                corner="blue"
              />
            </div>
          </form>

          {prediction ? (
            <>
              <div className="matchup-strip">
                <div>
                  <span className="strip-label">Model pick</span>
                  <strong>{prediction.predicted_winner}</strong>
                </div>
                <div>
                  <span className="strip-label">Confidence</span>
                  <strong>{prediction.confidence_percentage}</strong>
                </div>
                <div>
                  <span className="strip-label">Red corner</span>
                  <strong>{prediction.fighter_a_percentage}</strong>
                </div>
                <div>
                  <span className="strip-label">Blue corner</span>
                  <strong>{prediction.fighter_b_percentage}</strong>
                </div>
              </div>
              {parsePercentageText(prediction.confidence_percentage) >= 0.75 && (
                <p className="dim-note">
                  Heads up: very high-confidence picks have historically run a few
                  points hot — our ~85% calls have won closer to ~79%. Read this as a
                  clear favorite, not a near-lock.
                </p>
              )}
            </>
          ) : (
            <div className="stage-examples">
              <span>Try:</span>
              {EXAMPLE_FIGHTS.map((example) => (
                <button
                  key={example.join("-")}
                  type="button"
                  className="chip"
                  onClick={() => loadExample(example)}
                >
                  {example[0].split(" ").at(-1)} vs {example[1].split(" ").at(-1)}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <ErrorNote message={error} />

      {loading && <Spinner label="Running calibrated model…" />}

      {prediction && (
        <div className="results-grid">
          <VerdictCard
            prediction={prediction}
            imageLookup={imageLookup}
            onFighterClick={openProfile}
          />
          <MethodCard
            methodPrediction={methodPrediction}
            loading={methodLoading}
            error={methodError}
          />
          <RiskFlagsCard prediction={prediction} />
          <InsightsCard prediction={prediction} />
          <EdgesCard prediction={prediction} />
        </div>
      )}
    </div>
  );
}
