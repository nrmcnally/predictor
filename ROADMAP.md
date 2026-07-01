# UFC Fight Predictor — Accuracy Roadmap

_Last updated: 2026-06-26_

This document is the plan for making the predictor as accurate and well-calibrated as
the sport reasonably allows. It is opinionated and prioritized: the goal is to spend
effort where it moves **real, out-of-sample** performance, not where it adds surface area.

---

## 1. North Star — what "most accurate" actually means here

UFC is near the noise ceiling of predictable sports. Grounding numbers:

- Straight-up, **favorites win ~62–66%** of UFC fights.
- The **closing betting line** — the best single predictor that exists — lands ~**66–71%**.
- Good independent models cluster around **63–68%**. Beating the closing line on accuracy
  consistently is extremely rare, because the line already contains everyone's model plus
  injury/camp/weight-cut information a scraper never sees.

So the mission is **not** "push accuracy toward 90%." It is, in priority order:

1. **Be the best-calibrated model possible** — when we say 70%, it should happen ~70%.
   This is where most homegrown models are weak and where we can clearly win.
2. **Approach the closing line** in raw accuracy (close the gap from ~64% → ~67–68%).
3. **Find segments where we're sharper than the market** (specific divisions, styles,
   data-rich matchups). That's where genuine edge lives.

### Target metrics (what we optimize and report)

- **Primary:** Brier score + log loss (proper scoring rules) and **calibration** (reliability curves).
- **Secondary:** straight-up accuracy (noisy; report with confidence intervals, never alone).
- **New north-star indicator:** **Closing-Line Value (CLV)** — how often our pre-fight pick
  agrees with where the line *closes*. CLV is the leading indicator of a genuinely good model;
  accuracy is the lagging, noisy one.

---

## 2. Design principles (deliberate decisions — do not silently reverse)

1. **The front-facing model is market-free by design.** Betting odds are **never** training
   features for the production winner model. Rationale: we don't want the product's
   predictions to be a downstream echo of the market (that introduces market bias and removes
   any ability to detect when *we* are right and the market is wrong). This is intentional,
   not an oversight.
2. **Market data lives in backend-only "shadow" models** (`train_market_shadow_models.py`,
   `model_market_evaluation_service.py`). Their job is to answer one question: _is the market
   actually better than us, and by how much?_ The **gap** between the market-free model and the
   market-aware shadow model is our measured edge/ceiling. Shadow models must never feed the
   production prediction path or "best model" selection.
3. **No fantasy data.** We do not synthesize fake fights (SMOTE/GANs) to "increase accuracy" —
   on sports tabular data that manufactures patterns that don't exist and risks leakage. We
   create data only by **deriving richer features from real data** or by **hand-labeling real
   attributes** (see Phase 3).
4. **Leakage-safety is non-negotiable.** Every feature must be computable strictly from
   pre-fight information. New features ship with a test that proves it.
5. **Honesty over coverage.** Prefer "No prediction" / "low-data" flags over confident-looking
   median-imputed guesses.

---

## 3. Phase 1 — Measurement & Integrity (do first; we're partially flying blind)

We cannot tell whether a feature helped if evaluation is noisy or leaky. This phase raises
no accuracy by itself — it makes every later gain measurable and trustworthy.

- [x] **Walk-forward backtest harness.** _(2026-06-26)_ Expanding-window backtest: for each
      recent year, retrain the production model type on every prior fight and score that year
      out-of-sample. Reports per-fold metrics + aggregate mean with a 95% CI, plus an Elo-only
      baseline per fold. Backend: `app/services/walk_forward_evaluation_service.py`, endpoint
      `GET /walk-forward-evaluation`. Frontend: "Walk-forward evaluation" card in the
      Evaluation tab (loads on demand). Tests: `backend/tests/test_walk_forward.py`.
      First result: ~61.8% accuracy (±1.9% CI) over 8 yearly folds, beating the Elo baseline in
      every fold (+5.8 pts mean). _Still single-model-type per fold; full per-fold model
      reselection is a possible later refinement._
- [x] **Fix the `test_fraction` self-leak** _(2026-06-27)_. Train time now persists the exact
      `test_fight_urls` into `calibrated_model_metrics.json`; the evaluator (`resolve_holdout`)
      scores precisely that set (falling back to the saved `test_date_min` boundary, then a clamped
      fraction). The `test_fraction` slider was removed from the Evaluation UI + client. Verified:
      eval metrics now exactly match the saved training-test metrics, and `test_fraction` 0.20 vs
      0.50 return the identical 1,712-fight holdout (leak gone). Production model unchanged
      (retrain is deterministic; still logistic_regression).
