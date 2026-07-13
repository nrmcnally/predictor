# FIGHT IQ: System Description and Evidence-Based Improvement Roadmap

_A research-style review of the prediction engine as of model v1.2
(2026-07-13), and a literature-grounded analysis of where its metrics can
realistically be improved. Sources were gathered and adversarially verified
2026-07-13; all system numbers are reproduced from the repo's own model
registry and evaluation services._

---

## Abstract

FIGHT IQ predicts UFC fight outcomes with a Platt-calibrated logistic
regression over ~126 leakage-controlled difference features, achieving **63.2%
accuracy / 0.228 Brier / 0.649 log loss** on a chronological held-out test of
1,718 fights (2023–2026). This places it squarely in the published band for
leak-free MMA models (60–68%) but behind the betting market (~0.197 Brier on
tracked cards). We review the system end to end, situate it against the
literature, and identify the improvement avenues with the strongest evidence:
(1) style-interaction features (a published ablation attributes +2.6–3.8
accuracy points; the repo contains an orphaned implementation), (2) historical
closing odds as an anchor/benchmark via the BestFightOdds archive, (3) judge
scorecard and per-round data (already partially scraped) for round-level
skill signals, (4) rating-system upgrades (Glicko-2/WHR) over vanilla Elo, and
(5) evaluation upgrades — Shin-method de-vigging and closing-line-value as the
primary scoreboard. We also document the field's reliability pathology (a
withdrawn 80%-accuracy preprint; red-corner leakage in naive baselines) as a
guardrail for interpreting our own results.

## 1. The system as built

### 1.1 Data

All fight data derives from UFCStats: completed events, per-fight results
(winner, method, round, time), per-fighter fight stats (knockdowns,
significant strikes by target — head/body/leg — and position —
distance/clinch/ground, takedowns, submission attempts, control time), and
**per-round** versions of the same. Fighter profiles supply height, weight,
reach, stance, and DOB. Odds come from the-odds-api (h2h + rounds totals,
de-vigged by plain normalization) and are stored for display/evaluation, with
opening/closing tracked per fight for CLV.

Scale: 8,587 usable fights (1994–2026) → 17,174 training rows (each fight
mirrored in both orientations for exact symmetry); 2,694 fighters with current
snapshots. This is the entire labeled history of the sport at box-score
granularity — a permanently small-data regime.

### 1.2 Features (~110 per fighter, strictly pre-fight)

