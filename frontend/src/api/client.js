import * as mock from "./mock.js";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export const USE_MOCK =
  import.meta.env.MODE === "mock" || import.meta.env.VITE_USE_MOCK === "1";

const TOKEN_KEY = "fightiq_token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function setToken(token) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    /* ignore storage errors (private mode, etc.) */
  }
}

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
  const token = getToken();
  const headers = {};
  if (body) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: Object.keys(headers).length ? headers : undefined,
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

export async function loginUser(email, password) {
  if (USE_MOCK) {
    setToken("mock-token");
    return {
      token: "mock-token",
      user: {
        id: 0,
        email,
        display_name: email.split("@")[0],
        role: email.startsWith("admin") ? "admin" : "user",
      },
    };
  }

  return request("/auth/login", {
    method: "POST",
    body: { email, password },
    fallbackError: "Login failed.",
  });
}

export async function registerUser(email, password, displayName) {
  if (USE_MOCK) {
    return { user: { id: 0, email, display_name: displayName || email.split("@")[0], role: "user" } };
  }

  return request("/auth/register", {
    method: "POST",
    body: { email, password, display_name: displayName },
    fallbackError: "Registration failed.",
  });
}

export async function getMe() {
  if (USE_MOCK) {
    return { user: { id: 0, email: "demo@fightiq.local", display_name: "demo", role: "user" } };
  }

  return request("/auth/me", { fallbackError: "Session expired." });
}

export async function updateProfile(email, displayName) {
  if (USE_MOCK) {
    return { user: { id: 0, email, display_name: displayName, role: "user" } };
  }

  return request("/auth/profile", {
    method: "POST",
    body: { email, display_name: displayName },
    fallbackError: "Failed to update profile.",
  });
}

export async function changePassword(currentPassword, newPassword) {
  if (USE_MOCK) {
    return { message: "Password updated." };
  }

  return request("/auth/change-password", {
    method: "POST",
    body: { current_password: currentPassword, new_password: newPassword },
    fallbackError: "Failed to change password.",
  });
}

export async function setVisibility(isPublic) {
  if (USE_MOCK) {
    return { is_public: isPublic };
  }

  return request("/auth/visibility", {
    method: "POST",
    body: { is_public: isPublic },
    fallbackError: "Failed to update visibility.",
  });
}

export async function getUsers() {
  if (USE_MOCK) {
    return {
      users: [
        { id: 1, username: "admin", role: "admin", created_at: "2026-06-28" },
        { id: 2, username: "demo", role: "user", created_at: "2026-06-28" },
      ],
    };
  }

  return request("/admin/users", { fallbackError: "Failed to load users." });
}

