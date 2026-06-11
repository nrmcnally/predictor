import * as mock from "./mock.js";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export const USE_MOCK =
  import.meta.env.MODE === "mock" || import.meta.env.VITE_USE_MOCK === "1";

function extractErrorMessage(data, fallback) {
  const detail = data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (detail?.suggestions?.length) {
    return `${detail.message}\nSuggestions: ${detail.suggestions.join(", ")}`;
  }

  return detail?.message || detail?.error || data?.message || fallback;
}

async function request(path, { method = "GET", body, fallbackError } = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

  let data;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    throw new Error(extractErrorMessage(data, fallbackError || "Request failed."));
  }

  return data;
}

export async function checkHealth() {
  if (USE_MOCK) {
    return { status: "ok" };
  }

  return request("/health", { fallbackError: "API is unreachable." });
}

export async function searchFighters(query, limit = 8) {
  if (USE_MOCK) {
    return mock.searchFighters(query, limit);
  }

  const params = new URLSearchParams({ query, limit: String(limit) });
  const data = await request(`/fighters/search?${params}`, {
    fallbackError: "Fighter search failed.",
  });

  return data.fighters ?? [];
}

export async function getWeightClasses() {
  if (USE_MOCK) {
    return mock.getWeightClasses();
  }

  const data = await request("/weight-classes", {
    fallbackError: "Failed to load weight classes.",
  });

  return data.weight_classes ?? [];
}

export async function predictFight(fighterA, fighterB, weightClass) {
  if (USE_MOCK) {
    return mock.predictFight(fighterA, fighterB, weightClass);
  }

  return request("/predict", {
    method: "POST",
    body: { fighter_a: fighterA, fighter_b: fighterB, weight_class: weightClass },
    fallbackError: "Prediction failed.",
  });
}

export async function predictMethod(fighterA, fighterB, weightClass) {
  if (USE_MOCK) {
    return mock.predictMethod(fighterA, fighterB, weightClass);
  }

  return request("/predict-method", {
    method: "POST",
    body: { fighter_a: fighterA, fighter_b: fighterB, weight_class: weightClass },
    fallbackError: "Failed to predict method of ending.",
  });
}

export async function getFighterProfile(fighter) {
  if (USE_MOCK) {
    return mock.getFighterProfile(fighter);
  }

  const params = new URLSearchParams({ fighter });

  return request(`/fighter-profile?${params}`, {
    fallbackError: "Failed to load fighter profile.",
  });
}

export async function getFighterImages() {
  if (USE_MOCK) {
    return mock.getFighterImages();
  }

  const data = await request("/fighter-images", {
    fallbackError: "Failed to load fighter images.",
  });

  return data.images ?? [];
}

export async function getFutureCards() {
  if (USE_MOCK) {
    return mock.getFutureCards();
  }

  const data = await request("/future-cards", {
    fallbackError: "Failed to load future cards.",
  });

  return data.cards ?? [];
}

export async function getFutureCardPredictions(eventId) {
  if (USE_MOCK) {
    return mock.getFutureCardPredictions(eventId);
  }

  return request(`/future-cards/${eventId}/predictions`, {
    fallbackError: "Failed to load card predictions.",
  });
}

export async function refreshFutureCards() {
  if (USE_MOCK) {
    return { message: "Future cards refreshed." };
  }

  return request("/future-cards/refresh", {
    method: "POST",
    fallbackError: "Failed to refresh future cards.",
  });
}

export async function getFutureFightOdds() {
  if (USE_MOCK) {
    return mock.getFutureFightOdds();
  }

  const data = await request("/future-fight-odds", {
    fallbackError: "Failed to load future fight odds.",
  });

  return data.odds ?? [];
}

export async function getRecentCards(includeWaiting = true) {
  if (USE_MOCK) {
    return mock.getRecentCards();
  }

  const data = await request(`/recent-cards?include_waiting=${includeWaiting}`, {
    fallbackError: "Failed to load recent cards.",
  });

  return data.cards ?? [];
}

export async function getRecentCardDetail(eventId) {
  if (USE_MOCK) {
    return mock.getRecentCardDetail(eventId);
  }

  return request(`/recent-cards/${eventId}`, {
    fallbackError: "Failed to load recent card details.",
  });
}

export async function getLeaderboardOptions() {
  if (USE_MOCK) {
    return mock.getLeaderboardOptions();
  }

  return request("/leaderboards/options", {
    fallbackError: "Failed to load leaderboard options.",
  });
}

export async function getLeaderboards({ top, minFights, maxInactiveDays }) {
  if (USE_MOCK) {
    return mock.getLeaderboards();
  }

  const params = new URLSearchParams({
    top: String(top),
    min_fights: String(minFights),
    max_inactive_days: String(maxInactiveDays),
  });

  return request(`/leaderboards?${params}`, {
    fallbackError: "Failed to load leaderboards.",
  });
}

export async function getModelEvaluation({ testFraction, recentLimit }) {
  if (USE_MOCK) {
    return mock.getModelEvaluation();
  }

  const params = new URLSearchParams({
    test_fraction: String(testFraction),
    recent_prediction_limit: String(recentLimit),
  });

  return request(`/model-evaluation?${params}`, {
    fallbackError: "Failed to load model evaluation.",
  });
}

export async function getMethodModelMetrics() {
  if (USE_MOCK) {
    return mock.getMethodModelMetrics();
  }

  return request("/method-model-metrics", {
    fallbackError: "Failed to load method model metrics.",
  });
}

export async function getModelMarketEvaluation() {
  if (USE_MOCK) {
    return mock.getModelMarketEvaluation();
  }

  return request("/model-vs-market-evaluation", {
    fallbackError: "Failed to load model-vs-market evaluation.",
  });
}

export async function getModelSnapshotEvaluation() {
  if (USE_MOCK) {
    return mock.getModelSnapshotEvaluation();
  }

  return request("/model-snapshot-evaluation", {
    fallbackError: "Failed to load prospective model evaluation.",
  });
}

export async function getUpdateStatus() {
  if (USE_MOCK) {
    return mock.getUpdateStatus();
  }

  return request("/admin/update/status", {
    fallbackError: "Failed to load update status.",
  });
}

export async function getLatestUpdateReport() {
  if (USE_MOCK) {
    return mock.getLatestUpdateReport();
  }

  return request("/admin/update/latest-report", {
    fallbackError: "Failed to load latest update report.",
  });
}

export async function startIncrementalUpdate() {
  if (USE_MOCK) {
    return mock.startIncrementalUpdate();
  }

  return request("/admin/update/start", {
    method: "POST",
    fallbackError: "Failed to start update.",
  });
}