Snapshots are built by walking fights chronologically and computing every
feature from prior history only: record/experience with Bayesian shrinkage
(rate = (s + prior·w)/(n + w)), per-15-minute volume averages for/against,
recent-form windows (last 3/5), recency-decayed variants (0.72 decay per
fight), **opponent-adjusted differentials** (output relative to what that
opponent's pre-fight history typically allowed), hand-weighted style/path/
vulnerability composites, Elo (K=32 × method multiplier: finish 1.25, split
0.85) with peak/trend/strength-of-schedule aggregates, physicals, age, weight-
class history, cardio (round-slope of output; currently excluded from the
winner model after a walk-forward test showed no gain), and fight context
(scheduled rounds, main-event, card position). The winner model consumes
`diff_` columns only; the method model consumes orientation-invariant
transforms (abs-diff/mean/max/min, 497 columns).

Leakage controls are unusually disciplined for the genre: chronological
splits keyed by fight (mirrored rows stay together), pre-fight-only snapshot
construction, opponent baselines computed pre-that-fight, and method excluded
from features. Known soft spots (documented in the audit): physical/profile
attributes are merged as career constants from today's profiles; division
averages are computed over all-time data; `days_since_last_fight` for
upcoming cards measures to the latest completed event rather than the bout
date.

### 1.3 Models

Five candidate families (LR, RF, ExtraTrees, HistGB, XGBoost), each with a
Platt-calibrated variant (isotonic variants are trained as shadow experiments
but excluded from selection — correctly, as they overfit small calibration
sets; see §4.3). Selection minimizes Brier on the chronological test. The live
model is **calibrated logistic regression** — consistent with the literature's
finding that at this data scale, regularized linear models on good features
match or beat everything fancier. Serving predicts both orientations and
normalizes. A separate two-headed **method model** (broad 4-class / detailed
8-class random forests, deliberately unbalanced to keep probabilities honest)
supplies method and distance probabilities. **Market shadow models** (market-
only and model+market logistic regressions) exist for measurement only and
never influence user-facing predictions.

### 1.4 Evaluation surfaces

Retrospective: registry metrics on the 1,718-fight chronological test.
Prospective: pre-event prediction snapshots scored against results (57 fights
so far), Brier-based letter grading per card and cumulative, market-vs-model
comparison with a disagreement ("edge") analysis, CLV tracking from
opening/closing lines, and an on-demand walk-forward backtest harness with
yearly retraining. This evaluation stack is more complete than most published
work in the space.

### 1.5 Current numbers

| Metric | Value | Context |
|---|---|---|
| Test accuracy (1,718 fights) | 63.2% | Published band: 60–68% |
| Test Brier | 0.228 | Market ≈ 0.197–0.21; coin flip 0.25 |
| Test log loss / AUC | 0.649 / 0.674 | |
| Method (broad) accuracy / log loss | 53.4% / 0.983 | 4 classes; top-2 82% |
| Prospective (57 fights) | 66.7% acc, 0.223 Brier | small sample |
| Market on same tracked fights | 70.6% acc, 0.197 Brier | grade A- vs model B- |
| Disagreement record (14 fights) | model 36% vs market 64% | far below sample-size threshold |
| CLV (12 fights with movement) | 50% beat-close, ~0 avg | uninformative yet |

## 2. Related work and the honest ceiling

- **Peer-reviewed state of the art.** Holmes, McHale & Żychaluk (Intl. J.
  Forecasting 2023; Liverpool thesis 2022) simulate fights as Markov chains
  over 4,678 fights: **61.77%** winner accuracy vs bookmakers' 61.16% on the
  same 327-fight test — yet report +10–15% flat-stakes ROI in the result
  market and up to +30% in the **method market**, because profit flows from
  calibrated disagreement, not raw accuracy.
- **Feature ablations.** Yin (MLISE 2024; 7,515 fights) reports 60.6–65.5%
  across models and, critically, that removing **style-matchup factors** costs
  2.6–3.8 accuracy points — the largest single documented feature effect.
- **Serious practitioner ceiling.** The most transparent public stack
  (mmamodel.ai: GBM ensemble, 45 features, chronological splits) tops out at
  **67.6% / 0.598 log loss / ECE 0.015** and frames itself as a value-spotter,
  not a market-beater.
- **Market efficiency.** The only peer-reviewed MMA efficiency study (Miller &
  Nichols, J. Econ. & Finance 2026) finds the moneyline market largely
  efficient with no favorite-longshot bias; favorites win ~65–68%. Odds carry
  more information than results themselves (Wunderlich & Memmert 2018).
- **Reliability pathology.** An arXiv preprint claiming 80% accuracy / 90% ROI
  (FightTracker) was withdrawn in 2026 after longer evaluation; naive models
  inherit the ~62.6% red-corner win bias as fake skill (Stanford CS229 2019);
  popular Kaggle writeups leak current career stats into historical fights.
  **Any MMA claim above ~70% pre-fight accuracy has, on inspection, involved
  leakage, tiny windows, or broken baselines.** FIGHT IQ's 63.2% under strict
  chronology is exactly where an honest independent model should sit.

## 3. Improvement avenues, ranked by evidence

### 3.1 Features (strongest evidence per unit effort)

1. **Wire in the style-interaction features.** `app/features/
   matchup_interactions.py` already implements six cross-terms (takedown-vs-
   defense, KO-threat-vs-chin, sub-threat-vs-vulnerability, reach×distance,
   southpaw edge) but is orphaned — nothing imports it. The MLISE ablation
   (+2.6–3.8 pts for style factors) makes this the highest expected-value
   change in the repo, and it's mostly plumbing. Validate via the walk-forward
   harness.
2. **Exploit the per-round data already being scraped.** Only round-level
   sig-strike counts feed three cardio features today (and those are excluded
   from the winner model). Round-by-round trajectories support pace/fade,
   early-finish threat, and championship-round evidence features; judge-score
   research (JudgeAI: ~83% round-winner prediction from round stats) shows the
   rounds carry real signal.
3. **Fix the documented small bugs:** `days_since_last_fight` to actual bout
   date; scheduled-rounds inference for non-main-event five-rounders; consider
   time-based (not fight-count) recency decay and Elo inactivity decay.
4. **Unused columns:** reversals, attempted (not just landed) positional
   strikes, event location (altitude/home proxies).

### 3.2 Data acquisition

1. **Historical closing odds — BestFightOdds archive (2007→).** The single
   most informative feature in all sports-prediction literature, and the
   proper benchmark. Even kept out of the headline model (to preserve the
   market-blind comparison), a full odds history enables: an odds-anchored
   shadow model trained on *years* instead of 51 snapshot rows, Shin-de-vigged
   baselines, and CLV at scale. Open-source scrapers exist (ufc-scraper
   documents a BFO odds table with opening/closing ranges).
2. **Judge scorecards — MMADecisions;** UFC-DataLab ships an MIT-licensed
   merged stats+scorecards dataset. Enables round-winner models (~83–85%
   published), better decision-method labels, and "robbery-adjusted" results.
3. **Pre-UFC records (Sherdog/Tapology).** Kills the debut blind spot — the
   model's single largest reliability gap. Tapology's ToS prohibits scraping;
   Sherdog has been scraped at 143k-fighter scale historically. Even a coarse
   "regional record + level" feature would help the `very_limited` cohort.
4. **Weigh-ins/short-notice/camp:** constructible from event coverage but only
   anecdotal effect-size evidence; UFC PI's serial weight data (the good
   stuff) is closed. Low priority.

