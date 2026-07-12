import { useContext, useEffect, useState } from "react";
import { AppContext } from "../AppContext.js";
import { getFighterProfile } from "../api/client.js";
import FighterSearchInput from "../components/FighterSearchInput.jsx";
import EloTrendChart from "../components/EloTrendChart.jsx";
import { FighterAvatar } from "../components/FighterDisplay.jsx";
import {
  EmptyState,
  ErrorNote,
  SectionCard,
  Spinner,
  StatTile,
  Tag,
} from "../components/ui.jsx";
import { formatStatLabel } from "../lib/format.js";

function methodSummaryTotal(summary = {}) {
  return Object.values(summary).reduce((total, value) => total + Number(value || 0), 0);
}

// Already shown in the hero tile row — hide from the stat snapshot.
const HERO_STAT_KEYS = new Set([
  "prior_elo",
  "prior_peak_elo",
  "prior_win_rate",
  "height_inches",
  "reach_inches",
  "age_years",
]);

function buildProfileSummary(profile = {}, styleProfile = {}) {
  const form = profile.form_summary || {};
  const recentResults = Array.isArray(form.recent_results)
    ? form.recent_results.map((result) => result?.[0]?.toUpperCase() || "?").join(" ")
    : "";
  const topRanking = profile.notable_rankings?.[0];
  const winMethods = profile.method_summary?.wins || {};
  const topWinMethod = Object.entries(winMethods).sort(
    ([, firstCount], [, secondCount]) => Number(secondCount || 0) - Number(firstCount || 0)
  )[0];

  return [
    {
      label: "Style read",
      value: styleProfile.style_label || "Style unknown",
      // the full styleProfile.note already renders in the hero — tags only here
      note: styleProfile.tags?.slice(0, 3).join(" / ") || "Style profile is still building.",
    },
    {
      label: "Current form",
      value: form.current_streak || form.last_5_record || "N/A",
      note: form.last_5_record
        ? `Last 5: ${form.last_5_record}${recentResults ? ` (${recentResults})` : ""}`
        : "Recent UFC form unavailable.",
    },
    {
      label: "Finish lean",
      value: topWinMethod ? `${topWinMethod[0]} wins` : "No clear lean",
      note: topWinMethod
        ? `${topWinMethod[1]} recorded win${Number(topWinMethod[1]) === 1 ? "" : "s"} by ${topWinMethod[0]}.`
        : "Method history is sparse.",
    },
    {
      label: "Model context",
      // Elo already headlines the stat tiles; lead with the standout ranking
      value: topRanking ? `#${topRanking.rank} ${topRanking.category}` : "Unranked",
      note: topRanking?.description || "No top ranking flags among qualified fighters.",
    },
  ];
}