- [x] **Calibrate the method models** _(2026-06-27)_. Dropped `class_weight="balanced"` /
      `"balanced_subsample"` in `train_method_models.py`. Measured the distortion directly:
      with class balancing, broad "Decision" was shown ~35% when it actually happens ~51%
      (−16 pts), Submission +11 pts. Removing it aligned predicted vs actual class rates to within
      ~3.6 pts and cut broad log-loss 1.175 → 0.987 (RF now wins both targets). A calibrator wrapper
      proved unnecessary — removing class balancing alone made the probabilities faithful while
      keeping matchup sensitivity (Makhachev/Oliveira → Submission top; Ngannou/Gane → KO top).
      Retrained method models. (Backend restart needed to clear the method-model cache.)
- [x] **Low-data gating** _(2026-06-27)_. Added a concise `data_reliability` field to the
      prediction payload (`ok` / `limited` (<5 prior fights) / `very_limited` (≤1)) with an
      explanatory note, derived in `build_prediction_context`. Surfaced as a caution badge next to
      the confidence in both the Single Fight verdict and Future Cards, plus the note in the verdict
      card. Chose caveat-not-abstain to preserve Future Cards coverage. Demonstrated value: a
      1-fight fighter vs Jon Jones was showing "100% confidence" — now flagged "Very limited data"
      so the headline can't over-claim. (The detailed per-fighter risk flags already existed; this
      ties the signal to the headline confidence.)
- [x] **CLV + per-segment calibration plots** in the Evaluation tab. _(2026-06-27)_
      **Calibration:** prospective (out-of-sample) reliability section — per confidence band, what
      the production model *said* pre-fight vs what actually happened, on completed saved
      predictions (`model_snapshot_evaluation_service.build_calibration_buckets`, pinned to the
      production model). **CLV:** new opening/closing odds tracker (`fight_odds_track.csv` —
      freezes the opening line, updates the closing line on every odds refresh, auto-wired into
      `refresh_future_fight_odds`), plus `clv_evaluation_service` + `/clv-evaluation` endpoint +
      Evaluation panel: did the line move toward the model's pick by close (beat-close rate, avg
      CLV pts). Math unit-tested; accrues over time as odds are refreshed near fight time (empty
      today — no fight has a second capture yet).
- [x] **First regression tests + pytest setup** _(2026-06-27)_. Installed pytest, added
      `pytest.ini` + `conftest.py` + `requirements-dev.txt`; the 21 tests across 7 files now run as
      one suite (`pytest`, ~1.9s). Includes a dedicated **snapshot-leakage regression test**
      (`test_snapshot_leakage.py`) asserting snapshots use only prior fights — the most important
      correctness property.
- [x] **SE hygiene** _(2026-06-27)_. (a) Stopped leaking `str(error)` internals to clients — a
      catch-all exception handler now logs full detail server-side and returns a generic message.
      (b) Added optional **admin auth**: an `ADMIN_TOKEN` env var gates the 5 heavy/mutating
      endpoints (update/start, future-cards refresh, odds refresh, save-predictions); open when
      unset (local dev), enforced (401 without `X-Admin-Token`) when set.

---

## 4. Phase 2 — Features that move accuracy

The current model uses **differences of individual aggregates**, which is mostly linear. The
biggest untapped signal is **interactions and competition quality**, not more rate-stat variants.

### Tier 1 — high signal, derivable from data we already have (best ROI)

- [x] **Strength of schedule** _(2026-06-26)_ — four leakage-safe features built from each past
      opponent's pre-fight Elo: `prior_avg_opponent_elo`, `prior_recent3_avg_opponent_elo`,
      `prior_max_opponent_elo`, `prior_avg_beaten_opponent_elo` (quality of wins). Module:
      `app/features/strength_of_schedule.py`, wired into both the historical Elo replay
      (`add_elo_features.py`) and the current/inference features (`build_current_fighter_features.py`).
      **Walk-forward A/B (8 folds, identical folds, SoS ablated vs included):** every aggregate
      metric improved — accuracy 61.78% → 62.06% (+0.28 pts), Brier −0.0003, log-loss −0.0007,
      AUC +0.0013; 5/8 folds better, 2 flat, 2 marginally worse. Gain is small and within the CI,
      but directionally consistent and low-risk, so shipped to production (retrained; best model
      remains logistic_regression). Mainly valuable as a building block for the style/interaction
      features that can exploit it nonlinearly.
