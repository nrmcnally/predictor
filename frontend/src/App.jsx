import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_BASE_URL = "http://127.0.0.1:8000";

function formatEdgeDifference(edge) {
  if (edge.difference === null || edge.difference === undefined) {
    return "Unknown";
  }

  const sign = edge.difference > 0 ? "+" : "";
  const value = Number(edge.difference).toFixed(2);

  return edge.unit ? `${sign}${value} ${edge.unit}` : `${sign}${value}`;
}

function getProbabilityWidth(probability) {
  if (!Number.isFinite(probability)) {
    return "0%";
  }

  return `${Math.max(0, Math.min(100, probability * 100))}%`;
}

function parsePercentageText(value) {
  if (!value) {
    return null;
  }

  const parsed = Number(String(value).replace("%", ""));

  if (!Number.isFinite(parsed)) {
    return null;
  }

  return parsed / 100;
}

function PredictionDetails({ prediction }) {
  const winnerSide = useMemo(() => {
    if (!prediction) {
      return null;
    }

    if (prediction.predicted_winner === prediction.fighter_a) {
      return "fighter_a";
    }

    if (prediction.predicted_winner === prediction.fighter_b) {
      return "fighter_b";
    }

    return null;
  }, [prediction]);

  if (!prediction) {
    return (
      <div className="empty-state">
        <h2>No fight selected</h2>
        <p>Select or run a fight prediction to see details.</p>
      </div>
    );
  }

  const insights = prediction.matchup_insights;

  const predictedInsightKey =
    prediction.predicted_winner === prediction.fighter_a ? "fighter_a" : "fighter_b";

  const opponentInsightKey =
    predictedInsightKey === "fighter_a" ? "fighter_b" : "fighter_a";

  const predictedFighterInsights = insights?.[predictedInsightKey];
  const opponentFighterInsights = insights?.[opponentInsightKey];

  const predictedConcernEdgeLabels = new Set(
    predictedFighterInsights?.concerns?.map((item) => item.edge_label) ?? []
  );

  const uniqueOpponentPaths =
    opponentFighterInsights?.strengths?.filter(
      (item) => !predictedConcernEdgeLabels.has(item.edge_label)
    ) ?? [];

  return (
    <>
      <div className="winner-card">
        <p className="eyebrow">Predicted winner</p>
        <h2>{prediction.predicted_winner}</h2>
        <p>{prediction.confidence_label}</p>
        <strong>{prediction.confidence_percentage}</strong>
      </div>

      <div className="probability-grid">
        <div className={`fighter-result ${winnerSide === "fighter_a" ? "winner" : ""}`}>
          <div className="fighter-result-header">
            <h3>{prediction.fighter_a}</h3>
            <strong>{prediction.fighter_a_percentage}</strong>
          </div>
          <div className="probability-bar">
            <div
              className="probability-fill"
              style={{
                width: getProbabilityWidth(prediction.fighter_a_probability),
              }}
            />
          </div>
        </div>

        <div className={`fighter-result ${winnerSide === "fighter_b" ? "winner" : ""}`}>
          <div className="fighter-result-header">
            <h3>{prediction.fighter_b}</h3>
            <strong>{prediction.fighter_b_percentage}</strong>
          </div>
          <div className="probability-bar">
            <div
              className="probability-fill"
              style={{
                width: getProbabilityWidth(prediction.fighter_b_probability),
              }}
            />
          </div>
        </div>
      </div>

      {insights && predictedFighterInsights && opponentFighterInsights && (
        <div className="insights-card">
          <h2>Why this prediction?</h2>

          <div className="insight-summary-list">
            {insights.summary?.map((item, index) => (
              <div className={`insight-summary ${item.type}`} key={`${item.type}-${index}`}>
                {item.text}
              </div>
            ))}
          </div>

          <div className="explanation-layout">
            <div className="explanation-section">
              <h3>Support for {prediction.predicted_winner}</h3>

              {predictedFighterInsights.strengths.length === 0 && (
                <p>No major rule-based support edges found.</p>
              )}

              {predictedFighterInsights.strengths.map((item, index) => (
                <div className={`insight-item ${item.severity}`} key={`pick-strength-${index}`}>
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                </div>
              ))}
            </div>

            <div className="explanation-section">
              <h3>Reasons to be cautious</h3>

              {predictedFighterInsights.concerns.length === 0 && (
                <p>No major rule-based concerns found for the pick.</p>
              )}

              {predictedFighterInsights.concerns.map((item, index) => (
                <div
                  className={`insight-item concern ${item.severity}`}
                  key={`pick-concern-${index}`}
                >
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                </div>
              ))}
            </div>

            <div className="explanation-section full-width">
              <h3>Opponent’s unique path</h3>

              {uniqueOpponentPaths.length === 0 && (
                <p>
                  The opponent’s biggest edges are already covered in the caution section.
                </p>
              )}

              {uniqueOpponentPaths.map((item, index) => (
                <div className={`insight-item ${item.severity}`} key={`opponent-path-${index}`}>
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="edges-card">
        <h2>Basic matchup edges</h2>

        <div className="edges-list">
          {prediction.basic_matchup_edges.map((edge) => (
            <div className="edge-row" key={edge.label}>
              <div>
                <strong>{edge.label}</strong>
                <span>
                  {prediction.fighter_a} vs {prediction.fighter_b}
                </span>
              </div>
              <strong>{formatEdgeDifference(edge)}</strong>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function RecentFightDetails({ fight }) {
  if (!fight) {
    return (
      <div className="empty-state">
        <h2>No recent fight selected</h2>
        <p>Select a saved fight prediction to see the result comparison.</p>
      </div>
    );
  }

  const fighter1Probability = parsePercentageText(fight.fighter_1_percentage);
  const fighter2Probability = parsePercentageText(fight.fighter_2_percentage);

  const resultClass = fight.actual_result_available
    ? fight.prediction_correct
      ? "correct"
      : "incorrect"
    : "waiting";

  return (
    <>
      <div className={`recent-result-card ${resultClass}`}>
        <p className="eyebrow">Prediction result</p>

        <h2>
          {fight.actual_result_available
            ? fight.prediction_correct
              ? "Correct prediction"
              : "Incorrect prediction"
            : "Waiting for results"}
        </h2>

        {fight.prediction_available ? (
          <p>
            Predicted <strong>{fight.predicted_winner}</strong> at{" "}
            <strong>{fight.confidence_percentage}</strong> confidence.
          </p>
        ) : (
          <p>No saved prediction was available for this fight.</p>
        )}

        {fight.actual_result_available && (
          <p>
            Actual winner: <strong>{fight.actual_winner}</strong>
            {fight.actual_method && (
              <>
                {" "}
                by {fight.actual_method}
                {fight.actual_round && `, Round ${fight.actual_round}`}
                {fight.actual_time && ` at ${fight.actual_time}`}
              </>
            )}
          </p>
        )}
      </div>

      <div className="probability-grid">
        <div
          className={`fighter-result ${
            fight.predicted_winner === fight.fighter_1 ? "winner" : ""
          }`}
        >
          <div className="fighter-result-header">
            <h3>{fight.fighter_1}</h3>
            <strong>{fight.fighter_1_percentage || "N/A"}</strong>
          </div>
          <div className="probability-bar">
            <div
              className="probability-fill"
              style={{
                width: getProbabilityWidth(fighter1Probability ?? 0),
              }}
            />
          </div>
        </div>

        <div
          className={`fighter-result ${
            fight.predicted_winner === fight.fighter_2 ? "winner" : ""
          }`}
        >
          <div className="fighter-result-header">
            <h3>{fight.fighter_2}</h3>
            <strong>{fight.fighter_2_percentage || "N/A"}</strong>
          </div>
          <div className="probability-bar">
            <div
              className="probability-fill"
              style={{
                width: getProbabilityWidth(fighter2Probability ?? 0),
              }}
            />
          </div>
        </div>
      </div>

      <div className="edges-card">
        <h2>Saved prediction details</h2>

        <div className="edges-list">
          <div className="edge-row">
            <div>
              <strong>Predicted winner</strong>
              <span>Model pick before the card result was known</span>
            </div>
            <strong>{fight.predicted_winner || "Unavailable"}</strong>
          </div>

          <div className="edge-row">
            <div>
              <strong>Actual winner</strong>
              <span>Filled once the completed event is scraped</span>
            </div>
            <strong>{fight.actual_winner || "Waiting"}</strong>
          </div>

          <div className="edge-row">
            <div>
              <strong>Confidence label</strong>
              <span>Saved model confidence bucket</span>
            </div>
            <strong>{fight.confidence_label || "Unavailable"}</strong>
          </div>

          <div className="edge-row">
            <div>
              <strong>Model</strong>
              <span>Model used when the prediction was saved</span>
            </div>
            <strong>{fight.model_name || "Unknown"}</strong>
          </div>

          <div className="edge-row">
            <div>
              <strong>Saved at</strong>
              <span>When this prediction snapshot was saved</span>
            </div>
            <strong>{fight.saved_at || "Unknown"}</strong>
          </div>
        </div>
      </div>
    </>
  );
}

function App() {
  const [activeView, setActiveView] = useState("single");

  const [fighterA, setFighterA] = useState("Khamzat Chimaev");
  const [fighterB, setFighterB] = useState("Sean Strickland");
  const [weightClass, setWeightClass] = useState("Middleweight");

  const [weightClasses, setWeightClasses] = useState([]);
  const [singlePrediction, setSinglePrediction] = useState(null);

  const [fighterASearchResults, setFighterASearchResults] = useState([]);
  const [fighterBSearchResults, setFighterBSearchResults] = useState([]);

  const [futureCards, setFutureCards] = useState([]);
  const [selectedCardId, setSelectedCardId] = useState("");
  const [selectedCard, setSelectedCard] = useState(null);
  const [selectedFightPrediction, setSelectedFightPrediction] = useState(null);

  const [recentCards, setRecentCards] = useState([]);
  const [selectedRecentCardId, setSelectedRecentCardId] = useState("");
  const [selectedRecentCard, setSelectedRecentCard] = useState(null);
  const [selectedRecentFight, setSelectedRecentFight] = useState(null);

  const [updateStatus, setUpdateStatus] = useState(null);
  const [latestReport, setLatestReport] = useState(null);

  const [loading, setLoading] = useState(false);
  const [cardsLoading, setCardsLoading] = useState(false);
  const [cardPredictionsLoading, setCardPredictionsLoading] = useState(false);
  const [recentLoading, setRecentLoading] = useState(false);
  const [updateLoading, setUpdateLoading] = useState(false);

  const [error, setError] = useState("");
  const [cardsError, setCardsError] = useState("");
  const [recentError, setRecentError] = useState("");
  const [updateError, setUpdateError] = useState("");

  useEffect(() => {
    async function loadWeightClasses() {
      try {
        const response = await fetch(`${API_BASE_URL}/weight-classes`);

        if (!response.ok) {
          throw new Error("Failed to load weight classes.");
        }

        const data = await response.json();
        setWeightClasses(data.weight_classes ?? []);
      } catch (requestError) {
        console.error(requestError);
        setWeightClasses([
          "Flyweight",
          "Bantamweight",
          "Featherweight",
          "Lightweight",
          "Welterweight",
          "Middleweight",
          "Light Heavyweight",
          "Heavyweight",
        ]);
      }
    }

    loadWeightClasses();
    loadFutureCards();
    loadRecentCards();
    loadUpdateStatus();
    loadLatestReport();
  }, []);

  useEffect(() => {
    if (activeView !== "update") {
      return;
    }

    const intervalId = window.setInterval(() => {
      loadUpdateStatus();
    }, 3000);

    return () => window.clearInterval(intervalId);
  }, [activeView]);

  useEffect(() => {
    if (!updateStatus?.running) {
      return;
    }

    const intervalId = window.setInterval(() => {
      loadUpdateStatus();
    }, 3000);

    return () => window.clearInterval(intervalId);
  }, [updateStatus?.running]);

  useEffect(() => {
    if (activeView === "cards" && selectedCardId) {
      loadCardPredictions(selectedCardId);
    }
  }, [activeView, selectedCardId]);

  useEffect(() => {
    if (activeView === "recent" && selectedRecentCardId) {
      loadRecentCardDetail(selectedRecentCardId);
    }
  }, [activeView, selectedRecentCardId]);

  async function searchFighters(query, setResults) {
    if (!query.trim()) {
      setResults([]);
      return;
    }

    try {
      const params = new URLSearchParams({
        query,
        limit: "8",
      });

      const response = await fetch(`${API_BASE_URL}/fighters/search?${params}`);

      if (!response.ok) {
        throw new Error("Fighter search failed.");
      }

      const data = await response.json();
      setResults(data.fighters ?? []);
    } catch (requestError) {
      console.error(requestError);
      setResults([]);
    }
  }

  async function handlePredict(event) {
    event.preventDefault();

    setLoading(true);
    setError("");
    setSinglePrediction(null);

    try {
      const response = await fetch(`${API_BASE_URL}/predict`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          fighter_a: fighterA,
          fighter_b: fighterB,
          weight_class: weightClass,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        if (data.detail?.suggestions?.length) {
          throw new Error(
            `${data.detail.message}\nSuggestions: ${data.detail.suggestions.join(", ")}`
          );
        }

        throw new Error(data.detail?.message ?? "Prediction failed.");
      }

      setSinglePrediction(data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadFutureCards() {
    setCardsLoading(true);
    setCardsError("");

    try {
      const response = await fetch(`${API_BASE_URL}/future-cards`);

      if (!response.ok) {
        throw new Error("Failed to load future cards.");
      }

      const data = await response.json();
      const cards = data.cards ?? [];

      setFutureCards(cards);

      if (cards.length > 0 && !selectedCardId) {
        setSelectedCardId(cards[0].event_id);
      }
    } catch (requestError) {
      setCardsError(requestError.message);
    } finally {
      setCardsLoading(false);
    }
  }

  async function refreshFutureCards() {
    setCardsLoading(true);
    setCardsError("");

    try {
      const response = await fetch(`${API_BASE_URL}/future-cards/refresh`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error("Failed to refresh future cards.");
      }

      await loadFutureCards();
    } catch (requestError) {
      setCardsError(requestError.message);
    } finally {
      setCardsLoading(false);
    }
  }

  async function loadCardPredictions(eventId) {
    if (!eventId) {
      return;
    }

    setCardPredictionsLoading(true);
    setCardsError("");
    setSelectedCard(null);
    setSelectedFightPrediction(null);

    try {
      const response = await fetch(`${API_BASE_URL}/future-cards/${eventId}/predictions`);

      if (!response.ok) {
        throw new Error("Failed to load card predictions.");
      }

      const data = await response.json();

      setSelectedCard(data);

      const firstAvailablePrediction = data.fights?.find(
        (fight) => fight.prediction_available && fight.prediction
      );

      if (firstAvailablePrediction) {
        setSelectedFightPrediction(firstAvailablePrediction.prediction);
      }
    } catch (requestError) {
      setCardsError(requestError.message);
    } finally {
      setCardPredictionsLoading(false);
    }
  }

  async function loadRecentCards() {
    setRecentLoading(true);
    setRecentError("");

    try {
      const response = await fetch(`${API_BASE_URL}/recent-cards?include_waiting=true`);

      if (!response.ok) {
        throw new Error("Failed to load recent cards.");
      }

      const data = await response.json();
      const cards = data.cards ?? [];

      setRecentCards(cards);

      if (cards.length > 0 && !selectedRecentCardId) {
        setSelectedRecentCardId(cards[0].event_id);
      }
    } catch (requestError) {
      setRecentError(requestError.message);
    } finally {
      setRecentLoading(false);
    }
  }

  async function loadRecentCardDetail(eventId) {
    if (!eventId) {
      return;
    }

    setRecentLoading(true);
    setRecentError("");
    setSelectedRecentCard(null);
    setSelectedRecentFight(null);

    try {
      const response = await fetch(`${API_BASE_URL}/recent-cards/${eventId}`);

      if (!response.ok) {
        throw new Error("Failed to load recent card details.");
      }

      const data = await response.json();

      setSelectedRecentCard(data);

      if (data.fights?.length > 0) {
        setSelectedRecentFight(data.fights[0]);
      }
    } catch (requestError) {
      setRecentError(requestError.message);
    } finally {
      setRecentLoading(false);
    }
  }

  async function loadUpdateStatus() {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/update/status`);

      if (!response.ok) {
        throw new Error("Failed to load update status.");
      }

      const data = await response.json();
      setUpdateStatus(data);

      if (!data.running) {
        loadLatestReport();
      }
    } catch (requestError) {
      setUpdateError(requestError.message);
    }
  }

  async function loadLatestReport() {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/update/latest-report`);

      if (!response.ok) {
        throw new Error("Failed to load latest update report.");
      }

      const data = await response.json();
      setLatestReport(data);
    } catch (requestError) {
      setUpdateError(requestError.message);
    }
  }

  async function startIncrementalUpdate() {
    const confirmed = window.confirm(
      "This will run an incremental data/model update.\n\n" +
        "It refreshes completed events, scrapes only missing fight details, rebuilds features, retrains the model, refreshes future cards, and saves future-card predictions.\n\n" +
        "Most updates should be much faster than a full rebuild, but it can still take several minutes if new fights are available.\n\n" +
        "Keep the backend running while this completes.\n\n" +
        "Continue?"
    );

    if (!confirmed) {
      return;
    }

    setUpdateLoading(true);
    setUpdateError("");

    try {
      const response = await fetch(`${API_BASE_URL}/admin/update/start`, {
        method: "POST",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail?.message ?? "Failed to start update.");
      }

      setUpdateStatus(data.status);
    } catch (requestError) {
      setUpdateError(requestError.message);
    } finally {
      setUpdateLoading(false);
    }
  }

  const latestReportSummary = latestReport?.report?.summary;
  const latestReportStartedAt = latestReport?.report?.started_at;
  const latestReportFinishedAt = latestReport?.report?.finished_at;
  const latestReportDuration = latestReport?.report?.duration_seconds;

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">UFC fight predictor</p>
          <h1>Predict fight win probabilities</h1>
          <p className="hero-copy">
            Uses scraped UFCStats data, Elo-style features, physical profile data,
            historical fight stats, and a calibrated model.
          </p>
        </div>

        <div className="status-card">
          <span className="status-dot" />
          Backend connected to local API
        </div>
      </section>

      <nav className="view-tabs">
        <button
          type="button"
          className={activeView === "single" ? "active" : ""}
          onClick={() => setActiveView("single")}
        >
          Single fight
        </button>

        <button
          type="button"
          className={activeView === "cards" ? "active" : ""}
          onClick={() => setActiveView("cards")}
        >
          Future cards
        </button>

        <button
          type="button"
          className={activeView === "recent" ? "active" : ""}
          onClick={() => setActiveView("recent")}
        >
          Recent cards
        </button>

        <button
          type="button"
          className={activeView === "update" ? "active" : ""}
          onClick={() => setActiveView("update")}
        >
          Update data
        </button>
      </nav>

      {activeView === "single" && (
        <section className="layout">
          <form className="predict-card" onSubmit={handlePredict}>
            <h2>Single fight prediction</h2>

            <label>
              Fighter A
              <input
                value={fighterA}
                onChange={(event) => {
                  setFighterA(event.target.value);
                  searchFighters(event.target.value, setFighterASearchResults);
                }}
                placeholder="Example: Khamzat Chimaev"
              />
            </label>

            {fighterASearchResults.length > 0 && (
              <div className="suggestions">
                {fighterASearchResults.map((name) => (
                  <button
                    type="button"
                    key={name}
                    onClick={() => {
                      setFighterA(name);
                      setFighterASearchResults([]);
                    }}
                  >
                    {name}
                  </button>
                ))}
              </div>
            )}

            <label>
              Fighter B
              <input
                value={fighterB}
                onChange={(event) => {
                  setFighterB(event.target.value);
                  searchFighters(event.target.value, setFighterBSearchResults);
                }}
                placeholder="Example: Sean Strickland"
              />
            </label>

            {fighterBSearchResults.length > 0 && (
              <div className="suggestions">
                {fighterBSearchResults.map((name) => (
                  <button
                    type="button"
                    key={name}
                    onClick={() => {
                      setFighterB(name);
                      setFighterBSearchResults([]);
                    }}
                  >
                    {name}
                  </button>
                ))}
              </div>
            )}

            <label>
              Weight class
              <select
                value={weightClass}
                onChange={(event) => setWeightClass(event.target.value)}
              >
                {weightClasses.map((weightClassOption) => (
                  <option key={weightClassOption} value={weightClassOption}>
                    {weightClassOption}
                  </option>
                ))}
              </select>
            </label>

            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? "Predicting..." : "Predict fight"}
            </button>

            {error && <pre className="error-box">{error}</pre>}
          </form>

          <section className="results-panel">
            <PredictionDetails prediction={singlePrediction} />
          </section>
        </section>
      )}

      {activeView === "cards" && (
        <section className="cards-layout">
          <aside className="cards-sidebar">
            <div className="cards-sidebar-header">
              <h2>Future cards</h2>
              <button type="button" onClick={refreshFutureCards} disabled={cardsLoading}>
                {cardsLoading ? "Refreshing..." : "Refresh"}
              </button>
            </div>

            {cardsError && <pre className="error-box">{cardsError}</pre>}

            <div className="card-list">
              {futureCards.map((card) => (
                <button
                  type="button"
                  key={card.event_id}
                  className={selectedCardId === card.event_id ? "event-card active" : "event-card"}
                  onClick={() => {
                    setSelectedCardId(card.event_id);
                    setSelectedFightPrediction(null);
                  }}
                >
                  <strong>{card.event_name}</strong>
                  <span>{card.event_date}</span>
                  <span>{card.event_location}</span>
                  <em>{card.fight_count} known fights</em>
                </button>
              ))}
            </div>
          </aside>

          <section className="card-fights-panel">
            {!selectedCard && (
              <div className="empty-state">
                <h2>{cardPredictionsLoading ? "Loading card..." : "Select a card"}</h2>
                <p>Pick an upcoming card to see scheduled fight predictions.</p>
              </div>
            )}

            {selectedCard && (
              <>
                <div className="selected-card-header">
                  <div>
                    <p className="eyebrow">Selected card</p>
                    <h2>{selectedCard.event_name}</h2>
                    <p>
                      {selectedCard.event_date} • {selectedCard.event_location}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => loadCardPredictions(selectedCard.event_id)}
                    disabled={cardPredictionsLoading}
                  >
                    {cardPredictionsLoading ? "Loading..." : "Reload predictions"}
                  </button>
                </div>

                <div className="fight-list">
                  {selectedCard.fights.map((fight) => (
                    <button
                      type="button"
                      key={fight.fight_id}
                      className={
                        selectedFightPrediction &&
                        fight.prediction?.fighter_a === selectedFightPrediction.fighter_a &&
                        fight.prediction?.fighter_b === selectedFightPrediction.fighter_b
                          ? "fight-row active"
                          : "fight-row"
                      }
                      onClick={() => {
                        if (fight.prediction_available) {
                          setSelectedFightPrediction(fight.prediction);
                        }
                      }}
                    >
                      <div>
                        <strong>
                          {fight.fighter_1} vs {fight.fighter_2}
                        </strong>
                        <span>{fight.weight_class}</span>
                      </div>

                      {fight.prediction_available ? (
                        <div className="fight-pick">
                          <strong>{fight.prediction.predicted_winner}</strong>
                          <span>{fight.prediction.confidence_percentage}</span>
                        </div>
                      ) : (
                        <div className="fight-unavailable">
                          <strong>No prediction</strong>
                          <span>{fight.error?.message ?? "Missing fighter data"}</span>
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </>
            )}
          </section>

          <section className="results-panel">
            <PredictionDetails prediction={selectedFightPrediction} />
          </section>
        </section>
      )}

      {activeView === "recent" && (
        <section className="cards-layout">
          <aside className="cards-sidebar">
            <div className="cards-sidebar-header">
              <h2>Recent cards</h2>

              <div className="sidebar-button-group">
                <button type="button" onClick={loadRecentCards} disabled={recentLoading}>
                  {recentLoading ? "Loading..." : "Reload"}
                </button>
              </div>
            </div>

            {recentError && <pre className="error-box">{recentError}</pre>}

            <div className="card-list">
              {recentCards.length === 0 && (
                <div className="mini-empty-state">
                  <strong>No saved cards yet</strong>
                  <span>
                    Save future-card predictions first, then this tab can compare them
                    against actual results later.
                  </span>
                </div>
              )}

              {recentCards.map((card) => (
                <button
                  type="button"
                  key={card.event_id}
                  className={
                    selectedRecentCardId === card.event_id
                      ? "event-card active"
                      : "event-card"
                  }
                  onClick={() => {
                    setSelectedRecentCardId(card.event_id);
                    setSelectedRecentFight(null);
                  }}
                >
                  <strong>{card.event_name}</strong>
                  <span>{card.event_date}</span>
                  <span>{card.event_location}</span>
                  <em>
                    {card.status === "completed"
                      ? `${card.accuracy_percentage || "N/A"} accuracy`
                      : card.status === "partially_completed"
                        ? "Partially completed"
                        : "Waiting for results"}
                  </em>
                </button>
              ))}
            </div>
          </aside>

          <section className="card-fights-panel">
            {!selectedRecentCard && (
              <div className="empty-state">
                <h2>{recentLoading ? "Loading card..." : "Select a recent card"}</h2>
                <p>
                  Pick a saved card to compare pre-fight predictions against actual
                  results.
                </p>
              </div>
            )}

            {selectedRecentCard && (
              <>
                <div className="selected-card-header">
                  <div>
                    <p className="eyebrow">Saved card</p>
                    <h2>{selectedRecentCard.event_name}</h2>
                    <p>
                      {selectedRecentCard.event_date} • {selectedRecentCard.event_location}
                    </p>
                  </div>

                  <div className="recent-card-summary">
                    <strong>
                      {selectedRecentCard.status === "completed"
                        ? selectedRecentCard.accuracy_percentage || "N/A"
                        : selectedRecentCard.status === "partially_completed"
                          ? "Partial"
                          : "Waiting"}
                    </strong>
                    <span>
                      {selectedRecentCard.correct_prediction_count} correct of{" "}
                      {selectedRecentCard.predicted_completed_count} scored predictions
                    </span>
                  </div>
                </div>

                <div className="fight-list">
                  {selectedRecentCard.fights.map((fight) => (
                    <button
                      type="button"
                      key={fight.fight_id}
                      className={
                        selectedRecentFight?.fight_id === fight.fight_id
                          ? "fight-row active"
                          : "fight-row"
                      }
                      onClick={() => setSelectedRecentFight(fight)}
                    >
                      <div>
                        <strong>
                          {fight.fighter_1} vs {fight.fighter_2}
                        </strong>
                        <span>{fight.weight_class}</span>
                      </div>

                      {fight.actual_result_available ? (
                        <div
                          className={
                            fight.prediction_correct
                              ? "fight-result-pill correct"
                              : "fight-result-pill incorrect"
                          }
                        >
                          <strong>{fight.prediction_correct ? "Correct" : "Wrong"}</strong>
                          <span>Actual: {fight.actual_winner}</span>
                        </div>
                      ) : (
                        <div className="fight-result-pill waiting">
                          <strong>Waiting</strong>
                          <span>Predicted: {fight.predicted_winner || "N/A"}</span>
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </>
            )}
          </section>

          <section className="results-panel">
            <RecentFightDetails fight={selectedRecentFight} />
          </section>
        </section>
      )}

      {activeView === "update" && (
        <section className="update-layout">
          <section className="update-card warning-card">
            <p className="eyebrow">Incremental update</p>
            <h2>Update data and retrain model</h2>
            <p>
              This updates completed events, scrapes only missing fight details,
              rebuilds features, retrains the calibrated model, rebuilds current fighter
              features, refreshes future cards, and saves future-card predictions.
            </p>
            <p>
              Most updates should be much faster than a full rebuild, but it can still
              take several minutes if new fights are available.
            </p>

            <button
              className="primary-button"
              type="button"
              onClick={startIncrementalUpdate}
              disabled={updateLoading || updateStatus?.running}
            >
              {updateStatus?.running ? "Update running..." : "Start incremental update"}
            </button>

            {updateError && <pre className="error-box">{updateError}</pre>}
          </section>

          <section className="update-card">
            <h2>Update progress</h2>

            <div className="progress-header">
              <strong>{updateStatus?.progress_percent ?? 0}%</strong>
              <span>
                Stage {updateStatus?.current_stage_index ?? 0} of{" "}
                {updateStatus?.total_stages ?? 12}
              </span>
            </div>

            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{
                  width: `${updateStatus?.progress_percent ?? 0}%`,
                }}
              />
            </div>

            <div className="update-status-grid">
              <div>
                <span>Status</span>
                <strong>{updateStatus?.running ? "Running" : "Idle"}</strong>
              </div>

              <div>
                <span>Current stage</span>
                <strong>{updateStatus?.current_stage ?? "None"}</strong>
              </div>

              <div>
                <span>Message</span>
                <strong>{updateStatus?.message ?? "No status yet."}</strong>
              </div>

              <div>
                <span>Last result</span>
                <strong>
                  {updateStatus?.success === true
                    ? "Success"
                    : updateStatus?.success === false
                      ? "Failed"
                      : "Not finished"}
                </strong>
              </div>
            </div>
          </section>

          <section className="update-card report-card">
            <div className="report-header">
              <h2>Latest report</h2>
              <button type="button" onClick={loadLatestReport}>
                Reload report
              </button>
            </div>

            {!latestReport?.available && (
              <p>{latestReport?.message ?? "No report loaded yet."}</p>
            )}

            {latestReport?.available && latestReportSummary && (
              <>
                <div className="report-meta">
                  <span>Started: {latestReportStartedAt}</span>
                  <span>Finished: {latestReportFinishedAt}</span>
                  <span>Duration: {latestReportDuration}s</span>
                </div>

                <div className="report-grid">
                  <div>
                    <span>Completed events</span>
                    <strong>{latestReportSummary.completed_events_rows}</strong>
                  </div>
                  <div>
                    <span>Event fights</span>
                    <strong>{latestReportSummary.event_fights_rows}</strong>
                  </div>
                  <div>
                    <span>Fight stat rows</span>
                    <strong>{latestReportSummary.fight_stats_rows}</strong>
                  </div>
                  <div>
                    <span>Fighter profiles</span>
                    <strong>{latestReportSummary.fighter_profiles_rows}</strong>
                  </div>
                  <div>
                    <span>Training rows</span>
                    <strong>{latestReportSummary.training_matchups_rows}</strong>
                  </div>
                  <div>
                    <span>Current fighters</span>
                    <strong>{latestReportSummary.current_fighter_features_rows}</strong>
                  </div>
                  <div>
                    <span>Upcoming events</span>
                    <strong>{latestReportSummary.upcoming_events_rows}</strong>
                  </div>
                  <div>
                    <span>Upcoming fights</span>
                    <strong>{latestReportSummary.upcoming_fights_rows}</strong>
                  </div>
                  <div>
                    <span>Saved predictions</span>
                    <strong>{latestReportSummary.saved_card_predictions_rows ?? "N/A"}</strong>
                  </div>
                </div>

                {latestReportSummary.failed_stages?.length > 0 ? (
                  <pre className="error-box">
                    Failed stages: {latestReportSummary.failed_stages.join(", ")}
                  </pre>
                ) : (
                  <div className="success-box">Latest update completed successfully.</div>
                )}
              </>
            )}
          </section>
        </section>
      )}
    </main>
  );
}

export default App;