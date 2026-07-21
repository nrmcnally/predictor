# FightIQ Model Research and Evidence-Based Improvement Roadmap

## A standalone review of the `threejs` prediction system

**Status:** Current implementation audit, experimental duration baseline, and proposed research program
**Repository:** `C:\Users\nrmcn\predictor\threejs`
**Evidence snapshot:** July 21, 2026, current `threejs` implementation after duration release `60d9c84` plus the audited evaluation-hardening working set
**Model artifact:** logistic-regression winner model, version 1.3; frozen evaluation plus full-history production refit
**Audience:** developers, model reviewers, and product owners

---

## Abstract

FightIQ is a UFC analytics application whose production prediction engine estimates fight winners from strictly pre-fight differences between two fighter snapshots. The selected recipe is uncalibrated logistic regression. Its frozen candidate report shows 63.55% accuracy, 0.676 ROC AUC, 0.649 log loss, and 0.228 Brier score on a chronological held-out set of 1,720 unique fights. The training table contains 17,198 mirrored rows representing 8,599 unique fights. After those metrics are frozen, model 1.3 refits the locked recipe on all eligible history for serving; that full-history artifact is never scored on the now-seen holdout.

This report audits the implemented data, feature, modeling, evaluation, and market-comparison paths; separates current behavior from proposals; and ranks improvements by local evidence. The most important correction to the earlier research direction is that FightIQ's own controlled experiments do **not** support shipping the existing style-interaction or cardio feature families. Explicit style interactions were neutral to negative across logistic regression, histogram gradient boosting, and XGBoost. Cardio differences also reduced held-out accuracy. Those components should remain experimental until a new, leakage-safe hypothesis wins the same walk-forward gate.

The highest-value near-term work is now operational and evaluative: freeze the duration baseline, collect prospective exact-line results, monitor refresh/totals health, improve artifact provenance, and measure winner reliability by data-depth cohort. FightIQ now has an experimental discrete-time survival model that estimates P(Over 0.5/1.5/2.5/3.5/4.5 where supported). The separate method model still estimates P(Decision), and the Future Cards UI correctly preserves that distinction.

---

## 1. Research questions and evidence policy

This review asks five practical questions:

1. What prediction system is actually running?
2. Which data and features feed it, and where can leakage or identity errors enter?
3. Which proposed improvements have already been tested locally?
4. What evidence would justify a change to the production model?
5. How should FightIQ support a line-specific fight-duration product safely?

Claims are classified as follows:

| Label | Meaning |
|---|---|
| Current | Directly supported by checked-in code, data, tests, or model artifacts. |
| Experimental | Code or results exist, but the component is not part of the production path. |
| Proposed | Recommended future work with no claim that it is implemented. |
| Legacy or stale | Documentation or code conflicts with the active path or newer local evidence. |
| Uncertain | Evidence is incomplete or contradictory and should not be presented as fact. |

Repository metrics are reported as point-in-time evidence, not as universal performance promises. External research is used to choose experiments, not to override FightIQ's own held-out results.

---

## 2. System under study

### 2.1 Product and runtime context

FightIQ combines:

- a React/Vite frontend;
- a Python backend API and service layer;
- UFCStats ingestion and preprocessing;
- SQLite and exported JSON/CSV artifacts;
- serialized winner and method models;
- an odds integration for head-to-head and rounds-total markets;
- scheduled refresh, evaluation, and administrative workflows.

The prediction path can be summarized as:

```text
UFCStats and profiles
        |
        v
chronological pre-fight snapshots
        |
        v
fighter A minus fighter B feature row
        |
        v
selected logistic winner recipe
        |
        v
winner probability + warnings + market comparison
        |
        v
Future Cards and evaluation interfaces
```

Odds are a parallel input. They are not training features in the current production winner model. The UI compares model and de-vigged market probabilities after prediction.

### 2.2 Point-in-time data inventory

The audited local artifacts contained:

| Artifact or table | Audited size | Interpretation |
|---|---:|---|
| Training matchup rows | 17,198 | Two orientations for each usable historical fight. |
| Unique usable training fights | 8,599 | Effective labeled sample before train/test splitting. |
| Held-out oriented test rows | 3,440 | Two rows per test fight. |
| Held-out unique fights | 1,720 | Correct event-level test count. |
| Current fighter feature rows | 2,694 | Latest feature snapshot per fighter. |
| Current fighter columns | 134 | Identifiers, metadata, and engineered values. |
| Winner numeric features | Approximately 126 | Checked feature list consumed by the winner pipeline. |
| Method numeric features | 496 plus weight class | Wider orientation-invariant method feature representation. |

