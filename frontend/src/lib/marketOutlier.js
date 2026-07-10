/* A resolved market outlier: the model went against the market favorite. When they
   disagree, exactly one of prediction_correct / market_correct is true — so green
   ("market-beat") when the model's side won, red ("market-lost") when the market's
   did, and "" when they agreed or the fight isn't scored. */
export function marketOutlierState(fight) {
  if (
    fight.prediction_correct === null ||
    fight.prediction_correct === undefined ||
    fight.market_correct === null ||
    fight.market_correct === undefined
  ) {
    return "";
  }
  if (Boolean(fight.prediction_correct) === Boolean(fight.market_correct)) {
    return "";
  }
  return fight.prediction_correct ? "market-beat" : "market-lost";
}
