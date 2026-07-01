import { useContext, useEffect, useState } from "react";
import { AppContext } from "../AppContext.js";
import { getLeaderboardOptions, getLeaderboards } from "../api/client.js";
import { FighterName } from "../components/FighterDisplay.jsx";
import { EmptyState, ErrorNote, Spinner, Tag } from "../components/ui.jsx";
import {
  formatLeaderboardStatValue,
  formatNumber,
  formatStatLabel,
} from "../lib/format.js";

const FALLBACK_CATEGORIES = [
  { value: "overall", label: "Overall" },
  { value: "striking", label: "Striking" },
  { value: "grappling", label: "Grappling" },
  { value: "wrestling", label: "Wrestling" },
  { value: "finishing", label: "Finishing" },
  { value: "defense", label: "Defense" },
  { value: "elo", label: "Elo" },
  { value: "experience", label: "Experience" },
  { value: "reach", label: "Reach" },
  { value: "reach_for_size", label: "Reach for Size" },
];

export default function Leaderboards() {
  const { imageLookup, openProfile } = useContext(AppContext);

  const [options, setOptions] = useState(null);
  const [data, setData] = useState(null);

  const [scope, setScope] = useState("overall");
  const [weightClass, setWeightClass] = useState("Lightweight");
  const [category, setCategory] = useState("overall");
  const [direction, setDirection] = useState("best");
  const [top, setTop] = useState(5);
  const [minFights, setMinFights] = useState(5);
  const [maxInactiveDays, setMaxInactiveDays] = useState(1095);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadData() {
    setLoading(true);
    setError("");

    try {
      const result = await getLeaderboards({ top, minFights, maxInactiveDays });
      setData(result);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    getLeaderboardOptions()
      .then((result) => {
        setOptions(result);

        if (result.weight_classes?.length) {
          setWeightClass((current) => current || result.weight_classes[0]);
        }
      })
      .catch(() => {});

    async function init() {
      await loadData();
    }

    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const categories = options?.categories ?? FALLBACK_CATEGORIES;
  const weightClassOptions = options?.weight_classes ?? [];

  const payload =
    scope === "overall"
      ? data?.overall?.categories?.[category]
      : data?.weight_classes?.[weightClass]?.categories?.[category];

  const rows = payload?.[direction] ?? [];

  return (
    <div className="view leaderboards">
      <header className="view-head">
        <div>
          <p className="eyebrow">Fighter rankings</p>
          <h1 className="view-title">Leaderboards</h1>
        </div>
      </header>

      <div className="card controls-card">
        <div className="controls-row">
          <div className="control">
            <label>Scope</label>
            <div className="segmented">
              <button
                type="button"
                className={scope === "overall" ? "active" : ""}
                onClick={() => setScope("overall")}
              >
                Overall
              </button>
              <button
                type="button"
                className={scope === "weight_class" ? "active" : ""}
                onClick={() => setScope("weight_class")}
              >
                By weight class
              </button>
            </div>
          </div>

          {scope === "weight_class" && (
            <div className="control">
              <label htmlFor="lb-weight-class">Weight class</label>
              <select
                id="lb-weight-class"
                className="select"
                value={weightClass}
                onChange={(event) => setWeightClass(event.target.value)}
              >
                {weightClassOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="control">
            <label htmlFor="lb-category">Category</label>
            <select
              id="lb-category"
              className="select"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              {categories.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="control">
            <label>Direction</label>
            <div className="segmented">
              <button
                type="button"
                className={direction === "best" ? "active" : ""}
                onClick={() => setDirection("best")}
              >
                Best
              </button>
              <button
                type="button"
                className={direction === "worst" ? "active" : ""}
                onClick={() => setDirection("worst")}
              >
                Worst
              </button>
            </div>
          </div>

          <div className="control small">
            <label htmlFor="lb-top">Top N</label>
            <input
              id="lb-top"
              type="number"
              min="1"
              max="25"
              value={top}
              onChange={(event) => setTop(Number(event.target.value) || 5)}
            />
          </div>

          <div className="control small">
            <label htmlFor="lb-min-fights">Min fights</label>
            <input
              id="lb-min-fights"
              type="number"
              min="0"
              value={minFights}
              onChange={(event) => setMinFights(Number(event.target.value) || 0)}
            />
          </div>

          <div className="control small">
            <label htmlFor="lb-inactive">Max inactive days</label>
            <input
              id="lb-inactive"
              type="number"
              min="0"
              value={maxInactiveDays}
              onChange={(event) => setMaxInactiveDays(Number(event.target.value) || 0)}
            />
          </div>

          <button
            type="button"
            className="btn btn-primary"
            onClick={loadData}
            disabled={loading}
          >
            {loading ? "Loading..." : "Apply"}
          </button>
        </div>
      </div>

      <ErrorNote message={error} />

      {loading && <Spinner label="Ranking fighters..." />}

      {!loading && rows.length === 0 && (
        <EmptyState
          title="No leaderboard rows"
          message="Try loosening the filters or rebuilding the current fighter data."
        />
      )}

      {!loading && rows.length > 0 && (
        <div className="leaderboard-list">
          {rows.map((row) => (
            <div
              className={`leaderboard-row ${row.rank <= 3 ? `podium-${row.rank}` : ""}`}
              key={`${row.rank}-${row.fighter}`}
            >
              <span className="rank-medal">#{row.rank}</span>

              <div className="leaderboard-fighter">
                <FighterName
                  name={row.fighter}
                  imageLookup={imageLookup}
                  size="lg"
                  onClick={openProfile}
                />
                <span className="muted">
                  {row.weight_class} - {formatNumber(row.prior_fights)} UFC fights
                </span>
              </div>

              <div className="leaderboard-score">
                <span
                  className="stat-label"
                  title="Heuristic, data-derived composite - not an official UFC rating."
                >
                  Score (heuristic)
                </span>
                <strong className="mono">{row.score}</strong>
              </div>

              <div className="leaderboard-stats">
                {Object.entries(row.supporting_stats ?? {}).map(([key, value]) => (
                  <Tag key={key}>
                    {formatStatLabel(key)}: {formatLeaderboardStatValue(key, value)}
                  </Tag>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