### 3.3 Modeling and calibration

1. **Stay tabular-classical.** Grinsztajn et al. (NeurIPS 2022, 45 datasets)
   show tree ensembles beat neural nets at ~10k samples at every tuning
   budget; the live LR choice is defensible and cheap to keep honest.
2. **Market-anchored blend as a separate output.** The literature's standard
   recipe: blend model log-odds with de-vigged market log-odds (Egidi et al.),
   or express the model as *deviation from the market prior*. For betting
   value the target is calibrated **disagreement** (Hubáček et al., IJF 2019:
   decorrelation, not accuracy, generates profit). Keep the market-blind
   headline; add a "fused" probability in the shadow layer once BFO history
   exists.
3. **Calibration under small n:** current Platt choice is right (the isotonic
   shadow's log-loss 8.15 blow-up on 13 validation rows is the textbook
   failure). Beta calibration (Kull et al. 2017) is a drop-in upgrade;
   Venn–Abers predictors add validity-guaranteed intervals — attractive for
   showing honest probability *ranges* in the UI.
4. **Never rebalance classes** for probability outputs (van den Goorbergh
   2022) — the method model's no-balancing choice is already correct.
5. **Feature-count hygiene:** 126 features on 6k training fights invites
   variance; stability selection with elastic net (Meinshausen & Bühlmann)
   inside the chronological folds is the defensible pruning method (selection
   outside CV is the classic small-sample inflation trap — Varma & Simon).
6. **Rating upgrades:** tuned Glicko-2 (adds rating uncertainty — natural for
   layoffs) or Whole-History Rating (Coulom 2008) over vanilla Elo; both are
   best-evidenced for sparse opponent graphs like MMA's.

### 3.4 Method and distance (the friend hypothesis)

