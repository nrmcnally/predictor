from __future__ import annotations

"""
Model versioning & prediction provenance.

Three layers, increasing automation:

  1. MODEL_VERSION  — human-set "generation", MAJOR.MINOR.
         MAJOR (2.x) = big change: model type, methodology, major feature-set overhaul.
         MINOR (1.1) = smaller meaningful change: a feature added, calibration tweak.
       Bump it deliberately when you ship a meaningful change — NOT on routine retrains.

  2. recipe_hash    — automatic. Hash of (feature columns + model type + calibration).
       Stays identical across routine retrains (same recipe, new data); changes only
       when the recipe actually changes. This is the objective "meaningful change"
       detector, so staleness flags don't false-alarm on every data refresh.

  3. git_commit / trained_at — automatic lineage: which code, dirty-or-not, and when.

Saved predictions are stamped with this, so grading can tell whether a card was
predicted by the same generation of model that is live now.
"""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


# Winner-model recipe history, oldest first, reconstructed from git history + saved
# snapshot dates. `date` is when that recipe became effective (ISO YYYY-MM-DD). Used
# to estimate a version for snapshots saved before provenance stamping existed.
# Bump by appending an entry when you ship a meaningful change (major for big changes
# like a model-type swap, minor for a feature/calibration change).
VERSION_HISTORY = [
    {
        "version": "1.0",
        "date": "2026-05-15",
        "summary": "Initial model — Elo + core fight-history features, calibrated logistic.",
    },
    {
        "version": "1.1",
        "date": "2026-05-16",
        "summary": (
            "Feature expansion: Bayesian-shrunk / time-decayed / opponent-adjusted "
            "stats, physical (height/reach/stance) and age features."
        ),
    },
    {
        "version": "1.2",
        "date": "2026-06-27",
        "summary": (
            "Strength-of-schedule features (opponent-Elo quality). Same generation also "
            "shipped the evaluation holdout-leak fix, method-model recalibration, "
            "low-data gating, and probability-aware grading."
        ),
    },
]

MODEL_VERSION = VERSION_HISTORY[-1]["version"]


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CALIBRATED_METRICS_PATH = PROJECT_ROOT / "models" / "calibrated_model_metrics.json"


def compute_recipe_hash(
    numeric_features: list[str],
    categorical_features: list[str],
    model_type: str,
    calibration_method: str,
) -> str:
    payload = {
        "numeric_features": sorted(numeric_features),
        "categorical_features": sorted(categorical_features),
        "model_type": model_type,
        "calibration_method": calibration_method,
    }
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:10]


def compute_training_data_hash(training_df, columns: list[str]) -> str:
    """A deterministic, order-independent fingerprint of the exact training data
    (selected columns x rows) a model was fit on. Lets us later prove which data
    produced a given model (#17: real reproducibility)."""
    import pandas as pd

    subset = training_df[list(columns)]
    row_hashes = pd.util.hash_pandas_object(subset, index=False)

    digest = hashlib.sha256()
    for value in sorted(int(h) for h in row_hashes.to_numpy()):
        digest.update(int(value).to_bytes(8, "little", signed=False))
    digest.update("|".join(str(c) for c in columns).encode("utf-8"))
    return digest.hexdigest()[:16]


def get_git_info() -> dict[str, Any]:
    def _run(args: list[str]) -> str:
        try:
            result = subprocess.run(
                args,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

    commit = _run(["git", "rev-parse", "--short", "HEAD"])
    status = _run(["git", "status", "--porcelain"])

    return {"git_commit": commit, "git_dirty": bool(status)}


def build_provenance(
    numeric_features: list[str],
    categorical_features: list[str],
    model_type: str,
    calibration_method: str,
) -> dict[str, Any]:
    """Computed at train time and saved into calibrated_model_metrics.json."""
    provenance = {
        "model_version": MODEL_VERSION,
        "recipe_hash": compute_recipe_hash(
            numeric_features, categorical_features, model_type, calibration_method
        ),
        "model_type": model_type,
        "calibration_method": calibration_method,
        "trained_at": datetime.now().isoformat(timespec="seconds"),
    }
    provenance.update(get_git_info())
    return provenance


def load_current_provenance() -> dict[str, Any]:
    """The provenance of the currently-saved production model (empty if none)."""
    if not CALIBRATED_METRICS_PATH.exists():
        return {}

    try:
        with open(CALIBRATED_METRICS_PATH, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}

    return payload.get("provenance", {}) or {}


def estimate_version_for_date(saved_at: str | None) -> str:
    """
    Best-effort version for a snapshot saved before provenance stamping existed,
    based on when it was saved vs the recipe history. Returns "" if no date.
    """
    when = (saved_at or "")[:10]  # YYYY-MM-DD; ISO strings sort correctly as text

    if not when:
        return ""

    version = VERSION_HISTORY[0]["version"]
    for entry in VERSION_HISTORY:
        if entry["date"] <= when:
            version = entry["version"]
        else:
            break

    return version


def generation_status(saved_recipe_hash: str | None) -> str:
    """
    Compares a saved prediction's recipe hash to the current model.

    Returns "current" (same recipe), "older" (a different/earlier recipe), or
    "unknown" (snapshot predates provenance stamping).
    """
    saved_recipe_hash = (saved_recipe_hash or "").strip()

    if not saved_recipe_hash:
        return "unknown"

    current = load_current_provenance().get("recipe_hash", "")

    if not current:
        return "unknown"

    return "current" if saved_recipe_hash == current else "older"
