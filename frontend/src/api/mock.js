// Deterministic sample data so the UI can run without the FastAPI backend
// (the real backend needs scraped CSVs and trained models that are not in git).
// Enabled with `npm run dev:mock` or VITE_USE_MOCK=1.

const FIGHTERS = [
  { name: "Khamzat Chimaev", weightClass: "Middleweight", elo: 1712, peak: 1712, wins: 9, losses: 0, age: 31.8, height: 74, reach: 75, style: "Relentless grappler", tags: ["Wrestling-heavy", "Front-runner", "Submission threat"] },
  { name: "Sean Strickland", weightClass: "Middleweight", elo: 1641, peak: 1668, wins: 13, losses: 6, age: 35.2, height: 73, reach: 76, style: "Volume striker", tags: ["High output", "Iron chin", "Forward pressure"] },
  { name: "Islam Makhachev", weightClass: "Welterweight", elo: 1768, peak: 1768, wins: 15, losses: 1, age: 34.6, height: 70, reach: 70, style: "Dominant grappler", tags: ["Top control", "Submission threat", "Fight IQ"] },
  { name: "Ilia Topuria", weightClass: "Lightweight", elo: 1745, peak: 1745, wins: 9, losses: 0, age: 29.4, height: 67, reach: 69, style: "Knockout artist", tags: ["One-punch power", "Boxing", "Calm pressure"] },
  { name: "Alex Pereira", weightClass: "Light Heavyweight", elo: 1689, peak: 1721, wins: 9, losses: 2, age: 38.9, height: 76, reach: 79, style: "Kickboxing sniper", tags: ["Left hook", "Calf kicks", "Composure"] },
  { name: "Magomed Ankalaev", weightClass: "Light Heavyweight", elo: 1701, peak: 1701, wins: 14, losses: 1, age: 33.9, height: 75, reach: 75, style: "Patient counter striker", tags: ["Southpaw", "Takedown defense", "Low output"] },
  { name: "Merab Dvalishvili", weightClass: "Bantamweight", elo: 1733, peak: 1733, wins: 13, losses: 4, age: 35.4, height: 66, reach: 68, style: "Cardio machine", tags: ["Takedown chains", "Pace", "Durability"] },
  { name: "Sean O'Malley", weightClass: "Bantamweight", elo: 1648, peak: 1690, wins: 11, losses: 3, age: 31.6, height: 71, reach: 72, style: "Rangy sniper", tags: ["Distance control", "Power", "Creative striking"] },
  { name: "Tom Aspinall", weightClass: "Heavyweight", elo: 1722, peak: 1722, wins: 9, losses: 1, age: 33.1, height: 77, reach: 78, style: "Athletic finisher", tags: ["Hand speed", "Grappling", "Fast starts"] },
  { name: "Ciryl Gane", weightClass: "Heavyweight", elo: 1655, peak: 1683, wins: 12, losses: 3, age: 36.1, height: 76, reach: 81, style: "Mobile technician", tags: ["Footwork", "Range", "Kicks"] },
  { name: "Belal Muhammad", weightClass: "Welterweight", elo: 1668, peak: 1694, wins: 18, losses: 4, age: 37.9, height: 70, reach: 72, style: "Grinding pressure", tags: ["Wrestling mix", "Pace", "Durability"] },
  { name: "Shavkat Rakhmonov", weightClass: "Welterweight", elo: 1709, peak: 1709, wins: 10, losses: 0, age: 31.5, height: 73, reach: 77, style: "Finishing hunter", tags: ["100% finish rate", "Grappling", "Composure"] },
  { name: "Jack Della Maddalena", weightClass: "Welterweight", elo: 1671, peak: 1671, wins: 9, losses: 0, age: 29.7, height: 71, reach: 73, style: "Boxing pressure", tags: ["Body work", "Combinations", "Toughness"] },
  { name: "Dricus Du Plessis", weightClass: "Middleweight", elo: 1676, peak: 1702, wins: 9, losses: 1, age: 32.4, height: 73, reach: 76, style: "Chaotic pressure", tags: ["Awkward rhythm", "Cardio", "Finishing instinct"] },
  { name: "Nassourdine Imavov", weightClass: "Middleweight", elo: 1644, peak: 1644, wins: 9, losses: 4, age: 30.2, height: 75, reach: 75, style: "Technical striker", tags: ["Distance", "Counters", "Improving wrestling"] },
  { name: "Arman Tsarukyan", weightClass: "Lightweight", elo: 1698, peak: 1698, wins: 12, losses: 2, age: 29.6, height: 67, reach: 72, style: "Complete mixer", tags: ["Wrestling", "Striking blend", "Strength"] },
  { name: "Charles Oliveira", weightClass: "Lightweight", elo: 1632, peak: 1705, wins: 24, losses: 10, age: 36.5, height: 70, reach: 74, style: "Submission wizard", tags: ["Guard threat", "Finishing", "All-action"] },
  { name: "Max Holloway", weightClass: "Lightweight", elo: 1651, peak: 1699, wins: 22, losses: 8, age: 34.5, height: 71, reach: 69, style: "Volume legend", tags: ["Output", "Chin", "Boxing IQ"] },
  { name: "Alexandre Pantoja", weightClass: "Flyweight", elo: 1697, peak: 1697, wins: 14, losses: 3, age: 36.1, height: 65, reach: 68, style: "Back-take specialist", tags: ["Scrambles", "Pace", "Submissions"] },
  { name: "Joshua Van", weightClass: "Flyweight", elo: 1662, peak: 1662, wins: 8, losses: 1, age: 24.7, height: 66, reach: 67, style: "Young volume threat", tags: ["Output", "Speed", "Improving defense"] },
  { name: "Alexander Volkanovski", weightClass: "Featherweight", elo: 1681, peak: 1742, wins: 14, losses: 4, age: 37.7, height: 66, reach: 71, style: "Adaptive technician", tags: ["Fight IQ", "Footwork", "Toughness"] },
  { name: "Movsar Evloev", weightClass: "Featherweight", elo: 1692, peak: 1692, wins: 9, losses: 0, age: 32.2, height: 67, reach: 72, style: "Undefeated wrestler", tags: ["Control", "Chains", "Low damage taken"] },
  { name: "Kayla Harrison", weightClass: "Women's Bantamweight", elo: 1684, peak: 1684, wins: 3, losses: 0, age: 35.9, height: 68, reach: 69, style: "Judo powerhouse", tags: ["Trips", "Top pressure", "Finishing"] },
  { name: "Valentina Shevchenko", weightClass: "Women's Flyweight", elo: 1665, peak: 1718, wins: 14, losses: 4, age: 38.3, height: 65, reach: 67, style: "Precision counter", tags: ["Timing", "Defense", "Experience"] },
];

const WEIGHT_CLASSES = [
  "Flyweight",
  "Bantamweight",
  "Featherweight",
  "Lightweight",
  "Welterweight",
  "Middleweight",
  "Light Heavyweight",
  "Heavyweight",
  "Women's Flyweight",
  "Women's Bantamweight",
];

function hashString(value) {
  let hash = 2166136261;

  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }

  return (hash >>> 0) / 4294967295;
}

function findFighter(name) {
  const normalized = String(name || "").trim().toLowerCase();

  return FIGHTERS.find((fighter) => fighter.name.toLowerCase() === normalized) || null;
}

function percent(probability) {
  return `${(probability * 100).toFixed(1)}%`;
}

