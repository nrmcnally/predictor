import { useContext, useEffect, useMemo, useState } from "react";
import { AppContext } from "../AppContext.js";
import {
  getFutureCardPredictions,
  getFutureCards,
  getFutureFightOdds,
  refreshFutureCards,
} from "../api/client.js";
import { FighterMatchup } from "../components/FighterDisplay.jsx";
import {
  InsightsCard,
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

function OddsLine({ fight, odds }) {
  if (!odds || !odds.odds_available) {
    return <p className="odds-line muted">Market odds unavailable</p>;
  }

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
    </p>
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
              <div className="tile-row four">
                <StatTile label="Fights" value={summary.total} />
                <StatTile label="Predictions" value={summary.available} />
                <StatTile label="High confidence" value={summary.high} tone="win" />
                <StatTile label="Close fights" value={summary.close} tone="warn" />
              </div>

              <div className="fight-list">
                {selectedCard.fights?.map((fight) => {
                  const odds = findOdds(oddsRows, fight.fight_url);
                  const expanded = expandedFightId === fight.fight_id;
                  const prediction = fight.prediction;

                  return (
                    <div
                      key={fight.fight_id}
                      className={`fight-row ${expanded ? "expanded" : ""} ${
                        fight.prediction_available ? "has-prediction" : "no-prediction"
                      }`}
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
                            {prediction?.confidence_label && (
                              <Tag
                                tone={`conf-${getConfidenceClass(
                                  prediction.confidence_label
                                )}`}
                              >
                                {prediction.confidence_label}
                              </Tag>
                            )}
                          </div>
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
