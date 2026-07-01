"""
Build the deploy artifact bundle: the SQLite DB + model files + the CSVs the serving
path reads, tarred with paths relative to the backend dir so it extracts straight
onto the server volume (see DEPLOY.md).

    python deploy/make_bundle.py            # serving core (~150MB)
    python deploy/make_bundle.py --full     # + winner_models & training matchups
                                            #   (enables the Evaluation deep-dives)

Run it after a local Data Ops update, then push the fresh bundle to the host.
"""

from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
DEFAULT_OUT = REPO_ROOT / "deploy" / "deploy_bundle.tar.gz"

# Everything the SERVING path reads. Globs are relative to backend/.
CORE_PATTERNS = [
    "data/app.db",
    "data/raw/*.csv",
    "data/processed/current_fighter_features.csv",
    "data/processed/fighter_snapshots.csv",
    "models/*.json",
    "models/*.joblib",
    "models/market_shadow_models/*",
]
# Heavier extras for the Evaluation tab's model-comparison / holdout deep-dives.
FULL_PATTERNS = [
    "models/winner_models/*",
    "data/processed/training_matchups.csv",
]
# Never ship scratch copies.
EXCLUDE_SUBSTRINGS = ("backup", ".demo.", "-wal", "-shm")


def collect(patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        matches = sorted(BACKEND.glob(pattern))
        if not matches:
            print(f"  (nothing matches {pattern} — skipped)")
        files.extend(m for m in matches if m.is_file())
    return [
        f for f in files
        if not any(marker in f.name.lower() for marker in EXCLUDE_SUBSTRINGS)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="include winner_models + training matchups")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    patterns = CORE_PATTERNS + (FULL_PATTERNS if args.full else [])
    files = collect(patterns)
    if not (BACKEND / "data/app.db").is_file():
        print("ERROR: backend/data/app.db not found — nothing to deploy.")
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with tarfile.open(args.out, "w:gz") as tar:
        for path in files:
            arcname = path.relative_to(BACKEND).as_posix()
            tar.add(path, arcname=arcname)
            total += path.stat().st_size

    print(f"\n{len(files)} files, {total / 1048576:.0f} MB uncompressed")
    print(f"bundle: {args.out} ({args.out.stat().st_size / 1048576:.0f} MB)")
    print("Push it to the host and extract into the volume root (see DEPLOY.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