function confidenceLabel(confidence) {
  if (confidence >= 0.7) return "High confidence";
  if (confidence >= 0.65) return "Strong lean";
  if (confidence >= 0.6) return "Moderate lean";
  if (confidence >= 0.55) return "Slight lean";
  return "Very close / low confidence";
}

function delay(result, ms = 220) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(result), ms);
  });
}

export function searchFighters(query, limit = 8) {
  const normalized = String(query || "").trim().toLowerCase();

  if (!normalized) {
    return delay([], 80);
  }

  const matches = FIGHTERS.filter((fighter) =>
    fighter.name.toLowerCase().includes(normalized)
  )
    .map((fighter) => fighter.name)
    .slice(0, limit);

  return delay(matches, 120);
}

export function getWeightClasses() {
  return delay([...WEIGHT_CLASSES]);
}

function buildProbability(fighterA, fighterB) {
  const a = findFighter(fighterA);
  const b = findFighter(fighterB);
  const eloA = a?.elo ?? 1600;
  const eloB = b?.elo ?? 1600;
  const eloProbability = 1 / (1 + 10 ** ((eloB - eloA) / 400));
  const jitter = (hashString(`${fighterA}|${fighterB}`) - 0.5) * 0.08;

  return Math.min(0.92, Math.max(0.08, eloProbability * 0.8 + 0.5 * 0.2 + jitter));
}

export function predictFight(fighterA, fighterB, weightClass) {
  const a = findFighter(fighterA);
  const b = findFighter(fighterB);

  if (!a || !b) {
    const missing = !a ? fighterA : fighterB;
    const suggestions = FIGHTERS.map((fighter) => fighter.name)
      .filter((name) => name.toLowerCase().includes(String(missing).slice(0, 3).toLowerCase()))
      .slice(0, 3);

    return Promise.reject(
      new Error(
        `Could not find fighter: ${missing}${
          suggestions.length ? `\nSuggestions: ${suggestions.join(", ")}` : ""
        }`
      )
    );
  }

  const probabilityA = buildProbability(a.name, b.name);
  const predictedWinner = probabilityA >= 0.5 ? a.name : b.name;
  const confidence = Math.max(probabilityA, 1 - probabilityA);

  const edges = [
    { label: "Elo edge", difference: a.elo - b.elo, unit: "pts" },
    { label: "Experience edge", difference: a.wins + a.losses - (b.wins + b.losses), unit: "fights" },
    { label: "Win rate edge", difference: a.wins / (a.wins + a.losses || 1) - b.wins / (b.wins + b.losses || 1), unit: "" },
    { label: "Reach edge", difference: a.reach - b.reach, unit: "in" },
    { label: "Height edge", difference: a.height - b.height, unit: "in" },
    { label: "Age edge", difference: b.age - a.age, unit: "yrs younger" },
  ];

  function insightItems(fighter, opponent) {
    const strengths = [];
    const concerns = [];

    if (fighter.elo > opponent.elo + 25) {
      strengths.push({
        edge_label: "Elo edge",
        title: "Meaningful Elo advantage",
        description: `${fighter.name} holds a ${Math.round(fighter.elo - opponent.elo)}-point Elo edge, suggesting stronger recent results against comparable competition.`,
        severity: "strong",
      });
    }

    if (fighter.reach > opponent.reach + 1) {
      strengths.push({
        edge_label: "Reach edge",
        title: "Reach advantage",
        description: `${fighter.name} has a ${(fighter.reach - opponent.reach).toFixed(0)}-inch reach advantage to work behind at distance.`,
        severity: "moderate",
      });
    }

    if (fighter.age < opponent.age - 2.5) {
      strengths.push({
        edge_label: "Age edge",
        title: "Career-stage advantage",
        description: `${fighter.name} is ${(opponent.age - fighter.age).toFixed(1)} years younger and likely closer to physical prime.`,
        severity: "moderate",
      });
    }

    if (fighter.age > opponent.age + 2.5) {
      concerns.push({
        edge_label: "Age edge",
        title: "Older fighter risk",
        description: `${fighter.name} gives up ${(fighter.age - opponent.age).toFixed(1)} years of age, a historical negative signal at this level.`,
        severity: "moderate",
      });
    }

    if (fighter.losses > opponent.losses + 3) {
      concerns.push({
        edge_label: "Win rate edge",
        title: "More recorded losses",
        description: `${fighter.name} has absorbed more UFC losses, which correlates with declining form in the training data.`,
        severity: "minor",
      });
    }

    if (strengths.length === 0) {
      strengths.push({
        edge_label: "Style",
        title: "Stylistic threat",
        description: `${fighter.name}'s ${fighter.style.toLowerCase()} approach creates problems if the fight reaches their preferred phase.`,
        severity: "minor",
      });
    }

    return { strengths, concerns };
  }

  const insightsA = insightItems(a, b);
  const insightsB = insightItems(b, a);

  return delay({
    model_name: "calibrated_xgboost",
    fighter_a: a.name,
    fighter_b: b.name,
    weight_class: weightClass,
    fighter_a_probability: probabilityA,
    fighter_b_probability: 1 - probabilityA,
    fighter_a_percentage: percent(probabilityA),
    fighter_b_percentage: percent(1 - probabilityA),
    predicted_winner: predictedWinner,
    confidence,
    confidence_percentage: percent(confidence),
    confidence_label: confidenceLabel(confidence),
    basic_matchup_edges: edges,
    matchup_insights: {
      summary: [
        {
          type: "positive",
          text: `${predictedWinner} is favored at ${percent(confidence)} based on Elo, physical profile, and recent-form features.`,
        },
        {
          type: confidence >= 0.62 ? "positive" : "warning",
          text:
            confidence >= 0.62
              ? "The model sees several aligned edges rather than one dominant factor."
              : "This projects as a competitive fight — treat the pick as a lean, not a lock.",
        },
      ],
      fighter_a: insightsA,
      fighter_b: insightsB,
    },
  }, 450);
}

export function predictMethod(fighterA, fighterB) {
  const seed = hashString(`${fighterA}~${fighterB}`);
  const decision = 0.38 + seed * 0.2;
  const ko = (1 - decision) * (0.45 + seed * 0.25);
  const sub = (1 - decision - ko) * 0.8;
  const other = Math.max(0.02, 1 - decision - ko - sub);

  const broad = [
    { label: "Decision", probability: decision },
    { label: "KO/TKO", probability: ko },
    { label: "Submission", probability: sub },
    { label: "Other", probability: other },
  ]
    .sort((rowA, rowB) => rowB.probability - rowA.probability)
    .map((row) => ({ ...row, percentage: percent(row.probability) }));

  const detailed = [
    { label: "Unanimous decision", probability: decision * 0.72 },
    { label: "Split / majority decision", probability: decision * 0.28 },
    { label: "KO/TKO — punches", probability: ko * 0.78 },
    { label: "KO/TKO — kicks & knees", probability: ko * 0.22 },
    { label: "Submission — choke", probability: sub * 0.74 },
    { label: "Submission — joint lock", probability: sub * 0.26 },
    { label: "Other / DQ / doctor stoppage", probability: other },
  ]
    .sort((rowA, rowB) => rowB.probability - rowA.probability)
    .map((row) => ({ ...row, percentage: percent(row.probability) }));

  return delay({
    predicted_broad_method: broad[0].label,
    predicted_broad_method_percentage: broad[0].percentage,
    predicted_detailed_method: detailed[0].label,
    predicted_detailed_method_percentage: detailed[0].percentage,
    broad_method_probabilities: broad,
    detailed_method_probabilities: detailed,
    model_note:
      "Method prediction is directional context from a separate, less accurate model. It is not a guaranteed finish call.",
  }, 380);
}