- [~] **Round-level cardio / late fade** — _(2026-06-26, fully built + tested; awaits backfill + A/B.)_
      **Round-level data was NOT previously scraped** (`fight_stats.csv` is fight-totals only).
      Built end-to-end:
      - **Scraper** `app/data/scrape_fight_round_stats.py` → `data/raw/fight_round_stats.csv`
        (one row per fighter per round). Wired into BOTH pipelines. Validated: per-round rows sum
        exactly to fight totals across 1/2/3/5-round fights.
      - **Per-fight metrics** `app/features/cardio_features.py`: `cardio_sig_output_slope`
        (output rise/fall across rounds), `cardio_late_round_share` (offense in rounds 3+),
        `cardio_rounds_logged`. Real-data sanity check: Chimaev +7.1 slope / 90% late share;
        Volkov −6.0 / 24% (faded).
      - **Leakage-safe prior averages** `app/features/add_cardio_features.py`: each snapshot gets
        the fighter's average cardio over PRIOR fights only; raw post-fight values are dropped.
        Wired as an "Add cardio features" stage in both pipelines + current/inference features.
        Unit-tested (`tests/test_cardio_features.py`): metric math, prior-average leakage-safety,
        missing-data handling.
      - **RESULT (2026-06-26):** backfill done (99.8% coverage, 8,568 fights). Walk-forward A/B
        (8 folds): cardio was **−0.14 pts accuracy, Brier/log-loss slightly worse — within noise,
        no help** (same outcome as interactions). **Excluded from the model** via
        `MODEL_EXCLUDED_FEATURE_COLUMNS` in `train_calibrated_models.py`, but the round data,
        scraper, and feature pipeline are **kept** for future iteration. Production model unchanged
        (still SoS).
      - **Why it likely didn't help / how to revisit:** (a) the winner is decided by overall edges
        that Elo + striking/grappling diffs already capture; cardio mostly affects *who wins late
        rounds*, which a 3-round-weighted linear model may not reward; (b) cardio plausibly
        *interacts* with scheduled rounds (matters more in 5-round fights) — a linear model can't
        see that, a tree model could; (c) try richer metrics (output retention normalized to
        opponent, R1-vs-championship-round splits) and/or other round-derived signals (late-round
        damage absorbed, pace volatility) on the round data we now have.
- [ ] **Fighter mileage / damage accumulation** — career strikes absorbed, # of KO losses,
      total 5-round/"war" minutes, short-notice count. Predicts the sudden "falls off a cliff"
      decline that age alone misses. Pure derivation from fight logs.
- [ ] **Chin trajectory** — recency-weighted KO losses specifically (durability doesn't recover).
- [x] **Explicit style-matchup interactions** _(2026-06-26, tested — dropped)_ — built 6 cross
      terms in `app/features/matchup_interactions.py`. Walk-forward A/B across **three model types**
      (not just the production logistic): interactions were **neutral-to-slightly-negative for ALL
      of them** — logistic −0.10 pts, HistGradientBoosting −0.12 pts, XGBoost −0.33 pts; Brier flat
      or marginally worse. **Conclusion: this is not a linear-vs-tree issue** — the hand-crafted
      products carry no real signal beyond what Elo + the existing diff features already encode, and
      trees build their own interactions from the raw features so an explicit product is just
      redundant noise. Reverted from production; module kept as documented dead code. Secondary
      finding: the trees don't beat logistic on this data either (logistic 0.627 vs HGB 0.619 vs
      XGB 0.617), so "switch to a tree model" is not currently a win. **Takeaway: future gains will
      come from NEW data (cardio/fade, mileage/damage), not from recombining existing features.**
- [ ] **Stance matchup** — southpaw vs orthodox flag (a known, real edge); cross it, don't just
      include stance.

### Tier 2 — real signal, needs care

- [ ] **Layoff nonlinearity** — bucket `days_since_last_fight` (ring rust >500 days is
      nonlinearly bad); interact age × layoff.
- [ ] **Form trajectory** — improving vs declining (Elo slope), not just current level.
- [ ] **Glicko-2 rating layer** alongside Elo — adds rating *uncertainty*, which directly fixes
      the Elo cold-start + inactivity problems (see Phase 5).
- [ ] **Common-opponent / network ranking** (Bradley–Terry) as an additional signal.
- [ ] **Reach utilization** — reach advantage × distance-striking style, not reach in a vacuum.

### Tier 3 — market features: BENCHMARK-ONLY (per design principle #1/#2)

- [ ] Keep building out the **backend-only market-aware shadow models** as the accuracy
      *ceiling*. Do **not** merge market features into the production model.
- [ ] **Report the gap** between the market-free production model and the market-aware shadow
      model in the Evaluation tab — that gap is our measured edge and the honest answer to
      "is the market actually better than us?"
- [ ] Track market features that the shadow model finds most predictive (opening line, line
      movement) — useful intelligence even though we won't ingest them into the main model.

---

## 5. Phase 3 — Creating our own data

The high-ROI version is "derive richer data from what we have" and "hand-label real
attributes" — **not** synthesizing fake fights. Ranked by ROI:

1. [ ] **Mine round-level data we already scrape** (cardio, fade, fast-starter). #1 lever for
       "new data from nothing new." (Same as Phase 2 Tier 1.)
2. [ ] **Derive mileage / damage / strength-of-schedule** from existing fight logs — free,
       orthogonal signal.
