# Reading the Tea Leaves

## A practical guide to FightIQ predictions

**Status:** Current implementation guide
**Repository:** `C:\Users\nrmcn\predictor\threejs`
**Evidence snapshot:** July 13, 2026, commit `14bf2d4`
**Audience:** FightIQ users, reviewers, and developers

---

## What this guide is for

FightIQ presents several kinds of evidence on the same fight card: a calibrated winner probability, market odds, data-quality warnings, and sometimes a market total. These values answer different questions. They should not be combined casually.

This guide explains what each value means, what it does not mean, and how to make a disciplined reading of a prediction. It reflects the implementation and model artifacts in the `threejs` repository at the evidence snapshot above. Proposed behavior is explicitly labeled.

The short version:

1. Treat the winner probability as a measured estimate, not a guarantee.
2. Read confidence together with the data-quality badges.
3. Compare a model probability with the market only when both describe the same outcome.
4. A fight's probability of ending by decision is not the same as its probability of going over a particular rounds line.
5. Skip a bet when the available evidence does not support a clean comparison.

---

## 1. The prediction shown on a fight card

### Winner probability

The main percentage beside the selected fighter is FightIQ's estimated probability that the fighter wins. The production winner model is a calibrated logistic-regression pipeline trained on differences between two fighters' pre-fight feature snapshots.

Example:

> **Alex Fighter - 64%**

FightIQ is estimating a 64% chance that Alex Fighter wins under the information represented in the model. It is not saying that Alex wins 64% of the rounds, wins by 64 points, or is a certain pick.

The displayed pick is normally the fighter whose probability is above 50%. A 51% pick is nearly a coin flip; a 75% pick is a substantially stronger lean.

### Current held-out evidence

The checked-in calibrated winner-model artifact reports the following held-out metrics:

| Metric | Current artifact | Plain-language interpretation |
|---|---:|---|
| Accuracy | 63.15% | About 63 of every 100 held-out outcomes were classified correctly. |
| ROC AUC | 0.674 | The model ranks winners above losers better than chance, but not perfectly. |
| Log loss | 0.649 | Measures the quality of the full probability distribution and penalizes confident errors. Lower is better. |
| Brier score | 0.228 | Mean squared probability error. Lower is better. |

The artifact's confidence-bucket table contains **3,436 oriented test rows representing 1,718 unique fights**. FightIQ mirrors each fight so that both fighter orientations are represented. Calling all 3,436 rows separate fights would double-count the test sample.

### How to read confidence bands

The current artifact reports these calibrated logistic-regression buckets:

| Displayed probability band | Oriented rows | Observed accuracy | Average predicted confidence |
|---|---:|---:|---:|
| 50% to under 55% | 874 | 53.1% | 52.5% |
| 55% to under 60% | 850 | 62.8% | 57.4% |
| 60% to under 65% | 642 | 63.9% | 62.4% |
| 65% to under 70% | 510 | 65.9% | 67.4% |
| 70% to under 75% | 298 | 71.8% | 72.2% |
| 75% to under 80% | 156 | 85.9% | 77.3% |
| 80% and above | 106 | 73.6% | 84.6% |

These are diagnostics, not promises. The highest-confidence bucket is small and overconfident in this split. That is a reason to cap enthusiasm for extreme percentages and to monitor calibration prospectively.

Practical reading:

- **50% to 55%:** essentially a toss-up.
- **55% to 60%:** a modest lean.
- **60% to 70%:** a meaningful lean, subject to data quality and matchup context.
- **70% to 80%:** a strong statistical lean, but still vulnerable to missing context.
- **Above 80%:** rare. Treat as high model confidence, not certainty; the held-out sample is limited and currently overconfident at the top.

---

## 2. Data-quality badges matter

FightIQ attaches warning and context badges to help explain when a clean-looking probability rests on thin or unusual data. These badges should change how much trust you place in the number.

Common examples include:

| Badge or condition | What it signals | How to react |
|---|---|---|
| High confidence | The probability is far from 50%. | Check whether the supporting data are also strong. |
| Very close / low confidence | The probability is near 50%. | Treat the pick as fragile. |
| Limited data | One or both fighter snapshots are incomplete. | Reduce confidence and investigate manually. |
| Low UFC sample | A fighter has few UFC observations. | Expect wider uncertainty than the headline percentage shows. |
| Weight-class move | Historical performance may not transfer cleanly to the new division. | Review size, pace, and opponent-quality context. |
| Market agrees | The model pick and market favorite point to the same fighter. | Agreement is context, not independent proof. |
| Market disagreement | The model and market favor different fighters. | Verify identity, odds freshness, injuries, replacement status, and matchup information. |
| Clean data context | No major automated data-quality warning was triggered. | Still review normal MMA uncertainty and late-breaking news. |

