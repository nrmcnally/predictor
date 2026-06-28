# Model Changelog

Versions of the **winner-prediction model recipe** (features + model type + calibration).
`MAJOR.MINOR` — major for big changes (model-type swap, methodology), minor for a
feature/calibration change. Routine retrains on fresh data do **not** bump the version
(same recipe, new data); only recipe changes do. The source of truth is
`backend/app/models/model_version.py` (`VERSION_HISTORY`); the live model's exact
version + recipe hash are stamped into `models/calibrated_model_metrics.json` and onto
every saved prediction.

Dates are reconstructed from git history and saved-snapshot timestamps, so versions for
snapshots saved before provenance stamping (pre-1.2) are **estimated** from their save date.

---

## 1.2 — 2026-06-27 (current)
- **Strength-of-schedule features** — opponent-Elo quality (avg / recent / peak opponent
  Elo, quality of wins). The first feature change since 1.1; recipe hash changed here.
- Shipped in the same generation (trust/eval/UX, not recipe changes themselves):
  - Evaluation **holdout-leak fix** (`test_fraction`) — eval now scores the model's true
    persisted holdout.
  - **Method-model recalibration** — dropped class balancing so manner-of-ending
    percentages reflect real base rates.
  - **Low-data gating** — `data_reliability` caveat next to confidence.
  - **Probability-aware grading** + market-edge view in Recent Cards.
  - Round-level data scraper + cardio feature pipeline (built & A/B-tested; cardio
    **excluded** from the model — it didn't help).
  - `file_aware_cache` (auto-reload on retrain) and model-version provenance.

## 1.1 — 2026-05-16
- **Feature expansion**: Bayesian-shrunk, time-decayed, and opponent-adjusted stats;
  physical features (height / reach / stance); and **age** features.
- This was the mature pre-SoS recipe that produced the saved snapshots from
  2026-05-16 through 2026-06-15 (graded as estimated v1.1).

## 1.0 — 2026-05-15
- Initial model — Elo + core fight-history features, calibrated logistic regression.

---

_Note: the 2026-05-17 → 2026-06-10 commits (method prediction, fighter profiles, the
Three.js frontend rebuild, evaluation-tab work) did not change the winner-model recipe,
so they don't carry a winner-model version bump._
