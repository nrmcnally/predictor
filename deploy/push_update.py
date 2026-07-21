"""
One-command remote data update: build the deploy bundle and upload it to a running
FIGHT IQ instance over HTTPS. The server merges the shared data (results, cards,
odds, saved predictions) and swaps model files — accounts/picks/friendships on the
server are never touched.

    python deploy/push_update.py https://yourapp.fly.dev
    python deploy/push_update.py https://yourapp.fly.dev --email you@example.com

Run it after a local Data Ops update. Requires an ADMIN account on the server.
(For the rare --full bundle, use the sftp path in DEPLOY.md instead — it's too big
for a comfortable HTTP upload.)
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_bundle import DEFAULT_OUT, build_bundle  # noqa: E402

WAKE_ATTEMPTS = 4
LOGIN_ATTEMPTS = 3
WAKE_TIMEOUT = (10, 90)
LOGIN_TIMEOUT = (10, 90)
UPLOAD_TIMEOUT = (30, 600)  # connect, read; server merge can outlast the upload
RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


def _retry_delay(attempt: int) -> int:
    return min(2 ** (attempt - 1), 10)


def warm_host(session: requests.Session, base: str) -> bool:
    """Wake the hosted app before login so a cold start cannot consume its timeout."""
    for attempt in range(1, WAKE_ATTEMPTS + 1):
        try:
            response = session.get(f"{base}/health", timeout=WAKE_TIMEOUT)
        except (requests.Timeout, requests.ConnectionError) as error:
            response = None
            detail = error.__class__.__name__
        else:
            if response.status_code == 200:
                if attempt > 1:
                    print(f"Host became ready on wake attempt {attempt}.")
                return True
            detail = f"HTTP {response.status_code}"
            if response.status_code not in RETRYABLE_STATUS_CODES:
                print(f"ERROR: host health check failed ({detail}).")
                return False

        if attempt < WAKE_ATTEMPTS:
            delay = _retry_delay(attempt)
            print(
                f"Host is not ready ({detail}); retrying health check in {delay}s "
                f"[{attempt}/{WAKE_ATTEMPTS}]."
            )
            time.sleep(delay)

    print("ERROR: host did not become ready after repeated health checks.")
    return False


def login_with_retries(
    session: requests.Session,
    base: str,
    email: str,
    password: str,
) -> str | None:
    """Authenticate after warm-up, retrying only transient network/server failures."""
    for attempt in range(1, LOGIN_ATTEMPTS + 1):
        try:
            response = session.post(
                f"{base}/auth/login",
                json={"email": email, "password": password},
                timeout=LOGIN_TIMEOUT,
            )
        except (requests.Timeout, requests.ConnectionError) as error:
            response = None
            detail = error.__class__.__name__
        else:
            if response.status_code == 200:
                try:
                    return str(response.json()["token"])
                except (KeyError, TypeError, ValueError):
                    print("ERROR: login response did not contain a usable token.")
                    return None
            detail = f"HTTP {response.status_code}"
            if response.status_code not in RETRYABLE_STATUS_CODES:
                print(f"ERROR: login failed ({response.status_code}): {response.text[:200]}")
                return None

        if attempt < LOGIN_ATTEMPTS:
            delay = _retry_delay(attempt)
            print(
                f"Login hit a transient failure ({detail}); retrying in {delay}s "
                f"[{attempt}/{LOGIN_ATTEMPTS}]."
            )
            time.sleep(delay)

    print("ERROR: login failed after repeated transient failures.")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("server", help="base URL, e.g. https://fightiq.fly.dev")
    parser.add_argument("--email", help="admin email (prompted if omitted)")
    parser.add_argument(
        "--password-env",
        help="read the admin password from this environment variable (for scripting; "
        "interactive prompt otherwise)",
    )
    parser.add_argument("--skip-build", action="store_true", help="upload the existing bundle as-is")
    args = parser.parse_args()
    base = args.server.rstrip("/")

    # 1. Build (or reuse) the bundle.
    if args.skip_build:
        bundle = DEFAULT_OUT
        if not bundle.is_file():
            print(f"ERROR: no bundle at {bundle} — run without --skip-build.")
            return 1
    else:
        bundle = build_bundle()

    # 2. Log in as the admin (password prompted, never a CLI arg / shell history).
    email = args.email or input("Admin email: ").strip()
    if args.password_env:
        password = os.environ.get(args.password_env, "")
        if not password:
            print(f"ERROR: environment variable {args.password_env} is empty/unset.")
            return 1
    else:
        password = getpass.getpass(f"Password for {email}: ")
    session = requests.Session()
    if not warm_host(session, base):
        return 1
    token = login_with_retries(session, base, email, password)
    if not token:
        return 1

    # 3. Upload — the server extracts, merges the DB, and swaps artifacts.
    size_mb = bundle.stat().st_size / 1048576
    print(f"Uploading {bundle.name} ({size_mb:.0f} MB) to {base} ...")
    with open(bundle, "rb") as handle:
        try:
            response = session.post(
                f"{base}/admin/data/upload-bundle",
                data=handle,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/gzip",
                },
                timeout=UPLOAD_TIMEOUT,
            )
        except requests.Timeout:
            print(
                "ERROR: upload timed out. The server may still be applying the bundle; "
                "verify hosted data health before retrying with --skip-build."
            )
            return 1
        except requests.ConnectionError as error:
            print(f"ERROR: upload connection failed ({error.__class__.__name__}).")
            return 1

    if response.status_code != 200:
        print(f"ERROR: upload failed ({response.status_code}): {response.text[:300]}")
        return 1

    result = response.json()
    print(f"OK: {result.get('message')}")
    if isinstance(result.get("db"), dict):
        for table, rows in result["db"].items():
            print(f"  {table}: {rows} rows")
    print(f"  files updated: {result.get('files_updated')}")
    print("The server hot-reloads changed model/data files — picks will grade on next view.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