The database and exported flat files were not perfectly synchronized in the snapshot. For example, the audit found 8,772 historical database fight rows versus 8,758 exported CSV rows, and different upcoming-event/fight counts across database and CSV views. These differences may be explainable by filtering or refresh timing, but the repository did not provide one automatically generated reconciliation report. Until such a report exists, count differences should be treated as an operational risk.

### 2.3 Provenance warning

The current winner artifacts record model version 1.3 with distinct training protocols and hashes: `683f0e4d08` for the chronological candidate evaluation and `d318130478` for the full-history production refit. Both record commit `60d9c84` and `git_dirty: true`. These hashes prevent evaluation and production roles from being conflated, but a dirty training worktree still weakens exact reproducibility because uncommitted code or data could have influenced the artifacts.

Recommended rule: release artifacts must be trained from a clean commit, record dataset and feature-schema hashes, and fail release validation if provenance is incomplete.

---

## 3. Data and feature construction

### 3.1 Historical sources

Current source evidence centers on UFCStats event, fight, fighter-profile, and round-stat data. The system builds historical records, physical measurements, striking and grappling rates, time-normalized statistics, recent form, opponent adjustment, and rating features.

Odds are fetched separately for product display and prospective evaluation. Their coverage depends on the external provider, event matching, market availability, and refresh success.

### 3.2 Leakage control

The feature builder walks fights chronologically and constructs a fighter's pre-fight state from prior bouts. This is the correct high-level design for avoiding post-fight contamination.

The main leakage and integrity risks are nevertheless structural:

- a future row accidentally joining to a current rather than as-of snapshot;
- corrections to a fighter identity merging two people or splitting one career;
- mirrored orientations crossing folds independently;
- preprocessing, calibration, or feature selection fitted outside the training fold;
- exported artifacts and database state coming from different refreshes;
- outcome-derived columns surviving into an input schema under an innocent name.

Validation must group both orientations of the same fight and preserve chronology. Every learned transformation must fit inside the training partition.

### 3.3 Mirroring and symmetry

FightIQ creates two oriented rows per fight: A versus B and B versus A. This encourages the winner probability to respect fighter-order symmetry.

Consequences:

- Row counts are not fight counts.
- Both orientations must stay in the same train, validation, or test partition.
- Event-level metrics should deduplicate by fight.
- Symmetry tests should verify that swapping fighters approximately transforms `p` into `1 - p`.

The frozen evaluation artifact's 3,440 test rows represent 1,720 unique fights. Reports and UI documentation must use the unique-fight count when describing sample size. The separately labeled production artifact is refit on all 8,599 fights and must not be scored on that now-seen holdout.

### 3.4 Feature families

Implemented feature families include:

| Family | Examples | Primary risk |
|---|---|---|
| Record and experience | fights, wins, losses, win rate, UFC sample | Sparse careers and era differences. |
| Physical | age, height, reach, stance | Missing-value handling and stale profiles. |
| Pace and volume | strikes, takedowns, attempts per time | Opponent and fight-duration confounding. |
| Efficiency and defense | accuracy, absorption, takedown defense | Ratio instability at small sample sizes. |
| Recent form | recent windows and recency-weighted values | High variance and arbitrary window choice. |
| Opponent adjustment | performance relative to prior opponent baselines | Complex as-of joins and error propagation. |
| Ratings | Elo, peak, trend, strength-of-schedule summaries | Hyperparameter sensitivity and cold starts. |
| Context | weight class, scheduled rounds, event role | Schema drift and limited historical coverage. |
| Composite style/path | hand-built offensive, defensive, or vulnerability summaries | Hidden assumptions and correlated inputs. |

The production winner pipeline consumes fighter-difference values plus categorical weight class. The method model uses orientation-invariant combinations such as absolute difference, mean, minimum, and maximum.

### 3.5 Data-quality indicators

The product exposes warning badges for conditions such as low UFC sample, limited data, and weight-class changes. This is a good user-facing safeguard, but it does not quantify predictive uncertainty.

Proposed enhancement: define cohort-level reliability reports for debutants, one-fight samples, long layoffs, weight-class movers, replacement bouts, women's divisions, five-round bouts, and eras. Display ranges or reliability labels only after those cohorts have enough prospective evidence.

