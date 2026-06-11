export function normalizeFighterName(value) {
  return String(value || "")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase();
}

export function getFighterInitials(name) {
  const parts = String(name || "")
    .replaceAll("-", " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (parts.length === 0) {
    return "?";
  }

  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }

  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export function formatNumber(value) {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  const numberValue = Number(value);

  if (!Number.isFinite(numberValue)) {
    return String(value);
  }

  return numberValue.toLocaleString();
}

export function formatPercent(value, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "N/A";
  }

  return `${(Number(value) * 100).toFixed(digits)}%`;
}

export function formatDecimal(value, digits = 4) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "N/A";
  }

  return Number(value).toFixed(digits);
}

export function formatAmericanOdds(value) {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  const numberValue = Number(value);

  if (!Number.isFinite(numberValue)) {
    return String(value);
  }

  return numberValue > 0 ? `+${numberValue}` : `${numberValue}`;
}

export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || !Number.isFinite(Number(seconds))) {
    return "N/A";
  }

  const totalSeconds = Math.round(Number(seconds));
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;

  if (minutes <= 0) {
    return `${remainingSeconds}s`;
  }

  return `${minutes}m ${remainingSeconds}s`;
}

export function clampProbability(probability) {
  if (!Number.isFinite(Number(probability))) {
    return 0;
  }

  return Math.max(0, Math.min(100, Number(probability) * 100));
}

export function parsePercentageText(value) {
  if (!value) {
    return null;
  }

  const parsed = Number(String(value).replace("%", ""));

  if (!Number.isFinite(parsed)) {
    return null;
  }

  return parsed / 100;
}

const MODEL_NAMES = {
  calibrated_logistic_regression: "Calibrated Logistic",
  calibrated_random_forest: "Calibrated Random Forest",
  calibrated_xgboost: "Calibrated XGBoost",
  logistic_regression: "Logistic Regression",
  random_forest: "Random Forest",
  xgboost: "XGBoost",
};

export function formatModelName(modelName = "") {
  return MODEL_NAMES[modelName] ?? String(modelName || "N/A").replaceAll("_", " ");
}

const STAT_LABELS = {
  prior_elo: "Elo",
  prior_peak_elo: "Peak Elo",
  prior_win_rate: "Win rate",
  recent_5_win_rate: "Recent 5 win rate",
  prior_finish_win_rate: "Finish win rate",
  prior_finish_loss_rate: "Finish loss rate",
  prior_fights: "UFC fights",
  prior_wins: "UFC wins",
  prior_losses: "UFC losses",
  avg_sig_str_differential_per_15: "Sig. strike diff / 15",
  avg_sig_str_landed_per_15: "Sig. strikes landed / 15",
  avg_sig_str_absorbed_per_15: "Sig. strikes absorbed / 15",
  avg_sig_str_accuracy: "Sig. strike accuracy",
  avg_sig_str_defense: "Sig. strike defense",
  avg_kd_for: "Knockdowns for",
  avg_kd_against: "Knockdowns against",
  avg_td_landed_per_15: "Takedowns landed / 15",
  avg_td_attempted_per_15: "Takedowns attempted / 15",
  avg_td_accuracy: "Takedown accuracy",
  avg_td_defense: "Takedown defense",
  avg_td_absorbed_per_15: "Takedowns absorbed / 15",
  avg_ctrl_seconds_per_15: "Control seconds / 15",
  avg_ctrl_absorbed_seconds_per_15: "Control absorbed / 15",
  avg_sub_att_per_15: "Sub attempts / 15",
  height_inches: "Height",
  reach_inches: "Reach",
  reach_minus_height_inches: "Reach minus height",
  age_years: "Age",
};

export function formatStatLabel(value = "") {
  return STAT_LABELS[value] ?? String(value).replaceAll("_", " ");
}

export function formatLeaderboardStatValue(key, value) {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  const numberValue = Number(value);

  if (!Number.isFinite(numberValue)) {
    return String(value);
  }

  if (key.includes("rate") || key.includes("accuracy") || key.includes("defense")) {
    return `${(numberValue * 100).toFixed(1)}%`;
  }

  if (key.includes("height") || key.includes("reach")) {
    return `${numberValue.toFixed(1)} in`;
  }

  return numberValue.toFixed(2);
}

export function getConfidenceClass(label = "") {
  const lowerLabel = String(label).toLowerCase();

  if (lowerLabel.includes("high")) {
    return "high";
  }

  if (lowerLabel.includes("strong")) {
    return "strong";
  }

  if (lowerLabel.includes("moderate")) {
    return "moderate";
  }

  if (lowerLabel.includes("slight") || lowerLabel.includes("very close")) {
    return "close";
  }

  return "unknown";
}
