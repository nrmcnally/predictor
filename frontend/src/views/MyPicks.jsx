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

function boolValue(value) {
  return value === true || value === 1 || value === "1";
}

function methodLabel(value) {
  return METHODS.find((method) => method.value === value)?.label ?? null;
}

function isResolvedPick(pick) {
  return pick?.status === "scored" || pick?.status === "void";
}

function pickStatusInfo(pick, cardLocked = false, stale = false) {
  if (pick?.status === "scored") {
    const correct = boolValue(pick.result_correct);
    return {
      label: correct ? "Correct" : "Missed",
      tone: correct ? "win" : "loss",
      className: correct ? "result-win" : "result-loss",
      note: correct ? "Winner pick hit." : "Winner pick missed.",
    };
  }

  if (pick?.status === "void") {
    return {
      label: "Void",
      tone: "warn",
      className: "result-void",
      note: "Not graded because the bout changed or had no clean result.",
    };
  }

  if (stale) {
    return {
      label: "Card changed",
      tone: "warn",
      className: "result-void",
      note: cardLocked ? "This pick no longer matches the card." : "Re-pick this changed bout.",
    };
  }

  if (pick && (cardLocked || pick.locked)) {
    return {
      label: "Locked",
      tone: "neutral",
      className: "result-locked",
      note: "Awaiting official results.",
    };
  }

  if (pick) {
    return {
      label: "Open",
      tone: "gold",
      className: "result-open",
      note: "Editable until event day.",
    };
  }

  return {
    label: cardLocked ? "No pick" : "Open",
    tone: cardLocked ? "neutral" : "gold",
    className: "result-open",
    note: cardLocked ? "This fight is locked." : "",
  };
}

function sortPickDateDesc(a, b) {
  const aTime = new Date(a.event_date || 0).getTime();
  const bTime = new Date(b.event_date || 0).getTime();
  return (Number.isFinite(bTime) ? bTime : 0) - (Number.isFinite(aTime) ? aTime : 0);
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
  const [allPicks, setAllPicks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [busyFight, setBusyFight] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([getFutureCards(), getMyPredictions().catch(() => [])])
      .then(([rows, myPicks]) => {
        if (!active) return;
        setCards(rows);
        setAllPicks(myPicks);
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
    Promise.resolve()
      .then(() => {
        if (!active) return null;
        setDetailLoading(true);
        setError("");
        return Promise.all([
          getFutureCardPredictions(selectedId),
          getFutureFightOdds().catch(() => []),
          getMyPredictions(selectedId),
        ]);
      })
      .then((result) => {
        if (!result) return;
        const [card, odds, myPicks] = result;
        if (!active) return;
        setDetail(card);
        setOddsRows(Array.isArray(odds) ? odds : odds?.fights ?? []);
        const byUrl = {};
        for (const pick of myPicks) byUrl[pick.fight_url] = pick;
        setPicks(byUrl);
        setAllPicks((current) => {
          const refreshedUrls = new Set(myPicks.map((pick) => pick.fight_url));
          return [
            ...myPicks,
            ...current.filter((pick) => !refreshedUrls.has(pick.fight_url)),
          ];
        });
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
      setAllPicks((current) => [
        saved,
        ...current.filter((pick) => pick.fight_url !== fightUrl),
      ]);
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
      setAllPicks((current) => current.filter((pick) => pick.fight_url !== fightUrl));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyFight("");
    }
  }

  function onPickFighter(fight, fighter) {
    const existing = picks[fight.fight_url];
    if (isResolvedPick(existing)) return;
    if (existing && existing.picked_fighter === fighter) {
      clearPick(fight.fight_url); // tap your pick again to undo it
    } else {
      applyPick(fight.fight_url, fighter, existing?.picked_method ?? null);
    }
  }

  function onPickMethod(fight, method) {
    const existing = picks[fight.fight_url];
    if (!existing || isResolvedPick(existing)) return;
    const next = existing.picked_method === method ? null : method;
    applyPick(fight.fight_url, existing.picked_fighter, next);
  }

  const trackedPicks = useMemo(
    () =>
      allPicks
        .filter((pick) => pick.status === "scored" || pick.status === "void" || pick.locked)
        .sort(sortPickDateDesc)
        .slice(0, 12),
    [allPicks]
  );

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
                    const status = pickStatusInfo(pick, locked, stale);
                    const pickResolved = isResolvedPick(pick);
                    const pickDisabled = locked || busy || pickResolved;
                    return (
                      <div className="pick-fight" key={fight.fight_url}>
                        <div className="pick-fight-meta">
                          <span className="muted">{fight.weight_class}</span>
                          <Tag tone={status.tone}>{status.label}</Tag>
                          {fight.prediction?.predicted_winner && (
                            <span className="muted">
                              engine favors {fight.prediction.predicted_winner}
                            </span>
                          )}
                        </div>
                        <div className="pick-options">
                          {[fight.fighter_1, fight.fighter_2].map((fighter, index) => {
                            const active = pick?.picked_fighter === fighter;
                            return (
                              <button
                                key={fighter}
                                type="button"
                                className={`pick-option ${active ? "active" : ""} ${
                                  active ? status.className : ""
                                }`}
                                onClick={() => onPickFighter(fight, fighter)}
                                disabled={pickDisabled}
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
                        {pick && (
                          <div className="pick-method-row">
                            <span className="pick-method-label">
                              {pickResolved || stale ? "Pick status" : "Method (optional)"}
                            </span>
                            {!pickResolved &&
                              !stale &&
                              METHODS.map((method) => (
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
                            {pick.picked_method && (pickResolved || stale || locked) && (
                              <Tag>Method: {methodLabel(pick.picked_method)}</Tag>
                            )}
                            {pick.status === "scored" && pick.picked_method && (
                              <Tag tone={boolValue(pick.method_correct) ? "win" : "loss"}>
                                Method {boolValue(pick.method_correct) ? "hit" : "miss"}
                              </Tag>
                            )}
                            {status.note && (
                              <span className={`pick-status-note ${status.className}`}>
                                {status.note}
                              </span>
                            )}
                            {!locked && !pickResolved && (
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

      {trackedPicks.length > 0 && (
        <SectionCard
          eyebrow="Pick tracker"
          title="Locked & resolved picks"
          description="Locked picks are waiting for results. Scored and void picks update once official results are in."
          className="pick-history-card"
        >
          <div className="pick-history-list">
            {trackedPicks.map((pick) => {
              const status = pickStatusInfo(pick, pick.locked, false);
              return (
                <div
                  className={`pick-history-row ${status.className}`}
                  key={`${pick.event_id}-${pick.fight_url}`}
                >
                  <div className="pick-history-main">
                    <strong>{pick.picked_fighter}</strong>
                    <span>
                      {pick.fighter_1} vs {pick.fighter_2}
                    </span>
                    <span className="muted">
                      {pick.event_name} - {pick.event_date}
                    </span>
                  </div>

                  <div className="pick-history-meta">
                    {pick.picked_method && <Tag>Method: {methodLabel(pick.picked_method)}</Tag>}
                    {pick.status === "scored" && pick.picked_method && (
                      <Tag tone={boolValue(pick.method_correct) ? "win" : "loss"}>
                        Method {boolValue(pick.method_correct) ? "hit" : "miss"}
                      </Tag>
                    )}
                    <Tag tone={status.tone}>{status.label}</Tag>
                  </div>
                </div>
              );
            })}
          </div>
        </SectionCard>
      )}
    </div>
  );
}