const OPPONENT_POOL = [
  "Paulo Costa", "Robert Whittaker", "Jared Cannonier", "Marvin Vettori",
  "Roman Dolidze", "Brendan Allen", "Anthony Hernandez", "Caio Borralho",
];

export function getFighterProfile(name) {
  const fighter = findFighter(name);

  if (!fighter) {
    return Promise.reject(new Error(`Could not find fighter: ${name}`));
  }

  const seed = hashString(fighter.name);
  const totalFights = fighter.wins + fighter.losses;
  const winRate = totalFights ? fighter.wins / totalFights : null;

  const eloHistory = [];
  let runningElo = fighter.elo - 140 - Math.round(seed * 60);

  for (let index = 0; index < 10; index += 1) {
    const roll = hashString(`${index * 7919}#${fighter.name}#${index}`);
    const isWin = roll < (winRate ?? 0.5) * 0.92 + 0.06;
    const change = isWin ? 14 + roll * 22 : -(12 + roll * 18);
    runningElo += change;

    const year = 2021 + Math.floor(index / 2);
    const month = (index % 2) * 6 + 3;

    eloHistory.push({
      event_date: `${year}-${String(month).padStart(2, "0")}-15`,
      opponent: OPPONENT_POOL[Math.floor(roll * OPPONENT_POOL.length) % OPPONENT_POOL.length],
      result: isWin ? "Win" : "Loss",
      prior_elo: runningElo - change,
      plotted_elo: runningElo,
      fight_url: `mock://fight/${fighter.name}/${index}`,
    });
  }

  eloHistory[eloHistory.length - 1].plotted_elo = fighter.elo;

  const recentFights = [...eloHistory].reverse().slice(0, 6).map((row, index) => ({
    fight_url: row.fight_url,
    opponent: row.opponent,
    result: row.result,
    method_category: row.result === "Win" ? (index % 2 ? "KO/TKO" : "Decision") : "Decision",
    round: index % 2 ? 2 : 3,
    time: index % 2 ? "3:24" : "5:00",
    event_date: row.event_date,
    event_name: `UFC Fight Night ${230 + index * 4}`,
    weight_class: fighter.weightClass,
  }));

  const recentResults = recentFights.slice(0, 5).map((row) => row.result);
  const wins5 = recentResults.filter((result) => result === "Win").length;

  let streak = 1;
  for (let index = 1; index < recentResults.length; index += 1) {
    if (recentResults[index] === recentResults[0]) {
      streak += 1;
    } else {
      break;
    }
  }

  const striking = 0.42 + seed * 0.5;
  const grappling = 0.35 + hashString(`${fighter.name}-g`) * 0.55;
  const defense = 0.4 + hashString(`${fighter.name}-d`) * 0.5;

  return delay({
    fighter: fighter.name,
    weight_class: fighter.weightClass,
    image: { image_url: "", initials: undefined },
    headline_stats: {
      elo_formatted: String(Math.round(fighter.elo)),
      peak_elo_formatted: String(Math.round(fighter.peak)),
      ufc_wins: fighter.wins,
      ufc_losses: fighter.losses,
      win_rate_formatted: winRate === null ? "N/A" : percent(winRate),
      age_formatted: `${fighter.age.toFixed(1)} yrs`,
      height: `${Math.floor(fighter.height / 12)}'${fighter.height % 12}"`,
      reach: `${fighter.reach}"`,
    },
    style_profile: {
      style_label: fighter.style,
      tags: fighter.tags,
      note: `${fighter.name} profiles as a ${fighter.style.toLowerCase()} with ${
        fighter.tags[0]?.toLowerCase() || "balanced"
      } tendencies. Labels are heuristic, data-derived scouting context — not official UFC designations.`,
      score_percentages: {
        striking: percent(Math.min(0.95, striking)),
        grappling: percent(Math.min(0.95, grappling)),
        defense: percent(Math.min(0.95, defense)),
      },
    },
    form_summary: {
      last_5_record: `${wins5}-${5 - wins5}`,
      current_streak: `${streak} ${recentResults[0] === "Win" ? "wins" : "losses"}`,
      recent_results: recentResults,
    },
    elo_history: eloHistory,
    notable_rankings: [
      {
        metric: "prior_elo",
        scope: "overall",
        scope_label: "All weight classes",
        category: "Elo",
        rank: 1 + Math.floor(seed * 9),
        description: `Top-10 Elo among qualified active fighters across all weight classes.`,
        formatted_value: `${Math.round(fighter.elo)} Elo`,
      },
      {
        metric: "overall_score",
        scope: "weight_class",
        scope_label: fighter.weightClass,
        category: "Overall",
        rank: 1 + Math.floor(hashString(`${fighter.name}-rank`) * 5),
        description: `Top-5 overall model score inside ${fighter.weightClass}.`,
        formatted_value: `${(0.62 + seed * 0.3).toFixed(3)} score`,
      },
    ],
    method_summary: {
      wins: {
        "KO/TKO": Math.round(fighter.wins * 0.4),
        Submission: Math.round(fighter.wins * 0.3),
        Decision: fighter.wins - Math.round(fighter.wins * 0.4) - Math.round(fighter.wins * 0.3),
      },
      losses: {
        "KO/TKO": Math.min(fighter.losses, 1),
        Decision: Math.max(0, fighter.losses - 1),
      },
      all: {
        "KO/TKO": Math.round(fighter.wins * 0.4) + Math.min(fighter.losses, 1),
        Submission: Math.round(fighter.wins * 0.3),
        Decision:
          fighter.wins - Math.round(fighter.wins * 0.4) - Math.round(fighter.wins * 0.3) +
          Math.max(0, fighter.losses - 1),
      },
    },
    profile_stats: [
      { key: "prior_elo", formatted_value: String(Math.round(fighter.elo)) },
      { key: "prior_peak_elo", formatted_value: String(Math.round(fighter.peak)) },
      { key: "prior_fights", formatted_value: String(totalFights) },
      { key: "prior_win_rate", formatted_value: winRate === null ? "N/A" : percent(winRate) },
      { key: "avg_sig_str_landed_per_15", formatted_value: (28 + seed * 50).toFixed(1) },
      { key: "avg_sig_str_accuracy", formatted_value: percent(0.38 + seed * 0.22) },
      { key: "avg_td_landed_per_15", formatted_value: (seed * 4.5).toFixed(2) },
      { key: "avg_td_defense", formatted_value: percent(0.5 + hashString(`${fighter.name}-td`) * 0.45) },
      { key: "avg_ctrl_seconds_per_15", formatted_value: (40 + grappling * 220).toFixed(0) },
      { key: "height_inches", formatted_value: `${fighter.height}.0` },
      { key: "reach_inches", formatted_value: `${fighter.reach}.0` },
      { key: "age_years", formatted_value: fighter.age.toFixed(1) },
    ],
    recent_fights: recentFights,
  }, 420);
}

export function getFighterImages() {
  return delay([]);
}

