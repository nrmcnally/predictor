import { useContext, useEffect, useMemo, useState } from "react";
import { AppContext } from "../AppContext.js";
import { getRecentCardDetail, getRecentCards } from "../api/client.js";
import { FighterMatchup } from "../components/FighterDisplay.jsx";
import {
  EmptyState,
  ErrorNote,
  Spinner,
  SplitBar,
  StatTile,
  Tag,
} from "../components/ui.jsx";
import { clampProbability, parsePercentageText } from "../lib/format.js";

function statusTone(status = "") {
  const normalized = String(status).toLowerCase();

  if (normalized === "completed") {
    return "win";
  }

  if (normalized === "partially_completed") {
    return "warn";
  }

  return "neutral";
}

function statusLabel(status = "") {
  const normalized = String(status).toLowerCase();

  if (normalized === "completed") {
    return "Completed";
  }

  if (normalized === "partially_completed") {
    return "Partial results";
  }

  return "Waiting for results";
}

function fightResultState(fight) {
  if (!fight?.actual_result_available) {
    return "waiting";
  }

  if (
    !fight?.prediction_available ||
    fight.prediction_correct === null ||
    fight.prediction_correct === undefined
  ) {
    return "no-prediction";
  }

  return fight.prediction_correct ? "correct" : "incorrect";
}

function summarizeCard(card) {
  const fights = card?.fights ?? [];
  const scored = fights.filter(
    (fight) => fight.actual_result_available && fight.prediction_available
  );
  const correct = scored.filter((fight) => fight.prediction_correct).length;
  const waiting = fights.filter((fight) => !fight.actual_result_available).length;

  const marketScored = fights.filter(
    (fight) =>
      fight.actual_result_available &&
      fight.odds_available &&
      fight.market_correct !== null &&
      fight.market_correct !== undefined
  );
  const marketCorrect = marketScored.filter((fight) => fight.market_correct).length;

  return {
    total: fights.length,
    correct,
    wrong: scored.length - correct,
    waiting,
    accuracy: scored.length ? `${((correct / scored.length) * 100).toFixed(1)}%` : "N/A",
    marketAccuracy: marketScored.length
      ? `${((marketCorrect / marketScored.length) * 100).toFixed(1)}%`
      : "N/A",
  };
}