---

## 4. Current models and results

### 4.1 Winner model

Current production behavior:

- base estimator: logistic regression;
- probability calibration: none for the selected recipe; calibrated candidates remain evaluated alternatives;
- inputs: checked numeric fighter differences plus weight class;
- evaluation: chronological held-out fights;
- output: winner probability from the selected logistic recipe.

Checked artifact results:

| Metric | Value |
|---|---:|
| Unique held-out fights | 1,720 |
| Accuracy | 0.6355 |
| ROC AUC | 0.6756 |
| Log loss | 0.6492 |
| Brier score | 0.2276 |

These values indicate a useful but modest signal. They do not imply profitability, and they do not establish that performance is identical on future cards.

### 4.2 Calibration by confidence

The frozen report is reasonably close to observed outcomes through much of the middle range, but it is underconfident from 0.55-0.65 and overconfident in the highest band:

| Confidence band | Unique fights | Accuracy | Mean confidence | Gap: accuracy minus confidence |
|---|---:|---:|---:|---:|
| 0.50 to under 0.55 | 359 | 0.529 | 0.525 | +0.004 |
| 0.55 to under 0.60 | 360 | 0.606 | 0.575 | +0.031 |
| 0.60 to under 0.65 | 306 | 0.637 | 0.623 | +0.014 |
| 0.65 to under 0.70 | 263 | 0.658 | 0.675 | -0.017 |
| 0.70 and above | 432 | 0.734 | 0.772 | -0.038 |

These fight-deduplicated bucket diagnostics are still exploratory, and subgroup intervals remain important. Prospective calibration should be scored on one frozen prediction per fight.

### 4.3 Method model

The method model predicts broad outcome classes such as Decision, KO/TKO, and Submission. Its Decision class probability is exposed as contextual information on future cards.

Critical semantic rule:

> P(Decision) is not P(Over X rounds).

A decision normally survives late enough to clear some totals, but a late finish can also go over, and five-round fights make the difference larger. The method model must not be used to calculate a line-specific over/under edge.

---

## 5. What local experiments already say

Local controlled results should outrank attractive general claims from external studies.

### 5.1 Explicit style-interaction terms

**Status: Experimental, rejected by current evidence.**

The repository contains a style-interaction module and roadmap text that once promoted wiring it into training. Newer local A/B results tested six explicit interaction terms across three model families:

| Model family | Accuracy change | Brier direction | Decision |
|---|---:|---|---|
| Logistic regression | -0.10 percentage points | Flat to worse | Revert |
| Histogram gradient boosting | -0.12 percentage points | Flat to worse | Revert |
| XGBoost | -0.33 percentage points | Flat to worse | Revert |

Conclusion: do not ship the existing interaction features. Their presence in code is not evidence of benefit. Any stale roadmap item calling them "free alpha" conflicts with the experiment record and should be corrected.

Potential explanation: many interaction ideas may already be captured by correlated differential and composite features; explicit products can add variance in a small dataset.

### 5.2 Cardio differences

**Status: Experimental, excluded from the winner model.**

The walk-forward test reported approximately -0.14 percentage points of accuracy and slightly worse Brier/log-loss behavior. Round-level data remain valuable, but the tested cardio summary did not earn production inclusion.

Conclusion: retain the raw/as-of round evidence, redesign the hypothesis if warranted, and require a new ablation. Do not re-enable the old feature family by assumption.

### 5.3 Tree-model bake-off

**Status: Evaluated, not promoted.**

The documented bake-off did not find a tree or ensemble combination that beat the logistic baseline on the production gate. This is plausible in a medium-width, small-sample tabular problem with many smooth, correlated inputs. Grinsztajn, Oyallon, and Varoquaux show why tree-based models are often strong on tabular data, but that is a reason to test them carefully, not a reason to replace a locally superior baseline [2].

Conclusion: keep logistic regression as the champion until a challenger improves probability metrics across repeated chronological splits and key cohorts.

### 5.4 Class rebalancing

**Status: Not recommended for probability quality without specific evidence.**

The target is naturally close to balanced after orientation, and rebalancing can damage probability calibration even when it changes classification sensitivity. van den Goorbergh and colleagues document this risk for probability models [4].

Conclusion: optimize calibrated probability scores directly. If weights are tested, recalibrate and evaluate on the untouched natural distribution.

---

## 6. Market evidence and evaluation