const FUTURE_CARDS = [
  {
    event_id: "mock-card-1",
    event_name: "UFC 322: Chimaev vs. Du Plessis 2",
    event_date: "June 27, 2026",
    event_location: "Las Vegas, Nevada, USA",
    fight_count: 5,
    fights: [
      ["Khamzat Chimaev", "Dricus Du Plessis", "Middleweight"],
      ["Islam Makhachev", "Shavkat Rakhmonov", "Welterweight"],
      ["Merab Dvalishvili", "Sean O'Malley", "Bantamweight"],
      ["Alexandre Pantoja", "Joshua Van", "Flyweight"],
      ["Kayla Harrison", "Valentina Shevchenko", "Women's Bantamweight"],
    ],
  },
  {
    event_id: "mock-card-2",
    event_name: "UFC Fight Night: Aspinall vs. Gane",
    event_date: "July 11, 2026",
    event_location: "London, England, UK",
    fight_count: 4,
    fights: [
      ["Tom Aspinall", "Ciryl Gane", "Heavyweight"],
      ["Alex Pereira", "Magomed Ankalaev", "Light Heavyweight"],
      ["Ilia Topuria", "Arman Tsarukyan", "Lightweight"],
      ["Alexander Volkanovski", "Movsar Evloev", "Featherweight"],
    ],
  },
];

const FUTURE_ROUND_OVERRIDES = new Map();
const FUTURE_EVENT_CONTROLS = new Map();

function mockSuggestedStart(card) {
  const start = new Date(`${card.event_date} 18:00`);
  return Number.isNaN(start.getTime()) ? null : start.toISOString();
}