The absence of a warning is not proof that the data are complete. Some important factors - injuries, illness, short notice, camp changes, difficult weight cuts, or tactical changes - may not exist in the structured data.

---

## 3. Model probability versus market probability

American odds can be converted into implied probabilities. A bookmaker's two sides normally include margin, so FightIQ removes the two-sided overround before displaying a market comparison.

Example:

| Source | Fighter A | Fighter B |
|---|---:|---:|
| FightIQ winner model | 61% | 39% |
| De-vigged market | 55% | 45% |

The model-versus-market difference for Fighter A is +6 percentage points. That is a **model edge estimate**, not an expected return and not a guaranteed pricing error.

Before treating a difference as actionable, verify:

- The market quote is fresh.
- The odds map to the correct fighters.
- The bout has not changed opponent, division, or round count.
- The model data snapshot predates the fight and has not silently used post-fight information.
- The model and market describe the same outcome and same line.
- The difference is large enough to survive model error, market movement, and bookmaker limits.

### Why disagreement can happen

The model can disagree with the market because it found a pattern the market underweights. It can also disagree because the model is missing information, the fighter identity mapping is wrong, or the odds are stale. The UI cannot determine which explanation is correct by itself.

Use disagreement as a research trigger, not as an automatic bet signal.

---

## 4. Reading the fight-duration section

This is the most important semantic distinction in the current UI.

### Market total

A market total is tied to a specific rounds line, for example:

> Over 2.5 rounds / Under 2.5 rounds

When FightIQ has both sides of that market, it can show de-vigged market probabilities for **Over 2.5** and **Under 2.5**. Those probabilities apply only to that line.

FightIQ's odds aggregator selects the most common available line and averages only bookmaker quotes at that same line. It does not mix Over 1.5 with Over 2.5.

### Decision probability

The existing method model can estimate:

> P(Decision)

That is the probability that the official method class is Decision rather than KO/TKO or Submission. It is useful context, but it is not a line-specific total prediction.

For a three-round fight:

- A decision usually implies Over 2.5.
- Over 2.5 can also win when a finish occurs late in round three.

For a five-round fight, P(Decision) is even less comparable with Over 2.5 or Over 3.5 because many non-decision outcomes can occur after those lines have already gone over.

Therefore:

> **P(Decision) must not be labeled or interpreted as P(Over X rounds).**

### Current UI behavior

The improved Future Cards duration panel keeps three concepts visually separate:

1. **Market total:** the line-specific de-vigged Over and Under percentages, when available.
2. **Duration model:** reserved for a future line-specific model prediction.
3. **Decision context:** the existing P(Decision), labeled as contextual and not used to calculate a model edge on the rounds market.

If no dedicated line-specific duration model is present, the panel says so. It does not manufacture a model-over percentage from P(Decision).

### Proposed API contract for a future duration model

The UI can consume a future response shaped like this:

```json
{
  "duration_prediction": {
    "line": 2.5,
    "over_probability": 0.58,
    "under_probability": 0.42,
    "model_version": "duration-1.0.0"
  }
}
```

The UI compares that prediction with the market only when the model's `line` exactly matches the market's `rounds_line`. A line mismatch produces a warning and no edge calculation.

This is proposed backend behavior. At the evidence snapshot, the repository does **not** contain a trained, validated, line-specific duration model.

### What an honest duration comparison looks like

Example with matching lines:

| Value | Over 2.5 | Under 2.5 |
|---|---:|---:|
| Duration model | 58% | 42% |
| De-vigged market | 54% | 46% |
| Model minus market | +4 points | -4 points |

Example with mismatched lines:

- Market: Over/Under 1.5
- Model: Over/Under 2.5

Correct behavior: show both lines separately if useful, mark the mismatch, and do not compute an edge.

---

## 5. A disciplined card-reading workflow

Use this sequence for every fight.

### Step 1: Confirm the bout

Check the two fighter identities, division, scheduled round count, event date, and bout status. Replacement opponents and late cancellations are common sources of stale projections.

### Step 2: Read the winner probability

Ask whether the model presents a coin flip, modest lean, meaningful lean, or strong lean. Do not round a 51% estimate into conviction.

### Step 3: Read every data badge

Limited data, low UFC sample, or a weight-class move should reduce trust. Multiple warnings compound rather than cancel one another.

### Step 4: Compare with the moneyline market

