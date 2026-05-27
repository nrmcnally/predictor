function formatAmericanOdds(value) {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  const numberValue = Number(value);

  if (!Number.isFinite(numberValue)) {
    return String(value);
  }

  return numberValue > 0 ? `+${numberValue}` : `${numberValue}`;
}

export default function FightOddsComparison({ fight, odds }) {
  if (!odds || !odds.odds_available) {
    return (
      <div className="odds-comparison muted">
        <span>Market odds unavailable</span>
      </div>
    );
  }

  const fighter1Name = fight?.fighter_1 || "Fighter 1";
  const fighter2Name = fight?.fighter_2 || "Fighter 2";

  return (
    <div className="odds-comparison">
      <div>
        <span>Market favorite</span>
        <strong>
          {odds.market_favorite || "Unknown"}{" "}
          {odds.market_favorite_percentage || ""}
        </strong>
      </div>

      <div>
        <span>{fighter1Name}</span>
        <strong>
          {formatAmericanOdds(odds.fighter_1_odds_american)} •{" "}
          {odds.fighter_1_market_percentage || "N/A"}
        </strong>
      </div>

      <div>
        <span>{fighter2Name}</span>
        <strong>
          {formatAmericanOdds(odds.fighter_2_odds_american)} •{" "}
          {odds.fighter_2_market_percentage || "N/A"}
        </strong>
      </div>

      <small>
        {odds.odds_bookmaker
          ? `${odds.odds_bookmaker}${odds.bookmakers_matched ? ` • ${odds.bookmakers_matched} books` : ""}`
          : "Market odds source unavailable"}
      </small>

      <small className="odds-comparison-note">
        Market odds are shown for comparison only and are not used as model features.
      </small>
    </div>
  );
}