3. [ ] **Hand-labeled style-archetype dataset** — wrestler / striker / BJJ / pressure / counter
       for the active roster. A few hundred labels unlock real style-matchup interaction
       features UFCStats can't provide. Bootstrap it: cluster fighters on their own stat
       profiles, then hand-correct.
4. [ ] **Accumulate our own historical odds dataset.** Keep saving odds snapshots
       (`saved_model_predictions.csv`) religiously — in a year we own a proprietary closing-line
       history that paid APIs charge for, powering both CLV measurement and the shadow models.
5. [ ] _(Optional, later)_ **NLP features** — embed fight-result write-ups / injury-report text.
       Uncertain ROI; only after the above.

---

## 6. Phase 4 — Modeling improvements

- [ ] **Stacked ensemble** instead of "pick the best by Brier." We currently train ~5 models and
      discard 4 — train a meta-learner on their **out-of-fold** predictions for a reliable
      Brier/log-loss gain.
- [ ] **Glicko-2 over plain Elo** — rating uncertainty fixes cold-start + inactivity in one move.
- [ ] **Monotonic constraints** (XGBoost) — force "higher Elo never lowers win prob," etc.
      Reduces overfit and improves calibration.
- [ ] **Time-series hyperparameter tuning** (Optuna over the walk-forward folds) — current params
      are hand-set.
- [x] **Rolling-window calibration** _(2026-06-27, tested — not shipped)_. A/B on a held-out recent
      slice (core <2022, calibrate 2022-24, measure 2024+): recalibrating on a recent window made
      the model **worse** — sigmoid Brier 0.2246 → 0.2253 and *worsened* the high-confidence tail;
      isotonic overfit the small recent slice (log-loss 0.64 → 0.70). The uncalibrated logistic is
      already the best-calibrated option. Honest read on the reliable 3,424-fight holdout: the model
      is well-calibrated through ~0.70; the only real miscalibration is mild high-confidence
      overconfidence (says ~85%, wins ~79%) on a small bucket that resists post-hoc fixing without
      hurting the aggregate. The 60-70% overconfidence seen in the 17-fight Recent-Cards sample was
      small-sample noise. _Untried gentler option if ever revisited: temperature scaling._

---

## 7. Highest-ROI shortlist (if we only do five things)

1. **Walk-forward backtest + CLV metric** — so everything else is measurable.
2. **Strength-of-schedule + mileage/damage features** — free, orthogonal, high signal.
3. **Round-level cardio/fade features** — we already have the data.
4. **Explicit style-matchup interaction terms** — where MMA prediction is actually won.
5. **Report the market-free vs market-shadow gap** — our honest, documented edge.

---

## 8. Effort / impact summary

| Item | Impact | Effort | Phase |
|---|---|---|---|
| Walk-forward backtest + CLV | Enables everything | Med | 1 |
| Fix `test_fraction` leak | Trust in metrics | Low | 1 |
| Method-model calibration | Honest method % | Low | 1 |
| Low-data gating | Honesty + fewer bad calls | Low | 1 |
| Strength of schedule | High | Low | 2 |
| Round-level cardio/fade | High | Med | 2/3 |
| Mileage / damage | Med–High | Low | 2/3 |
| Style-matchup interactions | High | Med | 2 |
| Glicko-2 layer | Med | Med | 2/4 |
| Stacked ensemble | Med | Med | 4 |
| Market shadow gap reporting | Clarity/strategy | Low | 3/5 |
| Hand-labeled style archetypes | High (unlocks Tier-1 interactions) | High | 3 |

---

## 8b. Phase 2 — Productization (online, accounts, SQLite, redesign)

_Direction (2026-06-27): take it from a local single-user tool to a hosted, account-based web
app for me + friends, accessible anywhere, with a possible native mobile app later. Decisions:
**SQLite** data layer, **full UI redesign**. The 23 critique points fold into the phases below.
Phasing rule: build the multi-user foundation before the redesign so the UX isn't redone._

### Phase 0 — Honesty + bug fixes _(do first; fast, no dependencies, makes the app trustworthy now)_ ✅ _(2026-06-28)_
- [x] #1 Proper error handling: FastAPI exception handlers (FighterNotFound→404, ValueError→404,
      Exception→500 **+ server log**); delete redundant per-endpoint try/except. _(Fixes the logging
      hole I introduced.)_
- [x] #2 Remove the **Test Lab** view from the production nav (gate behind a dev flag).
- [x] #3 Odds→fighter match safety: require BOTH fighters to match; log/flag low-confidence matches.
- [x] #11 Sample-size gating: hide grades/edge/CLV verdicts until n ≥ threshold ("need N more fights"). _(threshold = 10)_
- [x] #23 Overconfidence note (or display-time shrink) on high-confidence picks. _(chose honest note, no shrink)_
- [x] #12 Label heuristic leaderboard/style scores as heuristic. #14 Rename "Why this prediction?" →
      "Matchup breakdown". #9 Letter-grade context _(already present)_. #22 Data-age banner.