### 6.1 Current market use

FightIQ converts American odds to implied probabilities and removes the two-sided overround by normalization when both sides are available. The application can then compare the winner model with the market.

The difference between model and market is descriptive:

```text
model edge = model probability - de-vigged market probability
```

It is not expected return. Realized return also depends on the offered price, line movement, stake sizing, limits, and model error.

### 6.2 Coverage limitations

The audited local database still contains only a small odds history. The latest append-only totals snapshot contains 32 per-book quotes across 8 fights, 4 bookmakers, and lines 1.5, 2.5, and 3.5; many later fights correctly remain in a no-market state. This establishes that the ingestion path works, but it is not enough coverage for strong market-performance conclusions.

Before market-relative conclusions are trusted, FightIQ needs:

- continued verification across restarts and offline intervals; the current Interactive task catches up after the user next logs on but does not run while that account is signed out;
- monitoring of the implemented heartbeat, freshness timestamps, provider status, and quota;
- robust fighter/event matching diagnostics;
- opening, snapshot, and closing quotes with source counts;
- one immutable pre-event prediction record;
- coverage and failure-rate dashboards.

### 6.3 Evaluation hierarchy

Recommended scoreboard:

1. **Primary model quality:** event-level log loss and Brier score on frozen prospective predictions.
2. **Secondary discrimination:** ROC AUC and accuracy, with thresholds declared in advance.
3. **Calibration:** reliability curves, expected calibration error with bin sensitivity reported, and cohort tables.
4. **Market comparison:** log loss/Brier versus a same-time de-vigged market quote on matched cases.
5. **Pricing process:** closing-line value, but only when line snapshots and timestamps are reliable.
6. **Realized return:** an operational outcome reported with uncertainty, not a model-selection objective on a small sample.

The app's historical held-out test and prospective market evaluation answer different questions. Do not merge them into one headline number.

### 6.4 De-vigging research

Plain normalization is transparent and defensible for a two-sided first version. Alternative de-vig methods, including power and Shin-style approaches, can be tested once enough matched opening/closing data exist. The choice should be selected by out-of-sample forecast quality, especially for higher-margin prop markets, rather than adopted because it is more sophisticated.

---

## 7. Fight-duration research program

### 7.1 Product question

The product needs to answer a precise market question:

> What is P(Over L rounds) for this fight, where L is the market line?

That is a different target from winner and method classification.

### 7.2 Current implementation boundary

Current:

- the odds schema supports `rounds_line`, Over odds, Under odds, and normalized probabilities;
- aggregation keeps quotes at the selected same line while `totals_odds_snapshots` retains every per-book line and price append-only;
- `duration_model.joblib` is an experimental discrete-time half-round survival artifact, version `duration-survival-0.2.0`, feature schema `duration-survival-features-2`;
- market odds and the bookmaker-selected line are not model inputs; the fitted curve is queried at the line after prediction;
- the broad method model still exposes P(Decision) as separately labeled context;
- Future Cards shows a compact exact-line prediction when available and the full curve in the expanded breakdown even before a market total is posted;
- frozen exact-line snapshots are graded against completed results by `duration_evaluation_service.py`, and the incremental pipeline runs this grader immediately after result ingestion.

Implemented UI safeguard:

- market totals are displayed separately from Decision probability;
- no model edge is claimed when a duration prediction is absent;
- a future prediction is compared only when its line exactly matches the market line;
- a mismatch is labeled and produces no edge.

### 7.3 Implemented target and settlement representation

`duration_settlement.py` resolves a canonical elapsed fight time. For a finish:

```text
elapsed_rounds = completed_rounds + elapsed_seconds_in_current_round / round_length_seconds
```

For a decision, use the scheduled duration. Carefully encode unusual round lengths, technical decisions, overturned results, no contests, and missing time.

For each valid line `L`:

```text
over_L = 1 if elapsed_rounds > L else 0
under_L = 1 - over_L
```

The same settlement service is used by training/evaluation tests and prospective grading. Decisions resolve to the scheduled limit; draws, no contests, overturned results, disqualifications, unsupported schedules, invalid clocks, and impossible finish times are excluded with reason codes. Half-round query lines avoid normal equality pushes, while the settlement function still defines the equality boundary explicitly.

### 7.4 Modeling options

Ranked from simplest to most ambitious:

| Option | Description | Advantages | Risks |
|---|---|---|---|
| Line-specific logistic baseline | Add the line and scheduled rounds to a leakage-safe fight feature row and predict Over. | Easy to audit and calibrate. | Separate line populations may be small. |
| Discrete-time hazard model | Estimate finish probability by interval and derive survival past any line. | One coherent model can answer multiple lines. | More complex labels, censoring, and calibration. |
| Method-time joint model | Jointly model finish type and time. | Rich product outputs. | High variance and harder validation. |
| Market-anchored residual model | Predict correction to a de-vigged market probability. | Can focus on disagreement. | Cannot operate without market; leakage and timestamp discipline are critical. |

Implemented experimental baseline: a regularized discrete-time hazard model at half-round intervals. This choice produces a monotone survival curve by construction and operates before a house line exists. It is not production-approved; a simpler line-aware classifier remains a useful challenger under identical chronological folds.

### 7.5 Duration features to test

Candidate features must be computed strictly pre-fight:

- scheduled rounds and total line;
- each fighter's prior finish and decision rates with shrinkage;
- prior time-to-finish and time-survived summaries;
- pace, absorption, knockdown, takedown, submission-attempt, and control rates;
- opponent-adjusted finishing and survival measures;
- round-specific pace and fade summaries redesigned from raw round data;
- UFC sample size, layoffs, age, and weight-class move indicators;
- division and gender cohorts where coverage supports them;
- matchup differences and symmetric summaries selected inside validation.

Do not assume the rejected winner-model cardio or interaction transforms will help duration. Duration has a different target, so they may be retested, but only under a new preregistered ablation.

### 7.6 Validation design

Current historical gate and remaining promotion requirements:

1. One row per fight-line observation, grouped by fight and event.
2. Strict chronological train/validation/test splits.
3. All preprocessing and feature selection fitted inside each training fold.
4. Brier, log loss, calibration slope/intercept, and reliability by line.
5. Cohort reports for 1.5, 2.5, 3.5, and 4.5 where sample size permits.
6. Comparison against a constant base rate, a simple historical-rate baseline, and same-time de-vigged market.
7. Bootstrap confidence intervals at the unique-fight or event level.
8. Prospective shadow period before any betting or recommendation language is enabled.

The installed historical artifact uses a chronological 80/20 unique-fight split before interval expansion: 6,816 training fights and 1,709 test fights. Across 5,443 exact-line test observations it reports 72.86% accuracy, 0.1754 Brier score, 0.5229 log loss, and 0.7514 ROC AUC, versus 69.59% accuracy and 0.1912 Brier for the same-line training base-rate baseline. There were zero monotonicity violations by construction. These are historical experimental results, not proof of live market value.

### 7.7 Current backend contract

```json
{
  "duration_prediction": {
    "status": "ready",
    "line": 2.5,
    "over_probability": 0.58,
    "under_probability": 0.42,
    "curve": [
      {"line": 0.5, "over_probability": 0.89, "under_probability": 0.11},
      {"line": 1.5, "over_probability": 0.71, "under_probability": 0.29},
      {"line": 2.5, "over_probability": 0.58, "under_probability": 0.42}
    ],
    "model_version": "duration-survival-0.2.0",
    "feature_schema_version": "duration-survival-features-2",
    "promotion_status": "experimental",
    "market_inputs_used": false,
    "market_line_role": "query_only",
    "generated_at": "2026-07-13T18:00:00Z"
  }
}
```

Contract safeguards:

- `line` is required and numeric;
- probabilities are finite, in `[0,1]`, and sum to 1 within tolerance;
- model and feature-schema versions are required;
- stale or line-mismatched predictions are not compared with the market;
- a missing prediction is a normal, explicitly labeled state.

---

## 8. Research opportunities ranked by evidence

### Tier 1: measurement and reproducibility

These changes are more likely to prevent false progress than a new algorithm.

1. **Clean artifact provenance.** Require clean-commit training, dataset hash, feature-schema hash, dependency lock hash, seed, split definition, and command.
2. **Repeated chronological evaluation.** Winner evaluation now includes a frozen eight-fold expanding-window report; extend the same discipline to method/duration challengers and cohort comparisons.
3. **Frozen prospective registry.** Winner and duration snapshots retain prediction/model/market timestamps and later outcomes; harden database immutability and lifecycle tests.
4. **Cohort calibration monitoring.** Surface where headline probabilities are unreliable.
5. **Data reconciliation checks.** Compare database, CSV, JSON, and serialized artifact counts during every refresh.

