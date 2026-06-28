import { useContext, useEffect, useMemo, useState } from "react";
import { AppContext } from "../AppContext.js";
import {
  getFutureCardPredictions,
  getFutureCards,
  getFutureFightOdds,
  refreshFutureCards,
  updateFutureFightScheduledRounds,
} from "../api/client.js";
import { FighterMatchup } from "../components/FighterDisplay.jsx";
import {
  InsightsCard,
  RiskFlagsCard,
  VerdictCard,
} from "../components/PredictionBreakdown.jsx";
import {
  EmptyState,
  ErrorNote,
  SectionCard,
  Spinner,
  StatTile,
  Tag,
} from "../components/ui.jsx";
import { formatAmericanOdds, getConfidenceClass } from "../lib/format.js";

function normalizeFightUrl(value) {
  return String(value || "")
    .replace("https://www.", "https://")
    .replace("http://www.", "http://")
    .replace(/\/$/, "");
}

function findOdds(oddsRows, fightUrl) {
  if (!Array.isArray(oddsRows) || !fightUrl) {
    return null;
  }

  const normalized = normalizeFightUrl(fightUrl);

  return oddsRows.find((row) => normalizeFightUrl(row.fight_url) === normalized) || null;
}

function normalizeName(value) {
  return String(value || "")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase();
}

function getMarketSignal(prediction, odds) {
  if (!prediction || !odds?.odds_available || !odds.market_favorite) {
    return null;
  }

  const split =
    normalizeName(prediction.predicted_winner) !== normalizeName(odds.market_favorite);

  return {
    className: split ? "market-split" : "market-agrees",
    label: split ? "Model-market split" : "Market agrees",
    tone: split ? "warn" : "win",
  };
}

function getProbabilityForFighter(prediction, fighterName) {
  const normalized = normalizeName(fighterName);

  if (normalizeName(prediction?.fighter_a) === normalized) {
    return Number(prediction.fighter_a_probability);
  }

  if (normalizeName(prediction?.fighter_b) === normalized) {
    return Number(prediction.fighter_b_probability);
  }

  return null;
}

function getMarketProbabilityForFighter(odds, fighterName) {
  const normalized = normalizeName(fighterName);

  if (normalizeName(odds?.fighter_1) === normalized) {
    return Number(odds.fighter_1_market_probability);
  }

  if (normalizeName(odds?.fighter_2) === normalized) {
    return Number(odds.fighter_2_market_probability);
  }

  return null;
}

function formatProbabilityPointDelta(delta) {
  if (!Number.isFinite(delta)) {
    return "N/A";
  }

  const points = delta * 100;
  return `${points >= 0 ? "+" : ""}${points.toFixed(1)} pts`;
}

function getMarketEdge(prediction, odds) {
  if (!prediction || !odds?.odds_available || !odds.market_favorite) {
    return null;
  }

  const predictedWinner = prediction.predicted_winner;
  const modelProbability = getProbabilityForFighter(prediction, predictedWinner);
  const marketProbability = getMarketProbabilityForFighter(odds, predictedWinner);

  if (!Number.isFinite(modelProbability) || !Number.isFinite(marketProbability)) {
    return null;
  }

  return {
    fighter: predictedWinner,
    modelProbability,
    marketProbability,
    delta: modelProbability - marketProbability,
  };
}

function summarizeCard(card) {
  const fights = card?.fights ?? [];
  const available = fights.filter((fight) => fight.prediction_available && fight.prediction);

  const byClass = (targets) =>
    available.filter((fight) =>
      targets.includes(getConfidenceClass(fight.prediction.confidence_label))
    ).length;

  return {
    total: fights.length,
    available: available.length,
    unavailable: fights.length - available.length,
    high: byClass(["high", "strong"]),
    close: byClass(["close"]),
  };
}

function summarizeMarkets(card, oddsRows) {
  const fights = card?.fights ?? [];

  return fights.reduce(
    (summary, fight) => {
      const signal = getMarketSignal(fight.prediction, findOdds(oddsRows, fight.fight_url));

      if (!signal) {
        return summary;
      }

      if (signal.className === "market-split") {
        summary.splits += 1;
      } else {
        summary.agrees += 1;
      }

      return summary;
    },
    { splits: 0, agrees: 0 }
  );
}