export default function RecentCards() {
  const { imageLookup, openProfile } = useContext(AppContext);

  const [cards, setCards] = useState([]);
  const [selectedCardId, setSelectedCardId] = useState("");
  const [selectedCard, setSelectedCard] = useState(null);
  const [expandedFightId, setExpandedFightId] = useState("");

  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadCards() {
      setLoading(true);
      setError("");

      try {
        const rows = await getRecentCards(true);

        const sorted = [...rows].sort(
          (a, b) => new Date(b.event_date) - new Date(a.event_date)
        );

        if (!cancelled) {
          setCards(sorted);

          if (sorted.length > 0) {
            setSelectedCardId((current) => current || sorted[0].event_id);
          }
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError.message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadCards();

    return () => {
      cancelled = true;
    };
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
        const data = await getRecentCardDetail(selectedCardId);

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

  const summary = useMemo(() => summarizeCard(selectedCard), [selectedCard]);

  return (
    <div className="view recent-cards">
      <header className="view-head">
        <div>
          <p className="eyebrow">Prediction tracking</p>
          <h1 className="view-title">Recent Cards</h1>
        </div>
      </header>

      <ErrorNote message={error} />

      <div className="cards-layout">
        <aside className="event-list">
          {loading && cards.length === 0 && <Spinner label="Loading saved cards…" />}
          {!loading && cards.length === 0 && (
            <EmptyState
              title="No saved cards"
              message="Run the update pipeline to save pre-fight prediction snapshots."
            />
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
              <div className="tag-row">
                <Tag tone={statusTone(card.status)}>{statusLabel(card.status)}</Tag>
                {card.accuracy_percentage && (
                  <Tag tone="gold">{card.accuracy_percentage} model</Tag>
                )}
              </div>
            </button>
          ))}
        </aside>

        <section className="event-detail">
          {detailLoading && <Spinner label="Loading results…" />}

          {!detailLoading && selectedCard && (
            <>
              <div className="tile-row five">
                <StatTile label="Fights" value={summary.total} />
                <StatTile label="Correct" value={summary.correct} tone="win" />
                <StatTile label="Wrong" value={summary.wrong} tone="loss" />
                <StatTile label="Waiting" value={summary.waiting} />
                <StatTile
                  label="Model vs market"
                  value={`${summary.accuracy} / ${summary.marketAccuracy}`}
                  hint="accuracy"
                />
              </div>

              <div className="fight-list">
                {selectedCard.fights?.map((fight) => {
                  const state = fightResultState(fight);
                  const expanded = expandedFightId === fight.fight_id;
                  const probability1 =
                    parsePercentageText(fight.fighter_1_percentage) ?? 0.5;

                  return (
                    <div
                      key={fight.fight_id}
                      className={`fight-row result-${state} ${expanded ? "expanded" : ""}`}
                    >
                      <div
                        role="button"
                        tabIndex={0}
                        className="fight-row-main"
                        onClick={() =>
                          setExpandedFightId(expanded ? "" : fight.fight_id)
                        }
                        onKeyDown={(event) => {
                          if (
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
                            <Tag>{fight.weight_class}</Tag>
                            <Tag
                              tone={
                                state === "correct"
                                  ? "win"
                                  : state === "incorrect"
                                    ? "loss"
                                    : "neutral"
                              }
                            >
                              {state === "correct"
                                ? "Correct"
                                : state === "incorrect"
                                  ? "Wrong"
                                  : state === "no-prediction"
                                    ? "No prediction"
                                    : "Waiting"}
                            </Tag>
                          </div>
                        </div>

                        <div className="fight-row-pick">
                          {fight.prediction_available && (
                            <>
                              <span className="pick-label">Pick</span>
                              <strong>{fight.predicted_winner}</strong>
                              <span className="pick-confidence">
                                {fight.confidence_percentage}
                              </span>
                            </>
                          )}
                          {fight.actual_result_available && (
                            <span className="actual-result">
                              Actual: <strong>{fight.actual_winner}</strong>
                              {fight.actual_method ? ` · ${fight.actual_method}` : ""}
                              {fight.actual_round ? ` · R${fight.actual_round}` : ""}
                            </span>
                          )}
                        </div>
                      </div>

                      {expanded && (
                        <div className="fight-row-detail">
                          <SplitBar
                            left={clampProbability(probability1)}
                            leftLabel={`${fight.fighter_1} · ${
                              fight.fighter_1_percentage || "N/A"
                            }`}
                            rightLabel={`${fight.fighter_2_percentage || "N/A"} · ${
                              fight.fighter_2
                            }`}
                          />

                          <div className="kv-grid">
                            <div className="kv-row">
                              <span>Confidence label</span>
                              <strong>{fight.confidence_label || "Unavailable"}</strong>
                            </div>
                            <div className="kv-row">
                              <span>Model</span>
                              <strong>{fight.model_name || "Unknown"}</strong>
                            </div>
                            <div className="kv-row">
                              <span>Market favorite</span>
                              <strong>
                                {fight.odds_available
                                  ? `${fight.market_favorite || "Unknown"} ${
                                      fight.market_favorite_percentage || ""
                                    }`
                                  : "Unavailable"}
                              </strong>
                            </div>
                            <div className="kv-row">
                              <span>Market result</span>
                              <strong>
                                {fight.market_correct === true
                                  ? "Correct"
                                  : fight.market_correct === false
                                    ? "Wrong"
                                    : "N/A"}
                              </strong>
                            </div>
                            <div className="kv-row">
                              <span>Saved at</span>
                              <strong>{fight.saved_at || "Unknown"}</strong>
                            </div>
                            {fight.actual_result_available && (
                              <div className="kv-row">
                                <span>Finish</span>
                                <strong>
                                  {fight.actual_method || "N/A"}
                                  {fight.actual_round ? ` · R${fight.actual_round}` : ""}
                                  {fight.actual_time ? ` · ${fight.actual_time}` : ""}
                                </strong>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {!detailLoading && !selectedCard && cards.length > 0 && (
            <EmptyState title="Select a card" message="Choose an event to review results." />
          )}
        </section>
      </div>
    </div>
  );
}