Use de-vigged probabilities and the correct fighter mapping. Treat a model-market gap as a hypothesis to investigate.

### Step 5: Read duration evidence separately

Identify the exact market line. Do not compare it with P(Decision). Use a model-market duration edge only if a dedicated duration prediction exists for the identical line.

### Step 6: Check information the model may not know

Review credible reports about injuries, replacement timing, weight cuts, illness, and camp changes. These are not reliably represented in the current structured feature set.

### Step 7: Decide whether the fight is a pass

A pass is a valid result. FightIQ is an analytical aid, not a requirement to make a pick or wager on every bout.

---

## 6. What FightIQ currently models

### Winner model

Current behavior:

- Learns from mirrored fighter-difference rows.
- Uses a calibrated logistic-regression classifier in production.
- Consumes the checked feature schema and categorical weight class.
- Outputs one winner probability per orientation, reconciled for display.

### Method model

Current behavior:

- Predicts broad official method classes: Decision, KO/TKO, or Submission.
- Supplies the decision probability used as contextual fight-duration information.
- Does not predict Over/Under at a bookmaker's rounds line.

### Market inputs

Current behavior:

- Supports moneyline and total-market fields.
- Normalizes two-sided implied probabilities when both sides are available.
- Tracks source and bookmaker coverage.

Evidence gap at the snapshot:

- The audited local odds artifact contained zero usable total quotes across 58 upcoming-fight rows, despite schema and UI support for totals.
- Availability therefore depends on the external odds feed, event coverage, matching, and refresh reliability.

---

## 7. Known limitations

### The data are historical

Past UFC performance does not encode every current condition. Training changes, health, motivation, tactical plans, and unreported injuries can matter.

### New and returning fighters are harder

A low-UFC-sample fighter or a fighter returning after a long gap may have a misleadingly precise percentage. The current UI uses warning badges, but the probability itself is still a point estimate.

### Calibration is not uniform

Aggregate calibration can look acceptable while specific divisions, eras, debutants, or confidence bands behave differently. The upper bucket in the current held-out split is an explicit example.

### Markets and model snapshots move

Odds can change after the card was refreshed. A model-market edge without timestamps can disappear or reverse.

### A local test split is not live proof

Held-out historical performance is necessary but does not replace prospective monitoring on predictions frozen before events. Live drift, feed failures, and changing fighter populations require separate checks.

### Fight duration is not yet modeled at the line level

The current method model answers a related question, not the market's exact one. A dedicated model must be trained and validated before the UI can make a defensible model-versus-market duration comparison.

---

## 8. Glossary

| Term | Meaning |
|---|---|
| Accuracy | Fraction of classified outcomes predicted correctly at a chosen threshold. |
| Brier score | Mean squared error of predicted probabilities; lower is better. |
| Calibration | Agreement between predicted probabilities and observed frequencies. |
| De-vigged probability | Implied market probability after normalizing out the two-sided bookmaker margin. |
| Decision probability | Estimated probability that the official result method is Decision. |
| Duration model | A proposed model that predicts Over/Under for a specific rounds line. |
| Edge | Difference, in percentage points, between model and market probabilities for the same outcome. |
| Log loss | Probability-scoring rule that penalizes confident mistakes strongly; lower is better. |
| Mirrored row | One orientation of a fight used for symmetry; each unique fight produces two oriented rows. |
| Moneyline | Market on which fighter wins. |
| Overround / vig | The amount by which raw two-sided implied probabilities sum above 100%. |
| P(Decision) | Probability of a Decision method class, not probability of going over a rounds line. |
| Rounds line | A duration threshold such as 1.5, 2.5, or 4.5 rounds. |
| ROC AUC | Ranking metric: how often a winner receives a higher score than a loser across thresholds. |

---

## Before acting on a prediction

- [ ] Confirm the fighters, division, scheduled rounds, date, and bout status.
- [ ] Read the probability as a range of confidence, not a guarantee.
- [ ] Review all limited-data and context badges.
- [ ] Verify odds freshness and fighter mapping.
- [ ] Compare model and market only for the same outcome.
- [ ] For totals, confirm the exact rounds line.
- [ ] Never substitute P(Decision) for P(Over X).
- [ ] Do not calculate a duration edge when the model and market lines differ.
- [ ] Check credible late-breaking context the model may not contain.
- [ ] Be willing to pass.

---

## Implementation note

This guide is intentionally standalone. When the model, feature schema, market feed, duration contract, or UI semantics change, update this document in the same pull request and regenerate `READING_THE_PREDICTIONS.pdf`.