The literature is thin — method/round modeling is an under-published niche,
which cuts both ways: no proven recipes, but practitioner consensus holds that
method/totals props are MMA's *least efficient* markets (wider vig, less sharp
action), and no rigorous study of MMA totals efficiency exists to refute it.
Base rates are strongly structured (≈53% of fights finish overall; heavyweight
≈2/3 finish; women's divisions ≈65% decision) — a calibrated distance model
that beats those base rates has a plausible, unmeasured market to disagree
with. Holmes's +26–30% method-market ROI at 61% winner accuracy is the
existence proof that this is where a modest model can matter. Concrete step:
per-weight-class distance calibration curves on the Model record tab, and a
totals-vs-model tracker mirroring the winner-market edge panel.

### 3.5 Evaluation

1. **Adopt CLV as the primary scoreboard** once odds history is deep enough:
   beating de-vigged closing probabilities predicts realized yield ~1:1
   (Buchdahl, 88k odds pairs) and is the only metric immune to small-sample
   luck. The plumbing (fight_odds_track) already exists.
2. **Upgrade de-vigging from plain normalization to Shin or power methods**
   (Štrumbelj 2014) — the choice matters most in high-vig markets, exactly
   where the method/totals work lives. This is a ~30-line change in
   odds_service.
3. Keep the walk-forward harness as the gate for every feature change (it has
   already correctly killed one feature family — cardio diffs).

## 4. Prioritized roadmap

| # | Change | Expected effect | Effort | Evidence |
|---|---|---|---|---|
| 1 | Wire matchup_interactions into training | +1–3 pts acc / Brier ↓ | S | peer-reviewed ablation |
| 2 | BFO closing-odds history + Shin de-vig | benchmark + shadow models on real n; CLV at scale | M | strongest-predictor consensus |
| 3 | Round-data features (pace/fade/threat) | modest Brier ↓ | M | round-signal studies |
| 4 | Glicko-2 or WHR replacing Elo | modest, compounding | M | rating-system literature |
| 5 | Beta calibration (+ Venn–Abers UI ranges) | calibration polish | S | Kull 2017 |
| 6 | Stability-selection feature pruning | variance ↓, robustness | S–M | Meinshausen & Bühlmann |
| 7 | Sherdog pre-UFC records | fixes debut blind spot | M–L | face-valid; no published ablation |
| 8 | Method/distance calibration + totals tracker | tests the soft-market hypothesis | S | Holmes ROI; practitioner consensus |
| 9 | Market-blend shadow output | value-spotting, not headline | S (after #2) | Egidi; Hubáček |

Ordering logic: #1 is free alpha sitting in the repo; #2 unlocks #9 and honest
benchmarking; everything passes through the walk-forward gate before shipping.

## 5. Limitations

Prospective samples are still tiny (57 scored fights; 14 disagreements; 12 CLV
points) — every live-performance conclusion here is provisional by the app's
own small-sample standards. The literature itself is thin and skewed toward
low-tier venues and practitioner writeups; effect sizes quoted (e.g., style
ablation points) transfer imperfectly across feature sets. And the strongest
structural fact doesn't change: this is a ~9k-fight sport with one-punch
variance — the realistic goal is market-adjacent Brier with honest calibration
and a real edge in undermeasured corners (method, distance, disagreements),
not a crystal ball.

## References

- Holmes, McHale & Żychaluk — Markov-chain MMA prediction, Intl. J. Forecasting (2023); Liverpool thesis (2022).
- Yin — MMA outcome prediction with style factors, MLISE (2024), IEEE.
- Miller & Nichols — MMA market efficiency, J. Economics & Finance 50(1) (2026).
- Wunderlich & Memmert — odds as forecasts, PLOS ONE (2018).
- Hubáček, Šourek & Železný — exploiting betting markets via decorrelation, Intl. J. Forecasting (2019).
- Egidi, Pauli & Torelli — combining historical data and bookmakers' odds (ASMBI).
- Grinsztajn, Oyallon & Varoquaux — why tree-based models outperform on tabular data, NeurIPS (2022), arXiv:2207.08815.
- Kull, Silva Filho & Flach — beta calibration (2017); Niculescu-Mizil & Caruana (2005).
- van den Goorbergh et al. — the harm of class rebalancing for probability models, JAMIA (2022); Elor (2022), arXiv:2201.08528.
- Varma & Simon (2006); Ambroise & McLachlan (2002) — selection-inside-CV.
- Meinshausen & Bühlmann — stability selection (2010).
- Coulom — Whole-History Rating (2008).
- Štrumbelj — de-vigging methods (2014).
- Buchdahl — CLV vs realized yield, football-data.co.uk.
- FightTracker, arXiv:2312.11067 — WITHDRAWN (2026); cited as cautionary only.
- McQuaide — Stanford CS229 (2019), red-corner bias.
- Data: bestfightodds.com/archive; mmadecisions.com; github.com/komaksym/UFC-DataLab (MIT); ufc-scraper.readthedocs.io; Kaggle "Ultimate UFC Dataset" (mdabbert).
