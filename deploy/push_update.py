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
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_bundle import DEFAULT_OUT, build_bundle  # noqa: E402

TIMEOUT_SECONDS = 300  # 44MB over a home upload link can take a couple of minutes


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
    login = requests.post(
        f"{base}/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    if login.status_code != 200:
        print(f"ERROR: login failed ({login.status_code}): {login.text[:200]}")
        return 1
    token = login.json()["token"]

    # 3. Upload — the server extracts, merges the DB, and swaps artifacts.
    size_mb = bundle.stat().st_size / 1048576
    print(f"Uploading {bundle.name} ({size_mb:.0f} MB) to {base} ...")
    with open(bundle, "rb") as handle:
        response = requests.post(
            f"{base}/admin/data/upload-bundle",
            data=handle,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/gzip",
            },
            timeout=TIMEOUT_SECONDS,
        )

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