export default function FighterProfile() {
  const { imageLookup, profileFighter, sendToFightLab, reflectRoute } = useContext(AppContext);

  const [query, setQuery] = useState(profileFighter || "Khamzat Chimaev");
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadProfile(name = query) {
    const cleaned = String(name || "").trim();

    if (!cleaned) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      const data = await getFighterProfile(cleaned);
      setProfile(data);
      setQuery(data.fighter || cleaned);
      // Keep the URL shareable: #/fighters/<name> always points at what's shown.
      reflectRoute?.("fighters", data.fighter || cleaned);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    async function init() {
      await loadProfile(profileFighter || query);
    }

    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileFighter]);

  const headline = profile?.headline_stats ?? {};
  const styleProfile = profile?.style_profile ?? {};
  const methodSummary = profile?.method_summary ?? {};
  const profileSummary = profile
    ? buildProfileSummary(profile, styleProfile)
    : [];

  return (
    <div className="view fighter-profile">
      <header className="view-head">
        <div>
          <p className="eyebrow">Fighter intelligence</p>
          <h1 className="view-title">Fighters</h1>
        </div>

        <div className="profile-search">
          <FighterSearchInput
            value={query}
            onChange={setQuery}
            onSelect={(name) => {
              setQuery(name);
              loadProfile(name);
            }}
            placeholder="Search a fighter to scout…"
          />
          <button
            type="button"
            className="btn btn-primary"
            disabled={loading || !query.trim()}
            onClick={() => loadProfile()}
          >
            {loading ? "Loading…" : "Load profile"}
          </button>
        </div>
      </header>

      <ErrorNote message={error} />

      {loading && !profile && <Spinner label="Pulling stats, rankings, and history…" />}

      {!profile && !loading && !error && (
        <EmptyState
          title="No fighter selected"
          message="Search for a fighter to open their scouting profile."
        />
      )}

      {profile && (
        <>
          <section className="card profile-hero">
            <FighterAvatar
              name={profile.fighter}
              imageLookup={imageLookup}
              size="hero"
            />

            <div className="profile-hero-copy">
              <Tag tone="neutral">{profile.weight_class || "Weight class unknown"}</Tag>
              <h2 className="profile-name">{profile.fighter}</h2>

              <div className="tag-row">
                <Tag tone="gold">{styleProfile.style_label || "Style unknown"}</Tag>
                {styleProfile.tags?.slice(0, 4).map((tag) => (
                  <Tag key={tag}>{tag}</Tag>
                ))}
              </div>

              {styleProfile.note && <p className="profile-note">{styleProfile.note}</p>}
            </div>

            <div className="profile-hero-actions">
              <button
                type="button"
                className="btn btn-corner-red"
                onClick={() => sendToFightLab({ a: profile.fighter })}
              >
                Use as red corner
              </button>
              <button
                type="button"
                className="btn btn-corner-blue"
                onClick={() => sendToFightLab({ b: profile.fighter })}
              >
                Use as blue corner
              </button>
            </div>
          </section>

          <section className="profile-summary">
            {profileSummary.map((item) => (
              <div className="profile-summary-item" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                <p>{item.note}</p>
              </div>
            ))}
          </section>

          <div className="tile-row six">
            <StatTile label="Elo" value={headline.elo_formatted} />
            <StatTile label="Peak Elo" value={headline.peak_elo_formatted} />
            <StatTile
              label="UFC record"
              value={`${headline.ufc_wins ?? "?"}–${headline.ufc_losses ?? "?"}`}
            />
            <StatTile label="Win rate" value={headline.win_rate_formatted} />
            <StatTile label="Age" value={headline.age_formatted} />
            <StatTile
              label="Height / Reach"
              value={`${headline.height || "N/A"} / ${headline.reach || "N/A"}`}
            />
          </div>

          <div className="two-col">
            <SectionCard eyebrow="Momentum" title="Recent form">
              <div className="tile-row three">
                <StatTile label="Last 5" value={profile.form_summary?.last_5_record} />
                <StatTile label="Streak" value={profile.form_summary?.current_streak} />
                <StatTile
                  label="Results"
                  value={
                    profile.form_summary?.recent_results?.length
                      ? profile.form_summary.recent_results
                          .map((result) => result?.[0]?.toUpperCase() || "?")
                          .join(" · ")
                      : "N/A"
                  }
                />
              </div>
            </SectionCard>

            <SectionCard
              eyebrow="Approach"
              title="Style scores"
              description="Heuristic scores derived from striking / grappling / defense stats."
            >
              <div className="tile-row three">
                <StatTile
                  label="Striking"
                  value={styleProfile.score_percentages?.striking}
                />
                <StatTile
                  label="Grappling"
                  value={styleProfile.score_percentages?.grappling}
                />
                <StatTile
                  label="Defense"
                  value={styleProfile.score_percentages?.defense}
                />
              </div>
            </SectionCard>
          </div>

          <SectionCard
            eyebrow="Trajectory"
            title="Elo / form trend"
            description="Post-fight Elo over the fighter's recent UFC bouts."
          >
            <EloTrendChart eloHistory={profile.elo_history || []} />
          </SectionCard>

          <SectionCard eyebrow="Standing" title="Notable rankings">
            {!profile.notable_rankings?.length && (
              <p className="dim-note">
                No top-10 overall or weight-class rankings among qualified fighters.
              </p>
            )}
            <div className="ranking-grid">
              {profile.notable_rankings?.map((ranking) => (
                <div
                  className="ranking-card"
                  key={`${ranking.metric}-${ranking.scope}-${ranking.scope_label}`}
                >
                  <span className="ranking-category">{ranking.category}</span>
                  <strong className="ranking-rank">#{ranking.rank}</strong>
                  <p>{ranking.description}</p>
                  <span className="ranking-value">{ranking.formatted_value}</span>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard eyebrow="Finishing" title="Method tendencies">
            <div className="method-summary-grid">
              {["wins", "losses", "all"].map((bucket) => {
                const summary = methodSummary[bucket] || {};
                const total = methodSummaryTotal(summary);

                return (
                  <div className="method-summary-col" key={bucket}>
                    <h3 className="mini-heading">
                      {bucket === "all" ? "All fights" : bucket}
                    </h3>
                    {total === 0 && <p className="dim-note">No data</p>}
                    {Object.entries(summary).map(([method, count]) => (
                      <div className="kv-row" key={`${bucket}-${method}`}>
                        <span>{method}</span>
                        <strong>{count}</strong>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          </SectionCard>

          <SectionCard eyebrow="Numbers" title="Stat snapshot">
            <div className="tile-row wrap">
              {profile.profile_stats
                ?.filter((stat) => !HERO_STAT_KEYS.has(stat.key))
                .map((stat) => (
                  <StatTile
                    key={stat.key}
                    label={formatStatLabel(stat.key)}
                    value={stat.formatted_value}
                  />
                ))}
            </div>
          </SectionCard>

          <SectionCard
            eyebrow="History"
            title="Recent fight history"
            description="Click an opponent to open their profile."
          >
            <div className="fight-history">
              {profile.recent_fights?.map((fight) => {
                const result = String(fight.result || "").toLowerCase();
                const resultTone =
                  result === "win" ? "win" : result === "loss" ? "loss" : "neutral";

                return (
                  <div className="history-row" key={fight.fight_url}>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => {
                        setQuery(fight.opponent);
                        loadProfile(fight.opponent);
                      }}
                    >
                      {fight.opponent || "Unknown opponent"}
                    </button>

                    <span className="history-meta">
                      {fight.event_date} · {fight.weight_class} · {fight.event_name}
                    </span>

                    <Tag tone={resultTone}>
                      {fight.result || "N/A"}
                      {fight.method_category ? ` · ${fight.method_category}` : ""}
                      {fight.round ? ` · R${fight.round}` : ""}
                      {fight.time ? ` · ${fight.time}` : ""}
                    </Tag>
                  </div>
                );
              })}
            </div>
          </SectionCard>
        </>
      )}
    </div>
  );
}