function OddsLine({ fight, odds }) {
  if (!odds || !odds.odds_available) {
    return <p className="odds-line muted">Market odds unavailable</p>;
  }

  const marketEdge = getMarketEdge(fight.prediction, odds);

  return (
    <p className="odds-line">
      <span>
        Market: <strong>{odds.market_favorite || "Unknown"}</strong>{" "}
        {odds.market_favorite_percentage || ""}
      </span>
      <span>
        {fight.fighter_1}: {formatAmericanOdds(odds.fighter_1_odds_american)} ·{" "}
        {odds.fighter_1_market_percentage || "N/A"}
      </span>
      <span>
        {fight.fighter_2}: {formatAmericanOdds(odds.fighter_2_odds_american)} ·{" "}
        {odds.fighter_2_market_percentage || "N/A"}
      </span>
      {odds.odds_bookmaker && (
        <span className="muted">
          {odds.odds_bookmaker}
          {odds.bookmakers_matched ? ` · ${odds.bookmakers_matched} books` : ""}
        </span>
      )}
      {marketEdge && (
        <span>
          Model edge on pick:{" "}
          <strong>{formatProbabilityPointDelta(marketEdge.delta)}</strong>
        </span>
      )}
    </p>
  );
}

function RoundOverrideControl({ fight, disabled, onChange }) {
  if (!fight?.round_override_eligible) {
    return null;
  }

  return (
    <div
      className="round-toggle segmented"
      aria-label={`${fight.fighter_1} vs ${fight.fighter_2} scheduled rounds`}
      onClick={(event) => event.stopPropagation()}
    >
      {[3, 5].map((rounds) => (
        <button
          key={rounds}
          type="button"
          className={Number(fight.scheduled_rounds) === rounds ? "active" : ""}
          disabled={disabled}
          onClick={() => onChange(fight, rounds)}
        >
          {rounds}
        </button>
      ))}
    </div>
  );
}