Expected effect: higher confidence that measured improvements are real, even if headline accuracy does not immediately change.

### Tier 2: strong model experiments

1. **Regularization and stability analysis.** Examine coefficient stability across chronological folds; remove features only within nested evaluation. Stability-selection concepts can guide this work, but the production gate must remain probability performance.
2. **Calibration challengers.** Compare sigmoid, isotonic, and beta calibration on untouched chronological folds. Beta calibration is a well-motivated challenger because standard logistic calibration can be too restrictive [3].
3. **Rating uncertainty.** Test Glicko-2-style rating deviation or another time-aware uncertainty signal against current Elo features. Treat it as an ablation, not an automatic replacement.
4. **Raw round-sequence hypotheses.** Redesign pace/fade features with shrinkage and missingness indicators; test separately for winner and duration targets.
5. **Sparse-cohort handling.** Compare hierarchical or partial-pooling representations for debutants and low-sample fighters.

### Tier 3: new data, subject to rights and reliability

1. **Historical odds snapshots.** Acquire a permitted, timestamped source for opening and closing markets. Do not build a critical pipeline on scraping until terms and reliability are reviewed.
2. **Judge scorecards.** Explore permitted scorecard data for round-level dominance and close-decision labels. Identity, event, and round joins require audit.
3. **Pre-UFC records.** A licensed or permitted source could reduce debut blind spots. Competition-level normalization is the central modeling challenge.
4. **Operational annotations.** Replacement timing, layoffs, and weight-class moves can be high value if provenance, timestamp, and review workflow are explicit.

### Research ideas not currently justified

- Shipping existing style interactions because a paper found interactions useful elsewhere.
- Re-enabling cardio differences despite a losing local test.
- Replacing the logistic champion with a more complex model that wins only accuracy or one split.
- Using market odds as both a training feature and evaluation benchmark without time-aligned snapshots.
- Treating P(Decision) as a totals model.
- Reporting mirrored row counts as independent fights.

---

## 9. Experiment protocol

Every model change should have a short experiment card:

| Field | Required content |
|---|---|
| Hypothesis | Why the change should improve a named metric or cohort. |
| Target | Winner, method, exact-line duration, or calibration. |
| Data cutoff | Latest event allowed in training. |
| Unit of analysis | Unique fight, fight-line, or event. |
| Feature provenance | Exact schema and as-of guarantees. |
| Baseline | Current champion artifact and simple reference model. |
| Splits | Predeclared chronological windows. |
| Primary metric | Normally log loss or Brier score. |
| Secondary metrics | Accuracy, AUC, calibration, and cohort metrics. |
| Decision rule | Minimum improvement and no-regression conditions. |
| Risks | Leakage, coverage, identity, market timestamp, and multiple testing. |
| Reproduction command | One command from a clean checkout. |

Recommended promotion rule:

- improve the primary probability metric across most chronological folds;
- show no material calibration regression;
- preserve fighter-order symmetry;
- avoid serious regression in sparse-data cohorts;
- pass schema, leakage, and artifact-provenance checks;
- complete a prospective shadow period for market-facing outputs.

Do not promote based only on a single accuracy-point increase. Because the dataset is small and many experiments may be tried, selection bias can create apparent winners.

---

## 10. Statistical and product safeguards

### 10.1 Uncertainty

Report confidence intervals or bootstrap distributions for metric differences. Resample at the unique-fight or event level, not the mirrored-row level.

### 10.2 Calibration

Calibration is part of the product contract because percentages are shown directly to users. Evaluate slope, intercept, reliability curves, and proper scoring rules. Kull, Silva Filho, and Flach provide the beta-calibration framework and show why common sigmoid assumptions can fail [3].

### 10.3 Missingness

Missing physical or fight-history values can encode meaningful cohort differences. Imputation and missingness indicators must be fitted inside training folds. Monitor missingness by source and refresh.

### 10.4 Identity integrity

One incorrect fighter merge can contaminate history, features, future matching, and odds evaluation. Maintain a canonical fighter ID, alias table, collision checks, and manual review queue. Never normalize names destructively without retaining the source value.

### 10.5 Market timestamps

Comparisons require a clearly defined information set. A prediction made Monday cannot be fairly compared with a closing line Friday unless the purpose is explicitly closing-line-value evaluation. UI edge displays should compare timestamps that a user can inspect.

### 10.6 Product language

Use:

