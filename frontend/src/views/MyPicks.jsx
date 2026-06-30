import { useContext, useEffect, useMemo, useState } from "react";
import { AppContext } from "../AppContext.js";
import { normalizeFighterName } from "../lib/format.js";
import {
  getFutureCards,
  getFutureCardPredictions,
  getFutureFightOdds,
  getMyPredictions,
  savePrediction,
  deletePrediction,
} from "../api/client.js";
import { EmptyState, ErrorNote, SectionCard, Spinner, Tag } from "../components/ui.jsx";
import { FighterAvatar } from "../components/FighterDisplay.jsx";

const METHODS = [
  { value: "ko_tko", label: "KO/TKO" },
  { value: "submission", label: "Sub" },
  { value: "decision", label: "Dec" },
];

function isLocked(eventDate) {
  const eventDay = new Date(eventDate);
  if (Number.isNaN(eventDay.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  eventDay.setHours(0, 0, 0, 0);
  return today >= eventDay;
}

function pct(value) {
  const n = Number(value);
  return value === null || value === undefined || !Number.isFinite(n)
    ? "—"
    : `${Math.round(n * 100)}%`;
}

function fightKey(url) {
  return String(url || "").replace(/\/+$/, "").split("/").pop();
}

function findOdds(oddsRows, fightUrl) {
  if (!oddsRows?.length) return null;
  const exact = oddsRows.find((row) => row.fight_url === fightUrl);
  if (exact) return exact;
  const key = fightKey(fightUrl);
  return oddsRows.find((row) => fightKey(row.fight_url) === key) || null;
}

function modelProb(prediction, name) {
  if (!prediction) return null;
  const n = normalizeFighterName(name);
  if (normalizeFighterName(prediction.fighter_a) === n) return prediction.fighter_a_probability;
  if (normalizeFighterName(prediction.fighter_b) === n) return prediction.fighter_b_probability;
  return null;
}

function marketProb(odds, name) {
  if (!odds?.odds_available) return null;
  const n = normalizeFighterName(name);
  if (normalizeFighterName(odds.fighter_1) === n) return odds.fighter_1_market_probability;
  if (normalizeFighterName(odds.fighter_2) === n) return odds.fighter_2_market_probability;
  return null;
}

export default function MyPicks() {
  const { imageLookup } = useContext(AppContext);

  const [cards, setCards] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState(null);
  const [oddsRows, setOddsRows] = useState([]);
  const [picks, setPicks] = useState({}); // fight_url -> pick
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [busyFight, setBusyFight] = useState("");

  useEffect(() => {
    let active = true;
    getFutureCards()
      .then((rows) => {
        if (!active) return;
        setCards(rows);
        const firstOpen = rows.find((card) => !isLocked(card.event_date));
        setSelectedId((current) => current || firstOpen?.event_id || rows[0]?.event_id || "");
      })
      .catch((err) => active && setError(err.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedId) return undefined;
    let active = true;
    setDetailLoading(true);
    setError("");
    Promise.all([
      getFutureCardPredictions(selectedId),
      getFutureFightOdds().catch(() => []),
      getMyPredictions(selectedId),
    ])
      .then(([card, odds, myPicks]) => {
        if (!active) return;
        setDetail(card);
        setOddsRows(Array.isArray(odds) ? odds : odds?.fights ?? []);
        const byUrl = {};
        for (const pick of myPicks) byUrl[pick.fight_url] = pick;
        setPicks(byUrl);
      })
      .catch((err) => active && setError(err.message))
      .finally(() => active && setDetailLoading(false));
    return () => {
      active = false;
    };
  }, [selectedId]);

  const locked = detail ? isLocked(detail.event_date) : false;

  const pickedCount = useMemo(
    () => (detail?.fights || []).filter((f) => picks[f.fight_url]).length,
    [detail, picks]
  );

  async function applyPick(fightUrl, fighter, method) {
    setBusyFight(fightUrl);
    setError("");
    try {
      const saved = await savePrediction(fightUrl, fighter, method ?? null);
      setPicks((current) => ({ ...current, [fightUrl]: saved }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyFight("");
    }
  }

  async function clearPick(fightUrl) {
    setBusyFight(fightUrl);
    setError("");
    try {
      await deletePrediction(fightUrl);
      setPicks((current) => {
        const next = { ...current };
        delete next[fightUrl];
        return next;
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyFight("");
    }
  }

  function onPickFighter(fight, fighter) {
    const existing = picks[fight.fight_url];
    if (existing && existing.picked_fighter === fighter) {
      clearPick(fight.fight_url); // tap your pick again to undo it
    } else {
      applyPick(fight.fight_url, fighter, existing?.picked_method ?? null);
    }
  }

  function onPickMethod(fight, method) {
    const existing = picks[fight.fight_url];
    if (!existing) return;
    const next = existing.picked_method === method ? null : method;
    applyPick(fight.fight_url, existing.picked_fighter, next);
  }

  return (
    <div className="view">
      <header>
        <p className="eyebrow">Beat the engine</p>
        <h1 className="view-title">My Picks</h1>
      </header>

      <ErrorNote message={error} />

      {loading && cards.length === 0 && <Spinner label="Loading cards…" />}
      {!loading && cards.length === 0 && (
        <EmptyState title="No upcoming cards" message="Check back once the schedule is scraped." />
      )}

      {cards.length > 0 && (
        <div className="cards-layout">
          <aside className="event-list">
            {cards.map((card) => (
              <button
                key={card.event_id}
                type="button"
                className={`event-item ${selectedId === card.event_id ? "active" : ""}`}
                onClick={() => setSelectedId(card.event_id)}
              >
                <strong>{card.event_name}</strong>
                <span>{card.event_date}</span>
                <span className="muted">{card.event_location}</span>
                <Tag tone={isLocked(card.event_date) ? "neutral" : "gold"}>
                  {isLocked(card.event_date) ? "Locked" : `${card.fight_count} fights`}
                </Tag>
              </button>
            ))}
          </aside>

          <section className="event-detail">
            {detailLoading && <Spinner label="Loading card…" />}

            {!detailLoading && detail && (
              <SectionCard
                eyebrow={detail.event_date}
                title={detail.event_name}
                description={
                  locked
                    ? "This card is locked — picks are final."
                    : `Tap a fighter to pick the winner. ${pickedCount}/${detail.fights.length} picked.`
                }
              >
                <div className="fight-list">
                  {detail.fights.map((fight) => {
                    const pick = picks[fight.fight_url];
                    const busy = busyFight === fight.fight_url;
                    const odds = findOdds(oddsRows, fight.fight_url);
                    const stale =
                      pick &&
                      pick.picked_fighter !== fight.fighter_1 &&
                      pick.picked_fighter !== fight.fighter_2;
                    return (
                      <div className="pick-fight" key={fight.fight_url}>
                        <div className="pick-fight-meta">
                          <span className="muted">{fight.weight_class}</span>
                          {fight.prediction?.predicted_winner && (
                            <span className="muted">
                              engine favors {fight.prediction.predicted_winner}
                            </span>
                          )}
                          {stale && <Tag tone="warn">Card changed — re-pick</Tag>}
                        </div>
                        <div className="pick-options">
                          {[fight.fighter_1, fight.fighter_2].map((fighter, index) => {
                            const active = pick?.picked_fighter === fighter;
                            return (
                              <button
                                key={fighter}
                                type="button"
                                className={`pick-option ${active ? "active" : ""}`}
                                onClick={() => onPickFighter(fight, fighter)}
                                disabled={locked || busy}
                              >
                                <span className="pick-option-head">
                                  <FighterAvatar
                                    name={fighter}
                                    imageLookup={imageLookup}
                                    size="sm"
                                    corner={index === 0 ? "red" : "blue"}
                                  />
                                  <span className="pick-option-name">{fighter}</span>
                                </span>
                                <span className="pick-option-odds">
                                  <span>Model {pct(modelProb(fight.prediction, fighter))}</span>
                                  <span className="muted">Mkt {pct(marketProb(odds, fighter))}</span>
                                </span>
                              </button>
                            );
                          })}
                        </div>
                        {pick && !stale && (
                          <div className="pick-method-row">
                            <span className="pick-method-label">Method (optional)</span>
                            {METHODS.map((method) => (
                              <button
                                key={method.value}
                                type="button"
                                className={`pick-method ${
                                  pick.picked_method === method.value ? "active" : ""
                                }`}
                                onClick={() => onPickMethod(fight, method.value)}
                                disabled={locked || busy}
                              >
                                {method.label}
                              </button>
                            ))}
                            {!locked && (
                              <button
                                type="button"
                                className="pick-clear"
                                onClick={() => clearPick(fight.fight_url)}
                                disabled={busy}
                              >
                                Clear
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </SectionCard>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
