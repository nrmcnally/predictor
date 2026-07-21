"""Unattended data refresh: run the incremental update locally, then push the
bundle to the server. This is what the "FIGHT IQ data update" scheduled task runs
(via auto_update.ps1, which supplies the admin password from an encrypted file).

    python deploy/auto_update.py [--server URL] [--email EMAIL] [--dry-run]

The push only happens when every pipeline stage succeeded — a failed scrape never
overwrites good server data. Exit code 0 = updated + pushed (or nothing to do),
exit 2 = safe update pushed with warnings, and other non-zero values = failure.
Any non-zero result remains visible in Task Scheduler.
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
SUCCESS_STATE_PATH = DEPLOY_DIR / "logs" / "last_successful_push.json"
PASSWORD_ENV = "FIGHTIQ_ADMIN_PASSWORD"
ODDS_API_KEY_ENV = "ODDS_API_KEY"

DEFAULTS = {"server": "https://fightiq.fly.dev", "email": "nrmcnally@gmail.com"}


def _read_success_state() -> dict:
    try:
        value = json.loads(SUCCESS_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _already_pushed_today(now: datetime | None = None) -> bool:
    """Return true only when a completed server upload is stamped for today."""
    value = _read_success_state().get("last_successful_push_at")
    if not isinstance(value, str) or not value:
        return False
    try:
        pushed_at = datetime.fromisoformat(value)
    except ValueError:
        return False

    current = now or datetime.now().astimezone()
    if pushed_at.tzinfo is not None and current.tzinfo is not None:
        pushed_at = pushed_at.astimezone(current.tzinfo)
    return pushed_at.date() == current.date()


def _write_success_state(*, server: str, degraded: bool) -> None:
    """Atomically stamp a successful upload so catch-up triggers stay idempotent."""
    SUCCESS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "last_successful_push_at": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
        "server": server,
        "degraded": bool(degraded),
    }
    temporary_path = SUCCESS_STATE_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(SUCCESS_STATE_PATH)


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
    parser.add_argument(
        "--skip-if-pushed-today",
        action="store_true",
        help="exit successfully when this machine already completed today's upload",
    )
    args = parser.parse_args()

    print(f"[auto-update] {datetime.now().isoformat(timespec='seconds')}")
    print(f"[auto-update] server={args.server} email={args.email}")

    if args.skip_if_pushed_today and _already_pushed_today():
        state = _read_success_state()
        print(
            "[auto-update] skipped: this machine already pushed successfully today "
            f"at {state.get('last_successful_push_at')}."
        )
        return 0

    # Fail fast on missing password BEFORE a long scrape burns 20 minutes for nothing.
    if not os.environ.get(PASSWORD_ENV, ""):
        print(
            f"ERROR: {PASSWORD_ENV} is not set. Run this through auto_update.ps1, "
            "or run deploy/setup_auto_update.ps1 once to store the admin password."
        )
        return 1
    if not os.environ.get(ODDS_API_KEY_ENV, ""):
        print(
            f"ERROR: {ODDS_API_KEY_ENV} is not set. Run deploy/setup_auto_update.ps1 "
            "to store the odds credential for the scheduled refresh."
        )
        return 1

    # The pipeline resolves its paths from the backend package; import it from there.
    sys.path.insert(0, str(BACKEND_DIR))
    os.chdir(BACKEND_DIR)
    from app.pipeline.update_incremental_data import run_incremental_update  # noqa: E402

    if args.dry_run:
        sys.path.insert(0, str(DEPLOY_DIR))
        from make_bundle import build_bundle  # noqa: F401  (import check only)

        print("[auto-update] dry run OK: pipeline importable, encrypted credentials present.")
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
    degraded = summary.get("degraded_stages") or []
    if degraded:
        print(f"WARNING: incremental update completed with warnings: {degraded}")
    print("[auto-update] incremental update succeeded.")

    # 2. Build the bundle + upload it to the server (push_update handles both).
    code = subprocess.call(
        [
            sys.executable,
            "-u",
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

    _write_success_state(server=args.server, degraded=bool(degraded))

    if degraded:
        print(
            "[auto-update] server received the safe data update, but the run is "
            "degraded; review Data Ops alerts."
        )
        return 2

    print("[auto-update] done — server data is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
