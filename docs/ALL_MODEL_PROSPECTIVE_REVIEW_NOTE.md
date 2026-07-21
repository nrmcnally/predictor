# FightIQ All-Model Prospective Review Checkpoint

**Created:** July 21, 2026  
**Status:** Tracking note only; no UI work or model-routing change is authorized by this note.

## Purpose

FightIQ saves the selected production prediction in `saved_card_predictions` and the
latest per-card predictions from every registered evaluation candidate in
`saved_model_predictions`. The all-model history should be reviewed again after the
current model generation has enough completed fights to distinguish repeatable model
behavior from one-card noise.

## Current storage boundary

- On each predictable fight, the active all-model pass saves 15 registered winner
  candidates plus the Elo baseline and ensemble average: 17 rows.
- Five additional market-shadow rows are saved only when the required odds inputs exist.
- A fight that cannot be predicted receives an explicit unavailable/error row.
- `saved_model_predictions` keeps the latest snapshot per card; it is not a history of
  every refresh.
- The full-history production refit is evaluated through its separately frozen
  `saved_card_predictions` row. The candidate named `logistic_regression` is not the
  same fitted artifact as `best_winner_model`, even though they share a recipe.

## July 21 exploratory baseline

These are descriptive observations, not selection evidence:

- The long-running core models share 65 completed fights across seven events.
- Logistic regression leads at 45/65 (69.2%); XGBoost and histogram gradient boosting
  are 44/65; Elo is 40/65. The entire first-to-last difference is five fights.
- All core models were unanimous on 37 fights and went 28/37 (75.7%). They split on 28
  fights and went 14/28 (50.0%). Model disagreement is currently the strongest useful
  reliability signal.
- Logistic regression went 34/46 on Fight Nights but 5/12 on the one conventional
  numbered card. XGBoost went 8/12 on that numbered card. This is interesting but is
  not a basis for card-type model routing.
- On 24 common odds-covered fights, the market-only logistic shadow went 20/24, the
  model-plus-market logistic shadow went 19/24, and raw market probabilities had the
  best Brier score. The isotonic model-plus-market shadow was severely overconfident.
- Raw and sigmoid-calibrated versions made identical winner picks. Calibration changed
  probability quality, not decision diversity. Elo was weakest overall but most often
  correct when the model majority was wrong.
- Weight-class results are too small for specialization claims. In particular, every
  model struggled on the eight completed lightweight fights.

## Review trigger

Repeat the analysis after **at least 100 common completed, pre-event predictions from
one fixed model generation and at least 10 completed events**. Do not mix generations
without reporting them separately. Card-type conclusions additionally require several
completed numbered cards, not one.

## Required review

1. Verify every scored row was frozen before the fight, was not overwritten post-event,
   has a model/version/recipe hash, and maps to a clean official result.
2. Compare models on identical fights using accuracy with intervals, Brier score, log
   loss, calibration gap/curve, and event-clustered uncertainty.
3. Report cohorts for confidence, card type, weight class, scheduled rounds, data depth,
   missingness, layoffs, weight moves, and replacement bouts where coverage permits.
4. Measure pairwise disagreement, unanimous-versus-split performance, majority errors,
   and each model's unique correct calls.
5. Compare raw, sigmoid, isotonic, and any beta-calibrated variants on the same fights.
6. Compare market-only, model-only, and combined shadows only on timestamp-aligned odds
   rows, using both hard-pick accuracy and proper probability scores.
7. Keep results exploratory unless an apparent specialization survives event-grouped
   chronological evaluation and a prospective generation-level replication.

## Decision boundary

Do not add automatic model switching, card-type routing, or stronger public confidence
language from this exploratory table. A future change needs a predeclared experiment,
event-grouped validation, no material calibration regression, and a prospective shadow
period. Until then, use cross-model disagreement as a research flag rather than a new
serving rule.