function mockDateLocked(eventDate) {
  const eventDay = new Date(eventDate);
  if (Number.isNaN(eventDay.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  eventDay.setHours(0, 0, 0, 0);
  return today >= eventDay;
}

function mockLockState(card) {
  const control = FUTURE_EVENT_CONTROLS.get(card.event_id) || {};
  const lockMode = control.lock_mode || "auto";
  const manualStart = control.event_start_at_utc || null;
  const suggestedStart = mockSuggestedStart(card);
  const effectiveStart = manualStart || suggestedStart;
  const parsedStart = effectiveStart ? new Date(effectiveStart) : null;
  let locked =
    parsedStart && !Number.isNaN(parsedStart.getTime())
      ? new Date() >= parsedStart
      : mockDateLocked(card.event_date);
  let reason =
    parsedStart && !Number.isNaN(parsedStart.getTime())
      ? "event_start_at_utc"
      : "date_fallback";

  if (lockMode === "force_open") {
    locked = false;
    reason = "force_open";
  } else if (lockMode === "force_locked") {
    locked = true;
    reason = "force_locked";
  }

  return {
    event_id: card.event_id,
    locked: Boolean(locked),
    lock_mode: lockMode,
    lock_reason: reason,
    effective_start_at_utc: effectiveStart,
    effective_source: manualStart ? "manual" : "odds",
    event_start_at_utc: manualStart,
    suggested_start_at_utc: suggestedStart,
    suggested_source: "odds_commence_time",
    suggested_confidence: "high",
    suggested_match_count: card.fights.length,
    suggested_low_confidence_count: 0,
    date_fallback_locked: mockDateLocked(card.event_date),
    updated_at: control.updated_at || "",
  };
}

export function getFutureCards() {
  return delay(
    FUTURE_CARDS.map(({ fights, ...card }) => {
      const source = FUTURE_CARDS.find((row) => row.event_id === card.event_id);
      const lockState = mockLockState(source);
      return {
        ...card,
        fight_count: fights.length,
        lock_state: lockState,
        locked: lockState.locked,
      };
    })
  );
}

export async function getFutureCardPredictions(eventId) {
  const card = FUTURE_CARDS.find((row) => row.event_id === eventId);

  if (!card) {
    throw new Error("Unknown future card.");
  }

  const fights = await Promise.all(
    card.fights.map(async ([fighter1, fighter2, weightClass], index) => {
      const noPrediction = index === card.fights.length - 1 && card.event_id === "mock-card-1";
      const fightId = `${card.event_id}-fight-${index}`;
      const override = FUTURE_ROUND_OVERRIDES.get(fightId);
      const scheduledRounds = override ?? (index === 0 ? 5 : 3);
      const isFightNight = String(card.event_name || "")
        .toLowerCase()
        .startsWith("ufc fight night");
      const base = {
        fight_id: fightId,
        fight_url: `mock://future/${card.event_id}/${index}`,
        fighter_1: fighter1,
        fighter_2: fighter2,
        weight_class: weightClass,
        scheduled_rounds: scheduledRounds,
        is_main_event: index === 0,
        card_position_from_top: index + 1,
        round_override_eligible: (index === 1 || index === 2) && !isFightNight,
        round_override_saved: FUTURE_ROUND_OVERRIDES.has(fightId),
        round_override_source: FUTURE_ROUND_OVERRIDES.has(fightId)
          ? "manual_override"
          : index === 0
            ? "main_event_inference"
            : "default_three_round",
      };

      if (noPrediction) {
        return {
          ...base,
          prediction_available: false,
          prediction: null,
          error: { message: "One or both fighters are missing historical feature data." },
        };
      }

      const prediction = await predictFight(fighter1, fighter2, weightClass);

      return { ...base, prediction_available: true, prediction };
    })
  );

  const lockState = mockLockState(card);
  return delay({ ...card, lock_state: lockState, locked: lockState.locked, fights }, 350);
}

// Model-free card detail for the picks tab (no predictions).
export function getFutureCardDetail(eventId) {
  const card = FUTURE_CARDS.find((row) => row.event_id === eventId);

  if (!card) {
    throw new Error("Unknown future card.");
  }

  const fights = card.fights.map(([fighter_1, fighter_2, weight_class], index) => ({
    fight_id: `${card.event_id}-fight-${index}`,
    fight_url: `mock://future/${card.event_id}/${index}`,
    fighter_1,
    fighter_2,
    weight_class,
  }));

  return delay(
    {
      event_id: card.event_id,
      event_name: card.event_name,
      event_date: card.event_date,
      event_location: card.event_location,
      lock_state: mockLockState(card),
      locked: mockLockState(card).locked,
      fights,
    },
    200
  );
}

// --- account picks (Phase 6) — in-memory so the picks tab works under mock ---

const MOCK_PICKS = new Map(); // fight_url -> pick

function mockFindFight(fightUrl) {
  for (const card of FUTURE_CARDS) {
    const index = card.fights.findIndex(
      (_, i) => `mock://future/${card.event_id}/${i}` === fightUrl
    );
    if (index >= 0) {
      const [fighter_1, fighter_2, weight_class] = card.fights[index];
      return { card, fighter_1, fighter_2, weight_class };
    }
  }
  return null;
}

export function listPredictions(eventId) {
  const picks = [...MOCK_PICKS.values()].filter(
    (pick) => !eventId || pick.event_id === eventId
  ).map((pick) => {
    const card = FUTURE_CARDS.find((row) => row.event_id === pick.event_id);
    const lockState = card ? mockLockState(card) : { locked: mockDateLocked(pick.event_date) };
    return { ...pick, locked: lockState.locked, lock_state: lockState };
  });
  return delay(picks, 120);
}

export function savePrediction(fightUrl, pickedFighter, pickedMethod = null) {
  const found = mockFindFight(fightUrl);
  if (!found) {
    throw new Error("That fight isn't on an upcoming card.");
  }
  const { card, fighter_1, fighter_2, weight_class } = found;
  if (![fighter_1, fighter_2].includes(pickedFighter)) {
    throw new Error("Pick one of the two fighters in this bout.");
  }
  if (mockLockState(card).locked) {
    throw new Error("Picks for this event are locked.");
  }

  const pick = {
    fight_url: fightUrl,
    event_id: card.event_id,
    event_name: card.event_name,
    event_date: card.event_date,
    fighter_1,
    fighter_2,
    weight_class,
    picked_fighter: pickedFighter,
    picked_method: pickedMethod || null,
    status: "open",
    result_correct: null,
    method_correct: null,
    locked: mockLockState(card).locked,
    lock_state: mockLockState(card),
  };
  MOCK_PICKS.set(fightUrl, pick);
  return delay(pick, 120);
}

export function deletePrediction(fightUrl) {
  const existing = MOCK_PICKS.get(fightUrl);
  const card = existing ? FUTURE_CARDS.find((row) => row.event_id === existing.event_id) : null;
  if (existing && card && mockLockState(card).locked) {
    throw new Error("Picks for this event are locked.");
  }
  const removed = MOCK_PICKS.delete(fightUrl);
  return delay({ removed }, 100);
}

// Demo stats so the profile tiles look alive under mock (no real scoring in mock).
export function getMyStats() {
  return delay(
    {
      rating: 1063,
      record: { wins: 7, losses: 4 },
      graded: 11,
      accuracy: 7 / 11,
      streak: { type: "W", count: 2 },
      method: { picks: 5, hits: 3, accuracy: 3 / 5 },
      vs_model: {
        overlap: 11,
        user_accuracy: 7 / 11,
        model_accuracy: 6 / 11,
        delta: 1 / 11,
        user_beats: 3,
        model_beats: 2,
      },
      pending: 1,
      voided: 0,
    },
    150
  );
}

export function getUserLeaderboard() {
  return delay(
    [
      { rank: 1, display_name: "slipznslams", name: "slipznslams", rating: 1112, wins: 14, losses: 6, graded: 20, accuracy: 14 / 20, provisional: false, provisional_threshold: 10, picks_until_established: 0, is_me: false },
      { rank: 2, display_name: "demo", name: "demo", rating: 1063, wins: 7, losses: 4, graded: 11, accuracy: 7 / 11, provisional: false, provisional_threshold: 10, picks_until_established: 0, is_me: true },
      { rank: 3, display_name: "KO_Karen", name: "KO_Karen", rating: 1041, wins: 9, losses: 7, graded: 16, accuracy: 9 / 16, provisional: false, provisional_threshold: 10, picks_until_established: 0, is_me: false },
      { rank: 4, display_name: "NorthStar", name: "NorthStar", rating: 1000, wins: 2, losses: 1, graded: 3, accuracy: 2 / 3, provisional: true, provisional_threshold: 10, picks_until_established: 7, is_me: false },
    ],
    150
  );
}

// --- friends (Phase 6) — canned demo data ---

export function getFriends() {
  return delay(
    {
      friends: [
        { user_id: 3, display_name: "KO_Karen", friendship_id: 30 },
        { user_id: 5, display_name: "slipznslams", friendship_id: 31 },
      ],
      incoming: [{ user_id: 7, display_name: "NorthStar", friendship_id: 40 }],
      outgoing: [{ user_id: 9, display_name: "GrappleGus", friendship_id: 41 }],
    },
    150
  );
}

export function sendFriendRequest(username) {
  return delay({ status: "pending", friend: { user_id: 99, display_name: username, friendship_id: 99 } }, 150);
}

export function respondFriendRequest(friendshipId, accept) {
  return delay({ status: accept ? "accepted" : "declined" }, 120);
}

export function removeFriend() {
  return delay({ removed: true }, 120);
}

export function getFriendCompare(userId) {
  const name = userId === 5 ? "slipznslams" : "KO_Karen";
  return delay(
    {
      friend: { user_id: userId, display_name: name },
      shared: 12,
      you: { correct: 8, accuracy: 8 / 12, rating: 1063 },
      them: { correct: 7, accuracy: 7 / 12, rating: 1041 },
      card_record: { you: 2, them: 1, tied: 0 },
      cards: [
        {
          event_id: "e1", event_name: "UFC 322: Chimaev vs. Du Plessis 2", event_date: "June 27, 2026",
          total: 5, you_correct: 4, them_correct: 2, winner: "you",
          fights: [
            { fighter_1: "Khamzat Chimaev", fighter_2: "Dricus Du Plessis", actual_winner: "Khamzat Chimaev", your_pick: "Khamzat Chimaev", your_correct: true, their_pick: "Dricus Du Plessis", their_correct: false },
            { fighter_1: "Islam Makhachev", fighter_2: "Shavkat Rakhmonov", actual_winner: "Islam Makhachev", your_pick: "Islam Makhachev", your_correct: true, their_pick: "Islam Makhachev", their_correct: true },
          ],
        },
        {
          event_id: "e2", event_name: "UFC Fight Night: Aspinall vs. Gane", event_date: "July 11, 2026",
          total: 4, you_correct: 2, them_correct: 3, winner: "them",
          fights: [
            { fighter_1: "Tom Aspinall", fighter_2: "Ciryl Gane", actual_winner: "Tom Aspinall", your_pick: "Ciryl Gane", your_correct: false, their_pick: "Tom Aspinall", their_correct: true },
          ],
        },
      ],
    },
    200
  );
}

export async function updateFutureFightScheduledRounds(eventId, fightId, scheduledRounds) {
  const card = FUTURE_CARDS.find((row) => row.event_id === eventId);

  if (!card) {
    throw new Error("Unknown future card.");
  }

  if (![3, 5].includes(Number(scheduledRounds))) {
    throw new Error("Scheduled rounds must be 3 or 5.");
  }

  FUTURE_ROUND_OVERRIDES.set(fightId, Number(scheduledRounds));

  return delay(
    {
      message: "Scheduled-rounds override saved.",
      event_id: eventId,
      fight_id: fightId,
      override: {
        scheduled_rounds: Number(scheduledRounds),
        source: "manual",
      },
      card: await getFutureCardPredictions(eventId),
    },
    180
  );
}

export async function updateFutureEventControl(eventId, payload = {}) {
  const card = FUTURE_CARDS.find((row) => row.event_id === eventId);

  if (!card) {
    throw new Error("Unknown future card.");
  }

  const mode = payload.lock_mode || "auto";
  if (!["auto", "force_open", "force_locked"].includes(mode)) {
    throw new Error("Lock mode must be auto, force_open, or force_locked.");
  }

  const control = {
    event_id: eventId,
    event_name: card.event_name,
    event_date: card.event_date,
    event_start_at_utc: payload.event_start_at_utc || null,
    lock_mode: mode,
    updated_at: new Date().toISOString().slice(0, 19),
  };
  FUTURE_EVENT_CONTROLS.set(eventId, control);

  return delay(
    {
      message: "Event lock controls saved.",
      event_control: control,
      lock_state: mockLockState(card),
      card: await getFutureCardPredictions(eventId),
    },
    180
  );
}

export function getFutureFightOdds() {
  const rows = [];

  for (const card of FUTURE_CARDS) {
    card.fights.forEach(([fighter1, fighter2], index) => {
      const seed = hashString(`${fighter1}-odds`);
      const favorite1 = seed > 0.45;
      const probability = 0.52 + seed * 0.3;
      const favoriteOdds = -Math.round((probability / (1 - probability)) * 100);
      const dogOdds = Math.round(((1 - probability) > 0 ? probability / (1 - probability) : 1) * 100) + 15;

      rows.push({
        fight_url: `mock://future/${card.event_id}/${index}`,
        odds_available: true,
        odds_commence_time: mockSuggestedStart(card),
        fighter_1: fighter1,
        fighter_2: fighter2,
        market_favorite: favorite1 ? fighter1 : fighter2,
        market_favorite_percentage: percent(probability),
        fighter_1_odds_american: favorite1 ? favoriteOdds : dogOdds,
        fighter_2_odds_american: favorite1 ? dogOdds : favoriteOdds,
        fighter_1_market_probability: favorite1 ? probability : 1 - probability,
        fighter_2_market_probability: favorite1 ? 1 - probability : probability,
        fighter_1_market_percentage: percent(favorite1 ? probability : 1 - probability),
        fighter_2_market_percentage: percent(favorite1 ? 1 - probability : probability),
        odds_bookmaker: "Consensus (no-vig)",
        bookmakers_matched: 6,
      });
    });
  }

  return delay(rows);
}

const RECENT_CARDS = [
  {
    event_id: "mock-recent-1",
    event_name: "UFC 321: Makhachev vs. Della Maddalena",
    event_date: "May 16, 2026",
    event_location: "Abu Dhabi, UAE",
    status: "completed",
    fights: [
      ["Islam Makhachev", "Jack Della Maddalena", "Welterweight", "Islam Makhachev", "Submission", 3],
      ["Ilia Topuria", "Charles Oliveira", "Lightweight", "Ilia Topuria", "KO/TKO", 1],
      ["Merab Dvalishvili", "Sean O'Malley", "Bantamweight", "Merab Dvalishvili", "Decision", 5],
      ["Belal Muhammad", "Shavkat Rakhmonov", "Welterweight", "Shavkat Rakhmonov", "Decision", 5],
    ],
  },
  {
    event_id: "mock-recent-2",
    event_name: "UFC Fight Night: Imavov vs. Strickland",
    event_date: "June 6, 2026",
    event_location: "Paris, France",
    status: "waiting",
    fights: [
      ["Nassourdine Imavov", "Sean Strickland", "Middleweight", null, null, null],
      ["Max Holloway", "Arman Tsarukyan", "Lightweight", null, null, null],
      ["Movsar Evloev", "Alexander Volkanovski", "Featherweight", null, null, null],
    ],
  },
];

function buildRecentFight(card, fight, index) {
  const [fighter1, fighter2, weightClass, actualWinner, method, round] = fight;
  const probability1 = buildProbability(fighter1, fighter2);
  const predictedWinner = probability1 >= 0.5 ? fighter1 : fighter2;
  const confidence = Math.max(probability1, 1 - probability1);
  const resultAvailable = Boolean(actualWinner);
  const seed = hashString(`${fighter1}-odds`);
  const favorite1 = seed > 0.45;
  const marketFavorite = favorite1 ? fighter1 : fighter2;
  const marketProbability = 0.52 + seed * 0.3;

  return {
    fight_id: `${card.event_id}-fight-${index}`,
    fight_url: `mock://recent/${card.event_id}/${index}`,
    fighter_1: fighter1,
    fighter_2: fighter2,
    weight_class: weightClass,
    prediction_available: true,
    predicted_winner: predictedWinner,
    confidence_percentage: percent(confidence),
    confidence_label: confidenceLabel(confidence),
    fighter_1_percentage: percent(probability1),
    fighter_2_percentage: percent(1 - probability1),
    model_name: "calibrated_xgboost",
    saved_at: "2026-05-12 09:30",
    actual_result_available: resultAvailable,
    actual_winner: actualWinner,
    actual_method: method,
    actual_round: round,
    actual_time: resultAvailable ? (round === 5 ? "5:00" : "3:41") : null,
    prediction_correct: resultAvailable ? actualWinner === predictedWinner : null,
    odds_available: true,
    market_favorite: marketFavorite,
    market_favorite_percentage: percent(marketProbability),
    fighter_1_odds_american: favorite1 ? -165 : 140,
    fighter_2_odds_american: favorite1 ? 140 : -165,
    fighter_1_market_percentage: percent(favorite1 ? marketProbability : 1 - marketProbability),
    fighter_2_market_percentage: percent(favorite1 ? 1 - marketProbability : marketProbability),
    odds_bookmaker: "Consensus (no-vig)",
    bookmakers_matched: 5,
    market_correct: resultAvailable ? actualWinner === marketFavorite : null,
  };
}

function buildRecentCardDetail(card) {
  const fights = card.fights.map((fight, index) => buildRecentFight(card, fight, index));
  const scored = fights.filter((fight) => fight.actual_result_available);
  const correct = scored.filter((fight) => fight.prediction_correct).length;

  return {
    event_id: card.event_id,
    event_name: card.event_name,
    event_date: card.event_date,
    event_location: card.event_location,
    status: card.status,
    fight_count: fights.length,
    actual_result_count: scored.length,
    accuracy_percentage: scored.length ? percent(correct / scored.length) : "",
    fights,
  };
}

export function getRecentCards() {
  return delay(
    RECENT_CARDS.map((card) => {
      const detail = buildRecentCardDetail(card);
      const { fights, ...summary } = detail;
      void fights;
      return summary;
    })
  );
}

export function getRecentCardDetail(eventId) {
  const card = RECENT_CARDS.find((row) => row.event_id === eventId);

  if (!card) {
    return Promise.reject(new Error("Unknown recent card."));
  }

  return delay(buildRecentCardDetail(card), 320);
}

export function getLeaderboardOptions() {
  return delay({
    scopes: [
      { value: "overall", label: "Overall" },
      { value: "weight_class", label: "By Weight Class" },
    ],
    weight_classes: WEIGHT_CLASSES.slice(0, 8),
    categories: [
      { value: "overall", label: "Overall" },
      { value: "striking", label: "Striking" },
      { value: "grappling", label: "Grappling" },
      { value: "wrestling", label: "Wrestling" },
      { value: "finishing", label: "Finishing" },
      { value: "defense", label: "Defense" },
      { value: "elo", label: "Elo" },
      { value: "experience", label: "Experience" },
      { value: "reach", label: "Reach" },
      { value: "reach_for_size", label: "Reach for Size" },
    ],
    directions: [
      { value: "best", label: "Best" },
      { value: "worst", label: "Worst" },
    ],
  });
}

function leaderboardRows(category, direction, pool, top = 5) {
  const scored = pool.map((fighter) => {
    const seed = hashString(`${fighter.name}-${category}`);
    return {
      fighter,
      score:
        category === "elo"
          ? fighter.elo
          : Number((0.35 + seed * 0.6).toFixed(3)),
    };
  });

  scored.sort((rowA, rowB) =>
    direction === "best" ? rowB.score - rowA.score : rowA.score - rowB.score
  );

  return scored.slice(0, top).map((row, index) => ({
    rank: index + 1,
    fighter: row.fighter.name,
    weight_class: row.fighter.weightClass,
    prior_fights: row.fighter.wins + row.fighter.losses,
    score: row.score,
    days_since_last_fight: 90 + Math.round(hashString(`${row.fighter.name}-days`) * 300),
    supporting_stats: {
      prior_elo: row.fighter.elo,
      prior_win_rate:
        row.fighter.wins / (row.fighter.wins + row.fighter.losses || 1),
      avg_sig_str_landed_per_15: 25 + hashString(`${row.fighter.name}-str`) * 55,
      reach_inches: row.fighter.reach,
    },
  }));
}

export function getLeaderboards() {
  const categories = [
    "overall", "striking", "grappling", "wrestling", "finishing",
    "defense", "elo", "experience", "reach", "reach_for_size",
  ];

  const overall = { categories: {} };

  for (const category of categories) {
    overall.categories[category] = {
      best: leaderboardRows(category, "best", FIGHTERS),
      worst: leaderboardRows(category, "worst", FIGHTERS),
    };
  }

  const weightClasses = {};

  for (const weightClass of WEIGHT_CLASSES) {
    const pool = FIGHTERS.filter((fighter) => fighter.weightClass === weightClass);

    if (!pool.length) {
      continue;
    }

    weightClasses[weightClass] = { categories: {} };

    for (const category of categories) {
      weightClasses[weightClass].categories[category] = {
        best: leaderboardRows(category, "best", pool),
        worst: leaderboardRows(category, "worst", pool),
      };
    }
  }

  return delay({
    metadata: {
      qualified_fighters: FIGHTERS.length,
      min_fights: 5,
      max_inactive_days: 1095,
    },
    overall,
    weight_classes: weightClasses,
  }, 350);
}

export function getModelEvaluation() {
  const buckets = [
    ["Very close / low confidence", 142, 0.521, 0.527],
    ["Slight lean", 217, 0.562, 0.574],
    ["Moderate lean", 198, 0.612, 0.623],
    ["Strong lean", 154, 0.682, 0.673],
    ["High confidence", 173, 0.792, 0.757],
  ];

  const weightClasses = [
    ["Lightweight", 131, 0.649, 0.638],
    ["Welterweight", 124, 0.637, 0.631],
    ["Middleweight", 102, 0.667, 0.642],
    ["Bantamweight", 98, 0.622, 0.628],
    ["Heavyweight", 84, 0.595, 0.647],
    ["Featherweight", 92, 0.652, 0.633],
    ["Light Heavyweight", 76, 0.618, 0.644],
    ["Flyweight", 67, 0.687, 0.629],
  ];

  const years = [
    ["2023", 214, 0.636, 0.633],
    ["2024", 297, 0.653, 0.638],
    ["2025", 288, 0.642, 0.635],
    ["2026", 85, 0.671, 0.641],
  ];

  function summaryRow([name, fights, accuracy, averageConfidence]) {
    return {
      name,
      fight_count: fights,
      accuracy,
      accuracy_percentage: percent(accuracy),
      average_confidence: averageConfidence,
      average_confidence_percentage: percent(averageConfidence),
      correct_count: Math.round(fights * accuracy),
      wrong_count: fights - Math.round(fights * accuracy),
    };
  }

  const samplePredictions = (correct) =>
    FIGHTERS.slice(0, 8).map((fighter, index) => {
      const opponent = FIGHTERS[(index + 9) % FIGHTERS.length];
      const confidence = 0.86 - index * 0.025;

      return {
        event_date: `2026-0${(index % 5) + 1}-1${index}`,
        event_name: `UFC ${310 + index}`,
        weight_class: fighter.weightClass,
        fighter_a: fighter.name,
        fighter_b: opponent.name,
        predicted_winner: correct ? fighter.name : opponent.name,
        actual_winner: fighter.name,
        prediction_correct: correct,
        confidence,
        confidence_percentage: percent(confidence),
        confidence_bucket: confidenceLabel(confidence),
      };
    });

  return delay({
    metadata: {
      test_fraction: 0.2,
      train_rows: 13544,
      test_rows: 3386,
      test_fights: 884,
      test_date_min: "March 12, 2023",
      test_date_max: "May 30, 2026",
      saved_best_model_name: "calibrated_xgboost",
      metric_note:
        "Fight accuracy and confidence use one row per fight with two-perspective normalization. Brier score, log loss, and ROC AUC use row-level holdout data.",
    },
    overall: {
      fight_count: 884,
      accuracy: 0.643,
      accuracy_percentage: "64.3%",
      average_confidence: 0.628,
      average_confidence_percentage: "62.8%",
      row_count: 3386,
      brier_score: 0.2216,
      log_loss: 0.6334,
      roc_auc: 0.6912,
    },
    by_weight_class: weightClasses.map(summaryRow),
    by_year: years.map(summaryRow),
    by_confidence_bucket: buckets.map(summaryRow),
    by_favorite_threshold: [
      ["60%+ favorites", 412, 0.689, 0.671],
      ["65%+ favorites", 286, 0.717, 0.703],
      ["70%+ favorites", 173, 0.792, 0.757],
    ].map(summaryRow),
    recent_predictions: samplePredictions(true).slice(0, 6),
    most_confident_correct: samplePredictions(true),
    most_confident_wrong: samplePredictions(false),
  }, 400);
}

export function getMethodModelMetrics() {
  return delay({
    available: true,
    message: "Method model metrics loaded.",
    metrics: {
      broad: {
        best_model_name: "xgboost",
        best_metrics: { accuracy: 0.531, log_loss: 1.012, macro_f1: 0.44 },
      },
      detailed: {
        best_model_name: "xgboost",
        best_metrics: { accuracy: 0.391, log_loss: 1.684, macro_f1: 0.27 },
      },
    },
  });
}

export function getModelMarketEvaluation() {
  return delay({
    message:
      "Comparison limited to fights where odds were saved locally before the event.",
    scored_fights: 118,
    models: [
      {
        model_name: "calibrated_xgboost",
        is_current_best_model: true,
        scored_fights: 118,
        accuracy: 0.644,
        accuracy_percentage: "64.4%",
        brier_score: 0.2198,
        log_loss: 0.6301,
        average_confidence_percentage: "63.1%",
        calibration_gap_percentage_points: 1.3,
      },
      {
        model_name: "market_no_vig_favorite",
        scored_fights: 118,
        accuracy: 0.661,
        accuracy_percentage: "66.1%",
        brier_score: 0.2144,
        log_loss: 0.6189,
        average_confidence_percentage: "64.8%",
        calibration_gap_percentage_points: 1.1,
      },
    ],
  });
}

export function getWalkForwardEvaluation() {
  const folds = [
    { test_year: 2021, train_fights: 5789, test_fights: 497, test_rows: 994, accuracy: 0.618, brier_score: 0.245, log_loss: 0.694, roc_auc: 0.627, elo_baseline_accuracy: 0.562, model_minus_elo_accuracy: 0.055 },
    { test_year: 2022, train_fights: 6286, test_fights: 506, test_rows: 1012, accuracy: 0.621, brier_score: 0.232, log_loss: 0.658, roc_auc: 0.656, elo_baseline_accuracy: 0.574, model_minus_elo_accuracy: 0.046 },
    { test_year: 2023, train_fights: 6792, test_fights: 504, test_rows: 1008, accuracy: 0.601, brier_score: 0.234, log_loss: 0.66, roc_auc: 0.648, elo_baseline_accuracy: 0.552, model_minus_elo_accuracy: 0.05 },
    { test_year: 2024, train_fights: 7296, test_fights: 513, test_rows: 1026, accuracy: 0.63, brier_score: 0.227, log_loss: 0.647, roc_auc: 0.673, elo_baseline_accuracy: 0.55, model_minus_elo_accuracy: 0.08 },
    { test_year: 2025, train_fights: 7809, test_fights: 515, test_rows: 1030, accuracy: 0.666, brier_score: 0.221, log_loss: 0.633, roc_auc: 0.702, elo_baseline_accuracy: 0.57, model_minus_elo_accuracy: 0.096 },
  ];

  return delay({
    available: true,
    message: "",
    metadata: {
      model_type: "logistic_regression",
      calibration_method: "none",
      n_folds: folds.length,
      requested_folds: folds.length,
      min_test_fights: 150,
      min_train_fights: 1000,
      feature_count: 96,
      metric_note:
        "Each fold trains a fresh model on every fight before that test year, then scores that year out-of-sample.",
    },
    aggregate: {
      accuracy: { mean: 0.6272, std: 0.0247, ci95: 0.0217, n: folds.length },
      brier_score: { mean: 0.2318, std: 0.0089, ci95: 0.0078, n: folds.length },
      log_loss: { mean: 0.6584, std: 0.0223, ci95: 0.0196, n: folds.length },
      roc_auc: { mean: 0.6612, std: 0.0277, ci95: 0.0243, n: folds.length },
      model_minus_elo_accuracy: { mean: 0.0654, std: 0.0218, ci95: 0.0191, n: folds.length },
      elo_baseline_accuracy: { mean: 0.5616, std: 0.0103, ci95: 0.009, n: folds.length },
    },
    folds,
  });
}

export function getModelSnapshotEvaluation() {
  return delay({
    message: "Prospective evaluation of saved pre-fight prediction snapshots.",
    prediction_rows: 642,
    scored_fights: 287,
    model_count: 3,
    models: [
      {
        model_name: "calibrated_xgboost",
        is_current_best_model: true,
        saved_prediction_rows: 642,
        saved_unique_fights: 321,
        scored_fights: 287,
        pending_fights: 34,
        accuracy: 0.652,
        accuracy_percentage: "65.2%",
        brier_score: 0.2187,
        log_loss: 0.6275,
        average_confidence_percentage: "63.4%",
        calibration_gap_percentage_points: 1.8,
      },
      {
        model_name: "calibrated_random_forest",
        saved_prediction_rows: 598,
        saved_unique_fights: 299,
        scored_fights: 265,
        pending_fights: 34,
        accuracy: 0.628,
        accuracy_percentage: "62.8%",
        brier_score: 0.2244,
        log_loss: 0.6412,
        average_confidence_percentage: "61.9%",
        calibration_gap_percentage_points: 0.9,
      },
      {
        model_name: "elo_baseline",
        saved_prediction_rows: 598,
        saved_unique_fights: 299,
        scored_fights: 265,
        pending_fights: 34,
        accuracy: 0.601,
        accuracy_percentage: "60.1%",
        brier_score: 0.2331,
        log_loss: 0.6588,
        average_confidence_percentage: "60.2%",
        calibration_gap_percentage_points: 0.1,
      },
    ],
  });
}

export function getDataQualitySummary() {
  return delay({
    available: true,
    generated_at: "2026-06-26T12:00:00",
    fighters: {
      total: 2688,
      inactive_over_3_years: 1801,
      inactive_over_3_years_percentage: "67.0%",
      low_sample_under_3_fights: 842,
      low_sample_under_3_fights_percentage: "31.3%",
      low_sample_under_5_fights: 1220,
      low_sample_under_5_fights_percentage: "45.4%",
      missing_reach: 164,
      missing_age: 29,
      missing_height: 81,
    },
    future_cards: {
      upcoming_fights: 63,
      future_odds_rows: 63,
      odds_available: 19,
      odds_missing: 44,
      odds_coverage_percentage: "30.2%",
    },
    saved_predictions: {
      saved_card_rows: 121,
      prediction_available: 99,
      prediction_unavailable: 22,
      prediction_coverage_percentage: "81.8%",
      odds_available: 34,
      odds_missing: 87,
      odds_coverage_percentage: "28.1%",
      top_unavailable_fighters: [
        { fighter: "Juan Diaz", count: 1 },
        { fighter: "Christian Edwards", count: 1 },
      ],
    },
    historical_results: {
      event_fights: 7850,
      clear_win_loss: 7728,
      draws: 46,
      no_contests: 76,
      dq_or_overturned: 24,
    },
  });
}

let mockUpdateState = {
  running: false,
  started_at: null,
  finished_at: "2026-06-08T22:41:10",
  current_stage: null,
  current_stage_index: 0,
  total_stages: 18,
  progress_percent: 0,
  message: "No update has been started this session.",
  success: true,
  error: null,
};

const MOCK_STAGES = [
  "Refresh completed events",
  "Add newly completed fights",
  "Score user predictions",
  "Scrape missing fight details",
  "Refresh fighter profiles",
  "Rebuild fighter snapshots",
  "Add Elo features",
  "Add physical features",
  "Add age features",
  "Rebuild matchup training rows",
  "Build method training data",
  "Train method models",
  "Train calibrated model",
  "Rebuild current fighter data",
  "Refresh future cards",
  "Refresh future fight odds",
  "Train market shadow models",
  "Save future-card predictions",
];

export function getUpdateStatus() {
  if (mockUpdateState.running) {
    const nextIndex = Math.min(
      mockUpdateState.current_stage_index + 1,
      MOCK_STAGES.length
    );

    mockUpdateState = {
      ...mockUpdateState,
      current_stage_index: nextIndex,
      current_stage: MOCK_STAGES[Math.min(nextIndex - 1, MOCK_STAGES.length - 1)],
      progress_percent: Math.round((nextIndex / MOCK_STAGES.length) * 100),
      message: `Running stage ${nextIndex} of ${MOCK_STAGES.length}…`,
    };

    if (nextIndex >= MOCK_STAGES.length) {
      mockUpdateState = {
        ...mockUpdateState,
        running: false,
        finished_at: new Date().toISOString().slice(0, 19),
        progress_percent: 100,
        message: "Incremental update completed successfully.",
        success: true,
      };
    }
  }

  return delay({ ...mockUpdateState }, 150);
}

export function startIncrementalUpdate() {
  mockUpdateState = {
    ...mockUpdateState,
    running: true,
    started_at: new Date().toISOString().slice(0, 19),
    finished_at: null,
    current_stage_index: 0,
    current_stage: MOCK_STAGES[0],
    total_stages: MOCK_STAGES.length,
    progress_percent: 0,
    message: "Incremental update is starting.",
    success: null,
    error: null,
  };

  return delay({ message: "Incremental update started.", status: { ...mockUpdateState } });
}

export function getLatestUpdateReport() {
  return delay({
    message: "Latest incremental update report loaded.",
    report: {
      started_at: "2026-06-08T22:18:44",
      finished_at: "2026-06-08T22:41:10",
      duration_seconds: 1346,
      summary: {
        success: true,
        new_fights_added: 13,
        saved_card_predictions_rows: 642,
      },
      stages: MOCK_STAGES.map((name, index) => ({
        name,
        status: "completed",
        duration_seconds: 18 + ((index * 37) % 160),
        details:
          name === "Train calibrated model"
            ? {
                best_model_name: "calibrated_xgboost",
                best_model_metrics: { accuracy: 0.643, brier_score: 0.2216 },
              }
            : { rows_processed: 120 + index * 48 },
      })),
    },
  });
}