### Phase 1 — SQLite data layer _(foundational for multi-user/online)_ ✅ _(2026-06-28)_
_Decision (2026-06-28): go all-in on SQLite — scrapers write directly to the DB, every
reader (app AND offline ML/pipeline) reads from the repository, no CSV interchange.
The big ML *artifacts* (snapshots/matchups/trained models) stay as files for now; the
feature pipeline reads results from the DB and writes those artifacts to CSV._
- [x] #16 Migrate transactional data (results, saved predictions, odds track, future cards) to
      SQLite with atomic transactions + WAL; a repository/data-access layer replacing direct CSV
      reads. Done dataset-by-dataset, each verified faithful + behind tests:
      `fight_odds_track`, `saved_card_predictions`, `saved_model_predictions`, `event_fights`
      (results — TDD + golden-master proof the training data is byte-identical), and future
      cards (`upcoming_events`/`upcoming_fights`). Foundation: `app/db/` (WAL connection +
      schema) + `app/repositories/` (typed repos, shared `SnapshotTable`).
- [x] #17 Real reproducibility: `compute_training_data_hash` fingerprints the exact training
      matrix; every train records a row in the `model_runs` audit table (data hash + recipe +
      git lineage + metrics), and the hash is stamped into the model's provenance.

### Audit follow-up - conversion/product hardening _(2026-06-30)_
- [x] **Fix the duplicated FastAPI request schemas**: split Fight Lab prediction requests from
      account-pick requests and add TestClient smoke coverage for `/predict` + `/predict-method`.
      Done with separate fight/user request models and HTTP smoke coverage.
- [x] **Centralize SQLite-safe boolean parsing**: one helper should correctly parse `True/False`,
      `1/0`, `1.0/0.0`, strings, blanks, and nulls. Wire it through Recent Cards,
      Model-vs-Market, Data Quality, CLV, model snapshot evaluation, market shadow training, and
      prediction-service market-shadow input. Add regression tests with SQLite/pandas `1.0`
      values.
- [x] **Make full rebuild match incremental odds behavior**: add `Refresh future fight odds`
      before market shadow training and future-card prediction snapshots in `update_all_data.py`,
      so full rebuilds do not save stale/no-odds snapshots.
- [x] **Lock down scheduled-round overrides**: admin-gate the mutation endpoint and enforce
      co-main / third-from-top eligibility server-side, with Fight Night cards excluded.
- [x] **Add forward migrations for all SQLite tables**: current `init_db` only ensures the
      `users` table has new columns; add table-specific column migrations for saved predictions,
      saved model predictions, future odds, future cards, and user predictions.
- [x] **Stamp provenance on all-model snapshots**: add model version, recipe hash, trained-at, and
      git lineage to `saved_model_predictions` so prospective model rows are not blended across
      recipe generations.
- [x] **Clean up update-job drift**: fix the initial `total_stages` count, remove the stale
      `update_job_services.py` duplicate, and make stage totals derive from the pipeline list.
- [x] **Frontend quality pass**: clear current ESLint failures (`AuthProvider`, `Leaderboards`,
      `MyPicks`). Route-level code splitting remains a performance follow-up for the large bundle.
- [ ] **Deployment/auth hardening**: require a real `AUTH_SECRET` outside local/demo, avoid open
      admin endpoints in hosted mode, hide demo credentials unless demo/mock mode is active, and
      keep `start_app.local.bat` private/ignored.
- [~] **Add HTTP/regression smoke tests**: cover `/predict`, `/predict-method`, Recent Cards
      market scoring, Model-vs-Market, Data Quality, market shadow training rows, and full rebuild
      stage ordering. Core HTTP/auth/prediction/event-control smoke coverage exists; market/data
      quality endpoint smoke coverage is still open.
- [ ] **Data-quality follow-up**: keep surfacing inactive, low-sample, and missing-reach caveats;
      latest audit saw 66.9% inactive-over-3-years, 53.3% under five UFC fights, 642 missing reach
      values, and 25.5% future-odds coverage.

### Phase 2 — Accounts + API security
- [ ] User auth (registration/login, hashed passwords, sessions or JWT); per-user data (saved
      cards, favorites, notes) — the ML/predictions stay **shared/global**.
- [ ] API hardening: rate limiting, input validation, replace the admin token with proper roles,
      CORS for the deployed origin, security headers.
- [ ] #18 Start splitting the 1,909-line `prediction_service` as you touch it.