export async function setUserRole(userId, role) {
  if (USE_MOCK) {
    return { user_id: userId, role };
  }

  return request(`/admin/users/${userId}/role`, {
    method: "POST",
    body: { role },
    fallbackError: "Failed to update role.",
  });
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

// Model-free card detail (just the fights) — the source for the picks tab, so the
// engine's prediction never shows here.
export async function getFutureCardDetail(eventId) {
  if (USE_MOCK) {
    return mock.getFutureCardDetail(eventId);
  }

  return request(`/future-cards/${encodeURIComponent(eventId)}`, {
    fallbackError: "Failed to load card.",
  });
}

// --- account picks (Phase 6) ---

export async function getMyPredictions(eventId) {
  if (USE_MOCK) {
    return mock.listPredictions(eventId);
  }

  const query = eventId ? `?event_id=${encodeURIComponent(eventId)}` : "";
  const data = await request(`/predictions${query}`, {
    fallbackError: "Failed to load your picks.",
  });
  return data.predictions ?? [];
}

export async function savePrediction(fightUrl, pickedFighter, pickedMethod = null) {
  if (USE_MOCK) {
    return mock.savePrediction(fightUrl, pickedFighter, pickedMethod);
  }

  const data = await request("/predictions", {
    method: "POST",
    body: {
      fight_url: fightUrl,
      picked_fighter: pickedFighter,
      picked_method: pickedMethod,
    },
    fallbackError: "Failed to save your pick.",
  });
  return data.prediction;
}

export async function deletePrediction(fightUrl) {
  if (USE_MOCK) {
    return mock.deletePrediction(fightUrl);
  }

  return request(`/predictions?fight_url=${encodeURIComponent(fightUrl)}`, {
    method: "DELETE",
    fallbackError: "Failed to remove your pick.",
  });
}

export async function getMyStats() {
  if (USE_MOCK) {
    return mock.getMyStats();
  }

  const data = await request("/predictions/stats", {
    fallbackError: "Failed to load your stats.",
  });
  return data.stats;
}

export async function updateFutureFightScheduledRounds(eventId, fightId, scheduledRounds) {
  if (USE_MOCK) {
    return mock.updateFutureFightScheduledRounds(eventId, fightId, scheduledRounds);
  }

  return request(
    `/future-cards/${encodeURIComponent(eventId)}/fights/${encodeURIComponent(
      fightId
    )}/scheduled-rounds`,
    {
      method: "POST",
      body: { scheduled_rounds: scheduledRounds },
      fallbackError: "Failed to save scheduled-rounds override.",
    }
  );
}

export async function updateFutureEventControl(eventId, payload) {
  if (USE_MOCK) {
    return mock.updateFutureEventControl(eventId, payload);
  }

  return request(`/future-cards/${encodeURIComponent(eventId)}/event-control`, {
    method: "POST",
    body: payload,
    fallbackError: "Failed to save event lock controls.",
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
    const cards = await mock.getRecentCards();
    return { cards, overall: null };
  }

  // Returns { card_count, overall, cards } so the UI can show a cumulative grade.
  return request(`/recent-cards?include_waiting=${includeWaiting}`, {
    fallbackError: "Failed to load recent cards.",
  });
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

// --- friends (Phase 6) ---

export async function getFriends() {
  if (USE_MOCK) {
    return mock.getFriends();
  }
  return request("/friends", { fallbackError: "Failed to load friends." });
}

export async function sendFriendRequest(username) {
  if (USE_MOCK) {
    return mock.sendFriendRequest(username);
  }
  return request("/friends/requests", {
    method: "POST",
    body: { username },
    fallbackError: "Failed to send friend request.",
  });
}

export async function respondFriendRequest(friendshipId, accept) {
  if (USE_MOCK) {
    return mock.respondFriendRequest(friendshipId, accept);
  }
  return request(`/friends/requests/${friendshipId}/respond`, {
    method: "POST",
    body: { accept },
    fallbackError: "Failed to respond to request.",
  });
}

export async function removeFriend(userId) {
  if (USE_MOCK) {
    return mock.removeFriend(userId);
  }
  return request(`/friends/${userId}`, {
    method: "DELETE",
    fallbackError: "Failed to remove friend.",
  });
}

export async function getFriendCompare(userId) {
  if (USE_MOCK) {
    return mock.getFriendCompare(userId);
  }
  return request(`/friends/${userId}/compare`, {
    fallbackError: "Failed to load the comparison.",
  });
}

export async function getUserLeaderboard({ scope = "overall", window = "all_time" } = {}) {
  if (USE_MOCK) {
    return mock.getUserLeaderboard({ scope, window });
  }

  const params = new URLSearchParams({ scope, window });
  const data = await request(`/leaderboard/users?${params}`, {
    fallbackError: "Failed to load the user leaderboard.",
  });
  return data.leaderboard ?? [];
}

export async function getUserCardLeaderboard(eventId, { scope = "friends" } = {}) {
  if (USE_MOCK) {
    return mock.getUserCardLeaderboard(eventId, { scope });
  }

  const params = new URLSearchParams({ scope });
  const data = await request(
    `/leaderboard/users/cards/${encodeURIComponent(eventId)}?${params}`,
    {
      fallbackError: "Failed to load the card leaderboard.",
    }
  );
  return data.leaderboard ?? [];
}

export async function getModelEvaluation({ recentLimit = 25 } = {}) {
  if (USE_MOCK) {
    return mock.getModelEvaluation();
  }

  // The holdout is fixed to the model's true chronological test set on the
  // backend, so there is no test-window parameter to pass anymore.
  const params = new URLSearchParams({
    recent_prediction_limit: String(recentLimit),
  });

  return request(`/model-evaluation?${params}`, {
    fallbackError: "Failed to load model evaluation.",
  });
}

export async function getWalkForwardEvaluation({ nFolds = 8 } = {}) {
  if (USE_MOCK) {
    return mock.getWalkForwardEvaluation();
  }

  const params = new URLSearchParams({ n_folds: String(nFolds) });

  return request(`/walk-forward-evaluation?${params}`, {
    fallbackError: "Failed to load walk-forward evaluation.",
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

export async function getClvEvaluation() {
  if (USE_MOCK) {
    return {
      available: false,
      message: "CLV accrues once odds are captured more than once per fight.",
      fights: [],
    };
  }

  return request("/clv-evaluation", {
    fallbackError: "Failed to load CLV evaluation.",
  });
}

export async function getDataQualitySummary() {
  if (USE_MOCK) {
    return mock.getDataQualitySummary();
  }

  return request("/data-quality", {
    fallbackError: "Failed to load data quality summary.",
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
