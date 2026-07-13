import { useContext, useEffect, useMemo, useState } from "react";
import { AppContext } from "../AppContext.js";
import { getRecentCardDetail, getRecentCards } from "../api/client.js";
import { FighterMatchup } from "../components/FighterDisplay.jsx";
import { SkeletonRows } from "../components/Skeleton.jsx";
import {
  EmptyState,
  ErrorNote,
  SectionCard,
  SplitBar,
  StatTile,
  Tag,
} from "../components/ui.jsx";
import { clampProbability, parsePercentageText } from "../lib/format.js";
import { marketOutlierState } from "../lib/marketOutlier.js";

function fmtNum(value, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toFixed(digits);
}

const VERDICT_SHORT = {
  beat: "Ahead of market",
  matched: "Even with market",
  behind: "Behind market",
  no_market: "No odds saved",
};

// Below this many graded fights the cumulative grade / market edge / CLV verdicts
// are mostly noise, so show a "need N more" placeholder instead (ROADMAP §8b #11).
const MIN_GRADED_FIGHTS = 10;

function ReportCard({ grading, eyebrow, compact = false }) {
  if (!grading || !grading.scored_fights) {
    return null;
  }

  const verdict = grading.verdict || {};
  const skill = grading.brier_skill_vs_market;

  if (compact) {
    // Per-card header: the four numbers that answer "how did this card go" —
    // the deep cuts (expected wins, log loss) live on the Model record tab.
    return (
      <div className="tile-row four">
        <StatTile
          label="Engine grade"
          value={grading.engine_grade}
          tone={grading.engine_grade_tone}
          hint={`Brier ${fmtNum(grading.model_brier)}`}
        />
        <StatTile
          label="Market grade"
          value={grading.market_grade === "N/A" ? "—" : grading.market_grade}
          tone={grading.market_grade_tone}
          hint={
            grading.market_brier != null
              ? `Brier ${fmtNum(grading.market_brier)}`
              : "no odds saved"
          }
        />
        <StatTile
          label="vs Market"
          value={VERDICT_SHORT[verdict.code] || verdict.label || "—"}
          tone={verdict.tone}
          hint={
            skill != null
              ? `${skill >= 0 ? "+" : ""}${(skill * 100).toFixed(1)}% Brier edge`
              : undefined
          }
        />
        <StatTile
          label="Accuracy"
          value={`${grading.actual_correct}/${grading.scored_fights}`}
          hint={grading.accuracy_percentage}
        />
      </div>
    );
  }

  return (
    <SectionCard eyebrow={eyebrow} title={null} className="report-card">
      <div className="tile-row six">
        <StatTile
          label="Engine grade"
          value={grading.engine_grade}
          tone={grading.engine_grade_tone}
          hint={`Brier ${fmtNum(grading.model_brier)}`}
        />
        <StatTile
          label="Market grade"
          value={grading.market_grade === "N/A" ? "—" : grading.market_grade}
          tone={grading.market_grade_tone}
          hint={
            grading.market_brier != null
              ? `Brier ${fmtNum(grading.market_brier)}`
              : "no odds saved"
          }
        />
        <StatTile
          label="vs Market"
          value={VERDICT_SHORT[verdict.code] || verdict.label || "—"}
          tone={verdict.tone}
          hint={
            skill != null
              ? `${skill >= 0 ? "+" : ""}${(skill * 100).toFixed(1)}% Brier edge`
              : undefined
          }
        />
        <StatTile
          label="Accuracy"
          value={`${grading.actual_correct}/${grading.scored_fights}`}
          hint={grading.accuracy_percentage}
        />
        <StatTile
          label="Expected wins"
          value={grading.expected_correct_display || "—"}
          hint={`model expected · got ${grading.actual_correct}`}
        />
        <StatTile label="Log loss" value={fmtNum(grading.model_log_loss)} hint="lower is better" />
      </div>
      <p className="dim-note">
        Grades are Brier-based (probability quality), not just win/loss: A is
        market-elite (~0.20), C is coin-flip territory (~0.25). A single card is
        noisy — the overall grade across all cards is the real signal.
      </p>
    </SectionCard>
  );
}

