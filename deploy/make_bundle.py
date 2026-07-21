"""
Build the deploy artifact bundle: the SQLite DB + model files + the CSVs the serving
path reads, tarred with paths relative to the backend dir so it extracts straight
onto the server volume (see DEPLOY.md).

    python deploy/make_bundle.py            # serving core (~150MB)
    python deploy/make_bundle.py --full     # + winner_models & training matchups
                                            #   (offline research/debugging only)

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
# Heavier extras for offline/server-side research. Production Evaluation uses the
# portable JSON reports already matched by models/*.json above.
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


def build_bundle(out: Path = DEFAULT_OUT, full: bool = False) -> Path:
    """Build the bundle tar.gz and return its path. Raises if there's no DB."""
    if not (BACKEND / "data/app.db").is_file():
        raise FileNotFoundError("backend/data/app.db not found — nothing to deploy.")

    files = collect(CORE_PATTERNS + (FULL_PATTERNS if full else []))
    out.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with tarfile.open(out, "w:gz") as tar:
        for path in files:
            tar.add(path, arcname=path.relative_to(BACKEND).as_posix())
            total += path.stat().st_size

    print(f"{len(files)} files, {total / 1048576:.0f} MB uncompressed")
    print(f"bundle: {out} ({out.stat().st_size / 1048576:.0f} MB)")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="include winner_models + training matchups")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    try:
        build_bundle(args.out, full=args.full)
    except FileNotFoundError as error:
        print(f"ERROR: {error}")
        return 1
    print("Push it to the host (deploy/push_update.py does this in one step).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