### Phase 3 — Deployment + ops
- [x] **Deploy prep, host-agnostic** _(2026-07-01)_. Single-container Dockerfile
      (multi-stage: frontend build → python-slim serve, Playwright excluded), FastAPI
      serves the built frontend same-origin, artifacts (DB + models) live on a volume
      populated by `deploy/make_bundle.py` (~44MB core bundle; `--full` adds
      winner_models for Evaluation deep-dives). `DEPLOY.md` covers Fly.io / Railway /
      VPS (compose file included). Host choice deliberately deferred.
- [x] **Hosted-mode hardening** _(2026-07-01)_. `FIGHTIQ_HOSTED=1`: boot fails fast
      without a real AUTH_SECRET; require-auth wall on everything except
      health/login/register/static; `ALLOW_REGISTRATION` kill-switch; demo seed strips
      real credentials (+VACUUM); proxy-aware (TRUST_PROXY) + memory-bounded rate
      limiter; admin one-time password reset (endpoint + Users admin UI).
- [x] #19 CI/CD _(2026-07-01)_ — GitHub Actions: backend pytest + frontend
      eslint/build on push; artifact-dependent tests self-skip without local models.
- [ ] Actually deploy: pick the host (Fly.io / Railway / VPS), follow DEPLOY.md.
- [ ] _(chosen model: local updates + bundle push, not server-side scraping)_ If that
      gets tiresome, revisit a scheduled server-side job (#20 idempotent stages).

### Phase 4 — Full UI redesign _(mobile-first, accessible, restructured)_
- [ ] #4 Evaluation-tab progressive disclosure (Overview vs Deep Dive). #5 de-clutter tags.
- [ ] #6 Color-blind-safe + a11y (icons+text not just color, aria, focus, keyboard).
- [ ] #7 Responsive/mobile-first (PWA-capable — bridges to a future native app). #8 CSS → design
      system / tokens. #21 account/login shell + navigation.
- [ ] First frontend tests as part of the redesign.

### Phase 5 — Modeling rigor _(parallelizable, backend-only)_
- [ ] #10 Select the production model via the **walk-forward folds**, not a single split.
- [ ] #15 Feature-importance / ablation diagnostic. #12 Validate-or-drop heuristic leaderboard
      scores. #13 Glicko-2 (optional — fixes Elo cold-start).

---

## 8c. Phase 6 — Account-based predictions & social

_Direction (2026-06-29): turn FIGHT IQ from a model viewer into a prediction game —
users make their own picks, build a track record, and compare against friends and
the model. The ML model stays shared/global; predictions/stats are per-account._

- [x] **Make the admin role functional** _(started 2026-06-29)_. Backend roles gate
      admin-only endpoints/surfaces; Users admin view supports role promote/demote.
- [x] **Account profile page** — view your account (username, role, joined), your
      prediction stats, and a place for future settings. Foundation for the social bits.
- [x] **Account-based card predictions** — let a logged-in user pick winners on upcoming
      cards; store per-user picks (`user_predictions`); lock at event start via admin
      event controls; score against actual results once events complete. Distinct from the
      model's own predictions (which stay the shared baseline to beat).
- [~] **User prediction stats** — per-account accuracy, record, streaks, and "vs the
      model" / "vs the market" deltas. Keep user scoring intuitive: winner/method only,
      no confidence slider; Brier/log-loss stay model-evaluation metrics.
- [~] **Public leaderboards** — rank users by prediction performance. Overall opt-in
      leaderboard exists; per-window / friends-only variants remain open.
- [x] **Friend vs friend comparisons** — mutual-accept friends by username plus direct
      head-to-head comparisons on shared graded picks.

_Open design decisions (resolve before building the prediction game):_
  - Friend model: resolved as mutual-accept by username.
  - Public vs private profiles: opt-in public leaderboard visibility.
  - Primary ranking metric: current FIGHT IQ rating + accuracy context; per-window views still open.
  - Pick window: backend-owned event lock state with odds-time suggestions and admin overrides.

---

## 9. Status log

- 2026-07-01 — Added backend-owned event lock controls for the prediction game:
  `event_controls` in SQLite, odds-derived start-time suggestions, admin manual start
  overrides, force-open / force-locked modes, and Future Cards admin UI. My Picks now
  consumes backend `lock_state` instead of local event-date math. No user confidence
  slider; user picks stay winner/method only.
- 2026-06-26 — Roadmap created. Confirmed design decision: production model stays market-free;
  market models remain backend-only benchmarks.
- 2026-06-26 — Built the walk-forward backtest harness (service + endpoint + Evaluation card +
  tests). Verified end-to-end: ~61.8% accuracy (±1.9% CI) across 8 yearly folds, beats Elo in
  every fold. **CLV deferred on purpose** — doing it honestly needs a true closing-line capture
  step (snapshot odds as close to fight time as possible); today's saved odds are captured at
  update time, not at close, and the existing "Model vs market" card already covers basic
  agreement. Next: add a closing-line snapshot step, then a real CLV metric on top of it.
- 2026-06-26 — Built per-round data infrastructure for cardio/fade: discovered round-level data
  was never scraped (fight totals only), wrote `scrape_fight_round_stats.py` (validated: rounds
  sum to totals), created `fight_round_stats.csv`, and wired refresh stages into both update
  pipelines. Sample of 6 fights scraped. Also tested style-matchup interactions across 3 model
  types and dropped them (neutral-to-negative for ALL, not a linear-vs-tree issue).
- 2026-06-26 — Built the full cardio/fade FEATURE pipeline (metrics + leakage-safe prior averages
  + current-feature + both-pipeline wiring + unit tests). Validated on real seed data and synthetic
  tests. Production model untouched; remaining work is the long backfill, then rebuild/retrain and
  a walk-forward A/B to decide whether cardio earns a place in the model.
- 2026-06-27 — Fixed the Evaluation `test_fraction` self-leak (Phase 1 trust item): the tab now
  scores the model's true persisted holdout regardless of UI controls; slider removed.
- 2026-06-27 — Made method-of-ending probabilities honest by removing class balancing (broad
  log-loss 1.175 → 0.987; predicted class rates now match actuals within ~3.6 pts).
- 2026-06-27 — Added low-data gating (data_reliability caveat next to confidence in both prediction
  views). **All three Phase 1 trust items now complete** (eval holdout leak, method calibration,
  low-data gating).
- 2026-06-27 — Replaced binary right/wrong grading in Recent Cards with probability-aware grading
  (`app/services/prediction_grading.py`): Brier/log-loss → UFC-calibrated **letter grades** for the
  engine AND the market on the same scale, a plain "Beat/Matched/Behind the market" verdict,
  per-fight quality tiers (Confident hit / Lean hit / Close miss / Bad miss), and **expected-vs-
  actual** wins. Per-card report card + an **overall cumulative grade** (the meaningful one; single
  cards are noise). First real read: engine B-, market A-, behind the market — but expected 28.0 /
  got 27, i.e. well-calibrated, just trailing a sharp market. This is also the foundation for the
  market-gap/CLV work: model-vs-market is now scored with proper rules and the disagreement is
  visible per fight.
- 2026-06-27 — Added **CLV (closing-line value)**: an opening/closing odds tracker that auto-captures
  on every odds refresh, a CLV service/endpoint/panel measuring whether the line moves toward the
  model's picks ("beat the close"), and a coverage pass (added pytest-cov; SoS test → SoS 100%;
  critical-logic coverage now 80-95% while overall is ~12%, which is the right shape for an
  I/O-heavy ML app). CLV is the last roadmap lever — it accrues over time, empty until odds get a
  second capture per fight.