- "model probability";
- "de-vigged market probability";
- "model minus market";
- "Decision probability";
- "no line-specific duration model available."

Avoid:

- "guaranteed" or "lock" for a model pick;
- "expected return" when only a probability gap is known;
- "model over" when the value is actually P(Decision);
- an edge calculation across different rounds lines.

---

## 11. Prioritized roadmap

### Quick wins: one to two weeks

| Priority | Work | Deliverable | Success check |
|---|---|---|---|
| Done | Correct UI duration semantics | Compact exact-line prediction plus expanded curve; P(Decision) remains context | Tests reject missing/mismatched lines and preserve curve-only state. |
| Done | Clean stale research claims | Documentation matches local A/B results | No guide recommends rejected interactions/cardio. |
| P0 | Artifact provenance gate | Training metadata and clean-worktree check | Release fails on dirty or incomplete provenance. |
| Done | Refresh/totals health foundation | Persisted refresh heartbeat, degraded-stage alerts, coverage/quota/snapshot indicators | Hosted Data Ops shows stale/failure state without reading logs. |
| Active | Prospective prediction freeze | Seven exact-line rows settled; six correct, all seven Over; automatic post-result grading | Evaluation reproduces the frozen prediction and reports zero uplift over the always-Over baseline. |
| P1 | Cohort report | Calibration and coverage by sample/context | Sparse cohorts are visible in review. |

### Medium term: two to eight weeks

| Priority | Work | Deliverable | Success check |
|---|---|---|---|
| Done | Duration dataset and settlement tests | Canonical elapsed-duration resolver and tested exclusions | Boundary fixtures and training/evaluation share semantics. |
| Experimental | Discrete-time survival baseline | Versioned `duration-survival-0.2.0` artifact and 80/20 report | Beats same-line base-rate proper scores historically; await live sample. |
| Active | Odds-history reliability | 32 append-only per-book quotes across 8 fights at snapshot | Continue daily capture; add closing-line and line-movement reporting. |
| Done (winner) | Repeated chronological model harness | Frozen eight-fold expanding-window winner report | Champion monitoring includes fold distribution and relative-to-Elo drift. Extend to other model families as they change. |
| P2 | Calibration bake-off | Sigmoid/isotonic/beta comparison | Challenger improves proper scores without cohort harm. |
| P2 | Rating uncertainty ablation | Glicko-2-style features versus Elo | Improvement survives nested chronological evaluation. |

### Long term: two to six months

| Priority | Work | Deliverable | Success check |
|---|---|---|---|
| Active | Prospective duration validation | At least 75-100 settled exact-line observations, including a useful five-round cohort | Calibration/proper scores and exclusions reviewed before promotion. |
| P2 | Permitted new data | Versioned scorecard or pre-UFC source | Coverage, rights, identity, and as-of checks pass. |
| P3 | Hierarchical sparse-fighter model | Uncertainty-aware cold-start predictions | Prospective low-sample cohort improves. |
| P3 | Market-residual shadow model | Time-aligned market correction | Adds value against same-time market out of sample. |

---

## 12. Risks and open questions

| Risk | Severity | Evidence | Recommended response |
|---|---|---|---|
| Stale roadmap promotes losing interaction features | High | Conflict with recorded three-model A/B | Remove promotion language; keep module experimental. |
| P(Decision) confused with P(Over) | High | Current method output is not line-specific | Enforce UI/API semantic separation. |
| Dirty artifact provenance | High | Winner metadata records `git_dirty: true` | Retrain release artifacts from a clean commit. |
| Odds and totals coverage is sparse | High | 32 per-book quotes cover 8 current fights; many cards have no posted total | Keep unavailable state, daily encrypted refresh, coverage/freshness alerts, and prospective capture. |
| Mirrored rows overstated as fights | Medium | 3,440 rows equal 1,720 fights in the frozen holdout | Standardize unique-fight reporting. |
| Database/export count drift | Medium | Point-in-time discrepancies found | Add reconciliation manifest. |
| High-confidence overcalibration | Medium | 77.2% mean confidence vs 73.4% accuracy across 432 held-out fights at 0.70+ | Monitor, compare calibration challengers, and show interval/sample size. |
| Multiple-experiment selection bias | Medium | Many plausible feature ideas, small dataset | Predeclare gates and use repeated chronological splits. |
| External data rights and stability | Medium | Proposed sources are not current contracts | Review terms, licensing, retention, and failure behavior. |
| Sparse/new fighter uncertainty | Medium | Low UFC sample is structurally common | Cohort calibration and uncertainty-aware models. |