const CARD_FILTERS = [
  { value: "review", label: "Review" },
  { value: "completed", label: "Completed" },
  { value: "waiting", label: "Waiting" },
  { value: "all", label: "All" },
];

function statusKey(status = "") {
  const normalized = String(status).toLowerCase();

  if (normalized === "completed") {
    return "completed";
  }

  if (normalized === "partially_completed") {
    return "partial";
  }

  return "waiting";
}

function cardMatchesFilter(card, filter) {
  const key = statusKey(card?.status);

  if (filter === "all") {
    return true;
  }

  if (filter === "review" || filter === "completed") {
    return filter === "review"
      ? key === "completed" || key === "partial"
      : key === "completed";
  }

  return key === "waiting";
}

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

  if (fight?.actual_is_cancelled || fight?.actual_outcome === "cancelled") {
    return "cancelled";
  }

  if (fight?.actual_is_no_contest || fight?.actual_outcome === "no_contest") {
    return "unscored";
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
    (fight) =>
      fight.actual_result_available &&
      fight.prediction_available &&
      fight.prediction_correct !== null &&
      fight.prediction_correct !== undefined
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

function EdgePanel({ edge }) {
  if (!edge || !edge.comparable_fights) {
    return null;
  }

  const disagree = edge.disagree || {};
  const verdict = disagree.verdict || {};

  return (
    <SectionCard
      eyebrow="Market edge"
      title="Where we disagree with the market"
      description="A model can only have an edge where it picks a different fighter than the market. Agreeing on the favorite is just chalk."
    >
      <div className="tile-row four">
        <StatTile
          label="Disagreement rate"
          value={edge.disagreement_rate_percentage || "—"}
          hint={`${edge.disagreement_count} of ${edge.comparable_fights} fights`}
        />
        <StatTile
          label="Contrarian record"
          value={disagree.count ? `${disagree.model_won_count}/${disagree.count}` : "—"}
          hint="our pick won, vs the favorite"
        />
        <StatTile
          label="Brier (us / market)"
          value={
            disagree.count
              ? `${fmtNum(disagree.model_brier)} / ${fmtNum(disagree.market_brier)}`
              : "—"
          }
        />
        <StatTile
          label="Verdict"
          value={disagree.count ? VERDICT_SHORT[verdict.code] || verdict.label || "—" : "—"}
          tone={verdict.tone}
        />
      </div>
      {edge.small_sample && (
        <p className="dim-note">
          Only {edge.disagreement_count} disagreement fights so far — far too few to
          conclude anything. This becomes meaningful as more cards complete.
        </p>
      )}
      <p className="dim-note">
        Matching the market when you agree is expected. The real test is whether the
        model beats the market on the fights where it deviates, over a large sample —
        that&apos;s the only place a genuine edge (or a leak) shows up.
      </p>
    </SectionCard>
  );
}

export default function RecentCards() {
  const { imageLookup, openProfile } = useContext(AppContext);

  const [cards, setCards] = useState([]);
  const [overall, setOverall] = useState(null);
  const [currentModel, setCurrentModel] = useState(null);
  const [selectedCardId, setSelectedCardId] = useState("");
  const [selectedCard, setSelectedCard] = useState(null);
  const [expandedFightId, setExpandedFightId] = useState("");
  const [statusFilter, setStatusFilter] = useState("review");
  // "cards" (browse + per-card detail) | "record" (all-time report + market edge)
  const [viewTab, setViewTab] = useState("cards");

  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadCards() {
      setLoading(true);
      setError("");

      try {
        const data = await getRecentCards(true);
        const rows = data?.cards ?? [];

        const sorted = [...rows].sort(
          (a, b) => new Date(b.event_date) - new Date(a.event_date)
        );

        if (!cancelled) {
          setCards(sorted);
          setOverall(data?.overall ?? null);
          setCurrentModel(data?.current_model ?? null);

          if (sorted.length > 0) {
            const defaultCard =
              sorted.find((card) => cardMatchesFilter(card, "review")) || sorted[0];

            setSelectedCardId((current) =>
              sorted.some((card) => card.event_id === current)
                ? current
                : defaultCard.event_id
            );
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

  const filteredCards = useMemo(
    () => cards.filter((card) => cardMatchesFilter(card, statusFilter)),
    [cards, statusFilter]
  );

  const filterCounts = useMemo(
    () =>
      CARD_FILTERS.reduce((counts, filter) => {
        counts[filter.value] = cards.filter((card) =>
          cardMatchesFilter(card, filter.value)
        ).length;
        return counts;
      }, {}),
    [cards]
  );

  const summary = useMemo(() => summarizeCard(selectedCard), [selectedCard]);

  function handleFilterChange(filterValue) {
    setStatusFilter(filterValue);

    const currentCard = cards.find((card) => card.event_id === selectedCardId);

    if (currentCard && cardMatchesFilter(currentCard, filterValue)) {
      return;
    }

    const nextCard = cards.find((card) => cardMatchesFilter(card, filterValue));

    if (nextCard) {
      setSelectedCardId(nextCard.event_id);
    } else {
      setSelectedCardId("");
      setSelectedCard(null);
      setExpandedFightId("");
    }
  }

  return (
    <div className="view recent-cards">
      <header className="view-head">
        <div>
          <p className="eyebrow">Prediction tracking</p>
          <h1 className="view-title">Card results</h1>
        </div>
        {currentModel?.model_version && (
          <Tag tone="neutral">
            Live model v{currentModel.model_version}
            {currentModel.recipe_hash ? ` · ${currentModel.recipe_hash.slice(0, 7)}` : ""}
          </Tag>
        )}
      </header>

      <ErrorNote message={error} />

      <div className="segmented view-tabs" aria-label="Card results sections">
        {[
          { value: "cards", label: "Cards" },
          { value: "record", label: "Model record" },
        ].map((tab) => (
          <button
            key={tab.value}
            type="button"
            className={viewTab === tab.value ? "active" : ""}
            aria-pressed={viewTab === tab.value}
            onClick={() => setViewTab(tab.value)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {viewTab === "record" && (
        <>
          {overall && overall.scored_fights > 0 && overall.scored_fights < MIN_GRADED_FIGHTS && (
            <SectionCard eyebrow="Overall report card" title={null} className="report-card">
              <p className="dim-note">
                Need {MIN_GRADED_FIGHTS - overall.scored_fights} more graded fight
                {MIN_GRADED_FIGHTS - overall.scored_fights === 1 ? "" : "s"} before the overall
                grade, market edge, and CLV verdicts are meaningful ({overall.scored_fights}/
                {MIN_GRADED_FIGHTS} so far). A handful of fights is mostly noise.
              </p>
            </SectionCard>
          )}

          {overall && overall.scored_fights >= MIN_GRADED_FIGHTS && (
            <ReportCard
              grading={overall}
              eyebrow={`Overall report card · ${overall.graded_card_count || 0} cards, ${
                overall.scored_fights
              } graded fights`}
            />
          )}

          {overall?.edge && overall.scored_fights >= MIN_GRADED_FIGHTS && (
            <EdgePanel edge={overall.edge} />
          )}

          {(!overall || !overall.scored_fights) && (
            <EmptyState
              title="No graded fights yet"
              message="The model record builds as cards complete and results are scored."
            />
          )}
        </>
      )}

      {viewTab === "cards" && (
      <div className="cards-layout">
        <aside className="event-list">
          <div className="event-filter segmented">
            {CARD_FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                className={statusFilter === filter.value ? "active" : ""}
                onClick={() => handleFilterChange(filter.value)}
              >
                {filter.label}
                <span>{filterCounts[filter.value] ?? 0}</span>
              </button>
            ))}
          </div>

          {loading && cards.length === 0 && <SkeletonRows rows={4} height={104} />}
          {!loading && cards.length === 0 && (
            <EmptyState
              title="No saved cards"
              message="Run the update pipeline to save pre-fight prediction snapshots."
            />
          )}
          {!loading && cards.length > 0 && filteredCards.length === 0 && (
            <EmptyState
              title="No cards in this filter"
              message="Switch filters to review another part of the schedule."
            />
          )}

          {filteredCards.map((card) => (
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
                {card.snapshot_generation === "older" && (
                  <Tag tone="warn">
                    {card.snapshot_version_estimated ? "~v" : "v"}
                    {card.snapshot_model_version}
                  </Tag>
                )}
                {card.snapshot_generation === "unknown" && (
                  <Tag tone="neutral">unversioned</Tag>
                )}
              </div>
            </button>
          ))}
        </aside>

        <section className="event-detail">
          {detailLoading && <SkeletonRows rows={5} height={96} />}

          {!detailLoading && selectedCard && (
            <>
              <ReportCard grading={selectedCard.grading} compact />

              {!selectedCard.grading?.scored_fights && summary.total > 0 && (
                <div className="tile-row four">
                  <StatTile label="Fights" value={summary.total} />
                  <StatTile label="Waiting" value={summary.waiting} />
                </div>
              )}

              {(summary.waiting > 0 || selectedCard.snapshot_generation) && (
              <p className="dim-note snapshot-note">
                {summary.waiting > 0
                  ? `${summary.waiting} fight${summary.waiting === 1 ? "" : "s"} still waiting for results. `
                  : ""}
                {selectedCard.snapshot_generation
                  ? `Predicted by ${
                      selectedCard.snapshot_model_version
                        ? `model ${selectedCard.snapshot_version_estimated ? "~v" : "v"}${selectedCard.snapshot_model_version}`
                        : "an unversioned snapshot"
                    }${
                      selectedCard.snapshot_generation === "older"
                        ? ` — older than the live model${
                            currentModel?.model_version ? ` (v${currentModel.model_version})` : ""
                          }`
                        : selectedCard.snapshot_generation === "current"
                          ? " — same generation as the live model"
                          : ""
                    }.`
                  : ""}
              </p>
              )}

              <div className="fight-list">
                {selectedCard.fights?.map((fight) => {
                  const state = fightResultState(fight);
                  const marketOutlier = marketOutlierState(fight);
                  const expanded = expandedFightId === fight.fight_id;
                  const probability1 =
                    parsePercentageText(fight.fighter_1_percentage) ?? 0.5;

                  return (
                    <div
                      key={fight.fight_id}
                      className={`fight-row result-${state} ${marketOutlier} ${
                        expanded ? "expanded" : ""
                      }`}
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
                            {fight.scheduled_rounds && (
                              <Tag tone={fight.scheduled_rounds === 5 ? "gold" : "neutral"}>
                                {fight.scheduled_rounds} rounds
                              </Tag>
                            )}
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
                                  : state === "cancelled"
                                    ? "Cancelled"
                                    : state === "unscored"
                                      ? "Unscored"
                                      : state === "no-prediction"
                                        ? "No prediction"
                                        : "Waiting"}
                            </Tag>
                            {fight.model_quality?.label &&
                              (state === "correct" || state === "incorrect") && (
                                <Tag tone={fight.model_quality.tone}>
                                  {fight.model_quality.label}
                                </Tag>
                              )}
                            {marketOutlier === "market-beat" && (
                              <Tag tone="win">Beat the market</Tag>
                            )}
                            {marketOutlier === "market-lost" && (
                              <Tag tone="loss">Market won</Tag>
                            )}
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
                              Actual:{" "}
                              <strong>
                                {fight.actual_is_cancelled ||
                                fight.actual_outcome === "cancelled"
                                  ? "Cancelled"
                                  : fight.actual_is_no_contest ||
                                fight.actual_outcome === "no_contest"
                                  ? "No contest"
                                  : fight.actual_winner}
                              </strong>
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
                            {fight.model_p_winner != null && (
                              <div className="kv-row">
                                <span>Prob. on actual winner</span>
                                <strong>
                                  {`Model ${(fight.model_p_winner * 100).toFixed(0)}%`}
                                  {fight.market_p_winner != null
                                    ? ` · Market ${(fight.market_p_winner * 100).toFixed(0)}%`
                                    : ""}
                                </strong>
                              </div>
                            )}
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
      )}
    </div>
  );
}
