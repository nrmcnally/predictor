"""Unattended data refresh: run the incremental update locally, then push the
bundle to the server. This is what the "FIGHT IQ data update" scheduled task runs
(via auto_update.ps1, which supplies the admin password from an encrypted file).

    python deploy/auto_update.py [--server URL] [--email EMAIL] [--dry-run]

The push only happens when every pipeline stage succeeded — a failed scrape never
overwrites good server data. Exit code 0 = updated + pushed (or nothing to do),
non-zero = something failed (visible as Last Run Result in Task Scheduler).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEPLOY_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
CONFIG_PATH = DEPLOY_DIR / "auto_update.config.json"
PASSWORD_ENV = "FIGHTIQ_ADMIN_PASSWORD"

DEFAULTS = {"server": "https://fightiq.fly.dev", "email": "nrmcnally@gmail.com"}


def _config() -> dict:
    if CONFIG_PATH.is_file():
        try:
            return {**DEFAULTS, **json.loads(CONFIG_PATH.read_text(encoding="utf-8"))}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULTS)


def main() -> int:
    config = _config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default=config["server"])
    parser.add_argument("--email", default=config["email"])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="verify wiring (imports, paths, password) without scraping or pushing",
    )
    args = parser.parse_args()

    print(f"[auto-update] {datetime.now().isoformat(timespec='seconds')}")
    print(f"[auto-update] server={args.server} email={args.email}")

    # Fail fast on missing password BEFORE a long scrape burns 20 minutes for nothing.
    if not os.environ.get(PASSWORD_ENV, ""):
        print(
            f"ERROR: {PASSWORD_ENV} is not set. Run this through auto_update.ps1, "
            "or run deploy/setup_auto_update.ps1 once to store the admin password."
        )
        return 1

    # The pipeline resolves its paths from the backend package; import it from there.
    sys.path.insert(0, str(BACKEND_DIR))
    os.chdir(BACKEND_DIR)
    from app.pipeline.update_incremental_data import run_incremental_update  # noqa: E402

    if args.dry_run:
        sys.path.insert(0, str(DEPLOY_DIR))
        from make_bundle import build_bundle  # noqa: F401  (import check only)

        print("[auto-update] dry run OK: pipeline importable, password present.")
        return 0

    # 1. Refresh data locally (scrape results/cards/odds, retrain snapshots, etc.).
    report = run_incremental_update(stop_on_failure=True)
    summary = report.get("summary", {})
    if not summary.get("success"):
        failed = summary.get("failed_stages") or [
            stage.get("stage")
            for stage in report.get("stages", [])
            if stage.get("status") != "success"
        ]
        print(f"ERROR: incremental update failed (stages: {failed}). Not pushing.")
        return 1
    print("[auto-update] incremental update succeeded.")

    # 2. Build the bundle + upload it to the server (push_update handles both).
    code = subprocess.call(
        [
            sys.executable,
            str(DEPLOY_DIR / "push_update.py"),
            args.server,
            "--email",
            args.email,
            "--password-env",
            PASSWORD_ENV,
        ],
        cwd=str(DEPLOY_DIR),
    )
    if code != 0:
        print(f"ERROR: push_update exited {code}. Data updated locally but NOT pushed.")
        return code

    print("[auto-update] done — server data is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