export default function FutureCards() {
  const { imageLookup, openProfile } = useContext(AppContext);

  const [cards, setCards] = useState([]);
  const [selectedCardId, setSelectedCardId] = useState("");
  const [selectedCard, setSelectedCard] = useState(null);
  const [oddsRows, setOddsRows] = useState([]);
  const [expandedFightId, setExpandedFightId] = useState("");

  const [cardsLoading, setCardsLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [savingRoundFightId, setSavingRoundFightId] = useState("");
  const [error, setError] = useState("");

  async function loadCards() {
    setCardsLoading(true);
    setError("");

    try {
      const [cardRows, odds] = await Promise.all([
        getFutureCards(),
        getFutureFightOdds().catch(() => []),
      ]);

      setCards(cardRows);
      setOddsRows(odds);

      if (cardRows.length > 0) {
        setSelectedCardId((current) => current || cardRows[0].event_id);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setCardsLoading(false);
    }
  }

  useEffect(() => {
    async function init() {
      await loadCards();
    }

    init();
  }, []);

  useEffect(() => {
    if (!selectedCardId) {
      return;
    }

    let cancelled = false;

    async function loadDetail() {
      setDetailLoading(true);
      setSelectedCard(null);
      setExpandedFightId("");

      try {
        const data = await getFutureCardPredictions(selectedCardId);

        if (!cancelled) {
          setSelectedCard(data);
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError.message);
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    }

    loadDetail();

    return () => {
      cancelled = true;
    };
  }, [selectedCardId]);

  async function handleRoundOverride(fight, scheduledRounds) {
    if (Number(fight.scheduled_rounds) === Number(scheduledRounds)) {
      return;
    }

    setSavingRoundFightId(fight.fight_id);
    setError("");

    try {
      const result = await updateFutureFightScheduledRounds(
        selectedCardId,
        fight.fight_id,
        scheduledRounds
      );

      if (result?.card) {
        setSelectedCard(result.card);
      } else {
        const data = await getFutureCardPredictions(selectedCardId);
        setSelectedCard(data);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSavingRoundFightId("");
    }
  }

  async function handleRefresh() {
    setCardsLoading(true);
    setError("");

    try {
      await refreshFutureCards();
      await loadCards();
    } catch (requestError) {
      setError(requestError.message);
      setCardsLoading(false);
    }
  }

  const summary = useMemo(() => summarizeCard(selectedCard), [selectedCard]);
  const marketSummary = useMemo(
    () => summarizeMarkets(selectedCard, oddsRows),
    [selectedCard, oddsRows]
  );

  return (
    <div className="view future-cards">
      <header className="view-head">
        <div>
          <p className="eyebrow">Upcoming schedule</p>
          <h1 className="view-title">Future Cards</h1>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={handleRefresh}
          disabled={cardsLoading}
        >
          ⟳ Refresh cards
        </button>
      </header>

      <ErrorNote message={error} />

      <div className="cards-layout">
        <aside className="event-list">
          {cardsLoading && cards.length === 0 && <Spinner label="Loading cards…" />}
          {!cardsLoading && cards.length === 0 && (
            <EmptyState title="No upcoming cards" message="Refresh to scrape the schedule." />
          )}

          {cards.map((card) => (
            <button
              key={card.event_id}
              type="button"
              className={`event-item ${selectedCardId === card.event_id ? "active" : ""}`}
              onClick={() => setSelectedCardId(card.event_id)}
            >
              <strong>{card.event_name}</strong>
              <span>{card.event_date}</span>
              <span className="muted">{card.event_location}</span>
              <Tag tone="neutral">{card.fight_count} fights</Tag>
            </button>
          ))}
        </aside>

        <section className="event-detail">
          {detailLoading && <Spinner label="Predicting card…" />}

          {!detailLoading && selectedCard && (
            <>
              <div className="tile-row five">
                <StatTile label="Fights" value={summary.total} />
                <StatTile label="Predictions" value={summary.available} />
                <StatTile label="High confidence" value={summary.high} tone="win" />
                <StatTile label="Close fights" value={summary.close} tone="warn" />
                <StatTile
                  label="Market splits"
                  value={marketSummary.splits}
                  hint={`${marketSummary.agrees} agree`}
                  tone={marketSummary.splits ? "warn" : "default"}
                />
              </div>

              <div className="fight-list">
                {selectedCard.fights?.map((fight) => {
                  const odds = findOdds(oddsRows, fight.fight_url);
                  const expanded = expandedFightId === fight.fight_id;
                  const prediction = fight.prediction;
                  const marketSignal = getMarketSignal(prediction, odds);

                  return (
                    <div
                      key={fight.fight_id}
                      className={`fight-row ${expanded ? "expanded" : ""} ${
                        fight.prediction_available ? "has-prediction" : "no-prediction"
                      } ${marketSignal?.className || ""}`}
                    >
                      <div
                        role={fight.prediction_available ? "button" : undefined}
                        tabIndex={fight.prediction_available ? 0 : undefined}
                        className="fight-row-main"
                        onClick={
                          fight.prediction_available
                            ? () => setExpandedFightId(expanded ? "" : fight.fight_id)
                            : undefined
                        }
                        onKeyDown={(event) => {
                          if (
                            fight.prediction_available &&
                            (event.key === "Enter" || event.key === " ") &&
                            event.target === event.currentTarget
                          ) {
                            event.preventDefault();
                            setExpandedFightId(expanded ? "" : fight.fight_id);
                          }
                        }}
                      >
                        <div className="fight-row-left">
                          <FighterMatchup
                            fighter1={fight.fighter_1}
                            fighter2={fight.fighter_2}
                            imageLookup={imageLookup}
                            onFighterClick={openProfile}
                          />
                          <div className="tag-row">
                            <Tag>{fight.weight_class || "Weight class unknown"}</Tag>
                            {fight.scheduled_rounds && (
                              <Tag tone={fight.scheduled_rounds === 5 ? "gold" : "neutral"}>
                                {fight.scheduled_rounds} rounds
                              </Tag>
                            )}
                            <RoundOverrideControl
                              fight={fight}
                              disabled={savingRoundFightId === fight.fight_id}
                              onChange={handleRoundOverride}
                            />
                            {prediction?.confidence_label && (
                              <Tag
                                tone={`conf-${getConfidenceClass(
                                  prediction.confidence_label
                                )}`}
                              >
                                {prediction.confidence_label}
                              </Tag>
                            )}
                            {prediction?.data_reliability &&
                              prediction.data_reliability.level !== "ok" && (
                                <Tag
                                  tone={
                                    prediction.data_reliability.level === "very_limited"
                                      ? "loss"
                                      : "warn"
                                  }
                                >
                                  {prediction.data_reliability.label}
                                </Tag>
                              )}
                            {marketSignal && (
                              <Tag tone={marketSignal.tone} className="market-signal">
                                {marketSignal.label}
                              </Tag>
                            )}
                          </div>
                          {prediction && (
                            <RiskFlagsCard prediction={prediction} compact />
                          )}
                        </div>

                        {fight.prediction_available && prediction ? (
                          <div className="fight-row-pick">
                            <span className="pick-label">Pick</span>
                            <strong>{prediction.predicted_winner}</strong>
                            <span className="pick-confidence">
                              {prediction.confidence_percentage}
                            </span>
                          </div>
                        ) : (
                          <div className="fight-row-pick none">
                            <span className="pick-label">No prediction</span>
                            <span className="muted">
                              {fight.error?.message ?? "Missing fighter data"}
                            </span>
                          </div>
                        )}
                      </div>

                      <OddsLine fight={fight} odds={odds} />

                      {expanded && prediction && (
                        <div className="fight-row-detail">
                          <VerdictCard
                            prediction={prediction}
                            imageLookup={imageLookup}
                            onFighterClick={openProfile}
                          />
                          <RiskFlagsCard prediction={prediction} />
                          <InsightsCard prediction={prediction} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <SectionCard className="note-card">
                <p className="dim-note">
                  Method predictions are intentionally excluded here — they are noisier
                  than winner predictions. Odds are comparison-only and never used as
                  model features.
                </p>
              </SectionCard>
            </>
          )}

          {!detailLoading && !selectedCard && cards.length > 0 && (
            <EmptyState title="Select a card" message="Choose an event to see predictions." />
          )}
        </section>
      </div>
    </div>
  );
}