- 2026-06-27 — Knocked out the trust/robustness queue in order: (1) **prospective calibration**
  section in the Evaluation tab (out-of-sample said-vs-actual per confidence band, pinned to the
  production model); (2) **pytest setup** (pytest.ini + conftest + requirements-dev; 21 tests run
  as one suite) plus a **snapshot-leakage regression test**; (3) **SE hygiene** — stopped leaking
  `str(error)` to clients (catch-all handler logs server-side, returns generic), and added optional
  `ADMIN_TOKEN` auth on the 5 heavy/mutating endpoints. The codebase is now tested, doesn't disclose
  internals, and can be locked down.
- 2026-06-27 — Reconstructed the **model version timeline** from git history + saved-snapshot
  dates: 1.0 (initial, 05-15) → 1.1 (feature + age expansion, 05-16) → 1.2 (strength-of-schedule,
  this session). The 05-17→06-10 commits were frontend/eval, not recipe changes. Bumped the live
  model to **v1.2** (more accurate than the 1.0 placeholder), added `VERSION_HISTORY` +
  `estimate_version_for_date` so pre-provenance snapshots get a **version estimated from their save
  date**, and wrote `CHANGELOG.md`. Result: the 5 completed cards now show **~v1.1 (estimated,
  older)** and the re-saved future cards show **v1.2 (current)** — every card is now version-labelled.
- 2026-06-27 — Added **model versioning + prediction provenance** (`app/models/model_version.py`).
  Three layers: a human `MAJOR.MINOR` `MODEL_VERSION` (bump deliberately — major for big changes,
  minor for small meaningful ones), an automatic **recipe_hash** (hash of features + model type +
  calibration — stable across routine retrains, changes only on real recipe changes), and git
  commit/dirty + trained_at lineage. Stamped into `calibrated_model_metrics.json` at train time and
  onto every saved prediction; Recent Cards now flags each card's snapshot as same/older/unknown
  **generation** vs the live model and shows the live model version. Also **re-saved the future-card
  snapshots** (safe — completed cards untouched), which fixes the stale-snapshot issue: upcoming
  cards now carry current-model predictions stamped v1.0. Completed cards honestly show
  "unversioned" (they predate this). **Discipline:** bump `MODEL_VERSION` when shipping a meaningful
  change; the recipe_hash is the automatic safety net.