Open questions:

1. What odds timestamp should the Future Cards edge represent: latest, first available, or a fixed pre-event window?
2. Which totals lines accumulate enough *prospective market* coverage for a meaningful model-versus-market comparison?
3. Should unusual promotions/round formats remain excluded or receive a separately versioned settlement contract?
4. The working review gate is 75-100 settled exact-line UFC observations plus adequate five-round coverage; should formal power analysis require more?
5. Should winner probabilities be clipped or conservatively transformed in the highest-confidence region until more evidence accumulates?

---

## 13. Recommended next experiment sequence

1. Freeze `duration-survival-0.2.0`; do not tune it after each event.
2. Run the encrypted daily odds/data refresh and watch the hosted heartbeat, quota, coverage, and stale-snapshot alerts.
3. Preserve exact-line predictions before events and let the incremental pipeline grade them after official results arrive.
4. Review after a predeclared 75-100 settled exact-line observations, with line and scheduled-round cohorts reported separately.
5. Compare Brier, log loss, calibration, accuracy, and same-time market probabilities; publish coverage and exclusions.
6. Keep Future Cards language neutral and the model experimental until the prospective gate passes.
7. In parallel, add winner reliability/abstention analysis for low-history and missing-data cohorts.
8. Use the frozen eight-fold winner report as the gate before choosing new features or algorithms; add cohort stability and abstention analysis on top of it.
9. Improve artifact provenance and atomic deployment generations.
10. Revisit feature families only through predeclared ablations.

This sequence prioritizes trustworthy measurement. It preserves a useful experimental over/under interface without pretending that seven same-side prospective results prove market value.

---

## 14. Limitations of this review

- The audit is a snapshot of a local checkout, not an independent reproduction from a clean machine.
- Counts can change after a refresh and some database/export differences may have legitimate filters.
- The frozen winner report includes one untouched holdout and an eight-fold expanding-window distribution, but it is not an independent external reproduction.
- External MMA modeling literature is limited and often uses different promotions, eras, targets, and leakage controls.
- Market claims are constrained by sparse local odds history and must remain provisional.
- The duration model is an experimental local baseline with one historical split and only seven settled prospective predictions; all seven selected Over, so the 6/7 result has no uplift over the always-Over baseline and is not independent reproduction.

---

## 15. References

1. Holmes, L., McHale, I. G., and Zychaluk, K. (2023). "A Markov chain model for forecasting results of mixed martial arts contests." *International Journal of Forecasting*, 39(2), 623-640. [RePEc record and DOI](https://ideas.repec.org/a/eee/intfor/v39y2023i2p623-640.html).
2. Grinsztajn, L., Oyallon, E., and Varoquaux, G. (2022). "Why do tree-based models still outperform deep learning on typical tabular data?" *NeurIPS 2022*. [Official proceedings](https://papers.nips.cc/paper_files/paper/2022/hash/0378c7692da36807bdec87ab043cdadc-Abstract-Datasets_and_Benchmarks.html).
3. Kull, M., Silva Filho, T. M., and Flach, P. (2017). "Beta calibration: a well-founded and easily implemented improvement on logistic calibration for binary classifiers." *AISTATS 2017*. [PMLR paper](https://proceedings.mlr.press/v54/kull17a.html).
4. van den Goorbergh, R., van Smeden, M., Timmerman, D., and Van Calster, B. (2022). "The harm of class imbalance corrections for risk prediction models: illustration and simulation using logistic regression." *Journal of the American Medical Informatics Association*. [DOI](https://doi.org/10.1093/jamia/ocac093).
5. Glickman, M. E. (2012). "Example of the Glicko-2 system." [Official Glicko paper](http://www.glicko.net/glicko/glicko2.pdf).

Repository evidence reviewed includes the model registry and metrics artifacts, training and feature-building code, `ROADMAP.md` experiment notes, odds service and schema code, future-card service/UI code, tests, SQLite/CSV/JSON datasets, and model metadata in `C:\Users\nrmcn\predictor\threejs`.

---

## Maintenance rule

This report is standalone and should change with the implementation. Any pull request that changes the winner or method target, feature ordering, calibration, duration contract, odds normalization, model artifact, evaluation split, or displayed prediction semantics must update this Markdown file and regenerate `MODEL_RESEARCH.pdf`.