- 2026-06-27 — Tested rolling-window calibration; **null result** — recalibrating on a recent slice
  made the model worse on Brier/log-loss and didn't fix the high-confidence tail. The uncalibrated
  logistic is already as calibrated as post-hoc methods allow. Not shipped (measure-first discipline
  again prevented a regression). The model's high-conf overconfidence (~85%→79%) is small, on a thin
  bucket, and largely irreducible — already visible in the Evaluation calibration buckets.
- 2026-06-27 — Fixed the recurring **stale-cache footgun** (the bug behind every "restart to see
  changes", incl. the age regression). New `file_aware_cache` decorator in `prediction_service.py`
  keys the cached loaders on source-file mtimes, so the running server auto-reloads the model,
  features, current-fighter, market-shadow, weight-size, and method caches whenever those files
  change on disk — including out-of-process CLI retrains and manual script runs. `cache_clear`
  preserved. Verified: cached when unchanged, reloads on change, no restart needed.
- 2026-06-27 — Built the **market-edge (disagreement) view** in Recent Cards
  (`build_edge_analysis`): splits scored fights into agree/disagree-with-market and grades each.
  First honest read — on disagreements (10 fights) the model went 4/10, Brier 0.283 vs market
  0.223 ("behind the market"); on agreements (24) it matched the market. I.e. the model's value is
  agreeing with the market on chalk; its deviations don't (yet) pay — correctly flagged as small
  sample. This is the model-shadow-gap lever realised at the per-fight level. True CLV still needs
  a closing-line capture step (current odds are snapshot-time). The model is at its accuracy ceiling and the product is now considerably more
  honest. Open future work is orthogonal-data (market-shadow gap / CLV) and the remaining original
  software-engineering critique items (tests, error-handling, admin auth, the lru_cache-after-
  retrain restart gap that keeps recurring).
- 2026-06-27 — **Tree-model bake-off (decisive).** Walk-forward, 3 models × 4 feature sets
  (base / +cardio / +interactions / +both). Result: **no model + feature-set combo beats
  production logistic/base on accuracy (0.6201).** Adding cardio or interactions made *every*
  model slightly worse on accuracy — confirmed not a linear-vs-tree issue. Nuance: trees gave
  marginally better *Brier* (XGB ~0.2317 vs logistic ~0.2338, uncalibrated) but ~0.8 pts worse
  accuracy — a possible future calibration angle, not a clear win. **Conclusion: accuracy is at
  the ceiling for this approach; stop chasing it via feature engineering and pivot to
  trustworthiness/calibration (Phase 1 integrity items) and orthogonal data (market-shadow gap).**
- 2026-06-26 — Backfilled per-round data (99.8% coverage), rebuilt snapshots+matchups with cardio,
  and ran the walk-forward A/B. Cardio did NOT help (−0.14 pts, within noise) — excluded from the
  model but data/scraper/pipeline kept for future iteration. So far: SoS shipped (small +);
  interactions and cardio both measured and held out. Pattern confirmed: recombining/deriving from
  existing signal hasn't beaten Elo+diffs with a linear model. Biggest open levers: a tree-model
  bake-off with richer interactions, and genuinely orthogonal data (market shadow gap, mileage/damage).
- 2026-06-26 — Round-stats scraper performance overhaul (the original was ~11s/fight → ~26h for the
  backfill, and only saved at the very end so an interrupt lost everything). Fixes: (1) `UfcStatsSession`
  in `ufcstats_fetcher.py` solves the JS browser-check once with Playwright, then fetches via a
  cookie-warmed `requests` session (~0.66s/fight, auto-re-warms if cookies go stale); (2)
  position-based per-round row parsing (robust to UFCStats' malformed table HTML that BeautifulSoup
  and a browser nest differently — avoided needing lxml/html5lib); (3) checkpoint-to-disk every 25
  fights + a finally block, so the scrape is fully resumable. Net: full backfill ~1.5h instead of
  ~26h, reliable (15/15), correct (per-round sums match fight totals 30/30). Fights are processed
  newest-first, so the most prediction-relevant data lands first.
- 2026-06-26 — Shipped strength-of-schedule (Phase 2 Tier 1). Added an ablation hook
  (`drop_feature_columns`) to the walk-forward harness and used it to A/B the feature on
  identical folds before shipping. Net: small but consistent improvement on every metric;
  retrained production. Note: a running backend must be restarted (or its lru_caches cleared)
  to pick up the new model + current features. Next candidate: round-level cardio/fade, or
  explicit style-matchup interactions that build on SoS.
