"""
Pull a backup of the LIVE server's user data down to this machine.

    python deploy/backup_server.py                 # app "fightiq"
    python deploy/backup_server.py --app myapp

Accounts, picks, friendships, and avatars exist ONLY on the server volume — the
deploy bundle flows the other way. Fly keeps ~5 days of volume snapshots; this gives
you an off-site copy you control. Run it before risky changes and after big events.

What it does (via the Fly CLI, so `fly auth login` must have been run):
  1. server-side: a CONSISTENT SQLite backup (sqlite3 backup API — safe while the
     app is serving), plus the avatars directory, tarred into one file;
  2. downloads the tarball to backups/fightiq_backup_<UTC>.tar.gz;
  3. cleans up the server-side temp files.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKUPS_DIR = REPO_ROOT / "backups"

SERVER_SCRIPT = (
    "import sqlite3, shutil, os, tarfile; "
    "os.makedirs('/data/_backup', exist_ok=True); "
    "src = sqlite3.connect('/data/data/app.db'); "
    "dst = sqlite3.connect('/data/_backup/app.db'); "
    "src.backup(dst); dst.close(); src.close(); "
    "shutil.copytree('/data/data/avatars', '/data/_backup/avatars', dirs_exist_ok=True) "
    "if os.path.isdir('/data/data/avatars') else None; "
    "tar = tarfile.open('/data/_backup/export.tar.gz', 'w:gz'); "
    "tar.add('/data/_backup/app.db', arcname='app.db'); "
    "[tar.add(f'/data/_backup/avatars/{n}', arcname=f'avatars/{n}') "
    " for n in (os.listdir('/data/_backup/avatars') if os.path.isdir('/data/_backup/avatars') else [])]; "
    "tar.close(); print('server backup ready')"
)


def _flyctl() -> str:
    for name in ("flyctl", "fly"):
        found = shutil.which(name)
        if found:
            return found
    default = Path.home() / ".fly" / "bin" / "flyctl.exe"
    if default.is_file():
        return str(default)
    print("ERROR: flyctl not found — install it or add it to PATH.")
    sys.exit(1)


def _run(args: list[str]) -> str:
    """Run flyctl and return combined output. On Windows, `fly ssh console` can
    report a bogus exit code ("The handle is invalid") without a real TTY, so
    callers judge success by OUTCOMES (expected output / downloaded file), not codes."""
    result = subprocess.run(args, capture_output=True, text=True)
    output = (result.stdout or "") + (result.stderr or "")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", default="fightiq")
    args = parser.parse_args()

    fly = _flyctl()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    BACKUPS_DIR.mkdir(exist_ok=True)
    out = BACKUPS_DIR / f"{args.app}_backup_{stamp}.tar.gz"

    print("1/3 building a consistent backup on the server...")
    output = _run([fly, "ssh", "console", "--app", args.app, "-C", f'python -c "{SERVER_SCRIPT}"'])
    if "server backup ready" not in output:
        print(output.strip()[-600:])
        print("ERROR: the server-side backup step did not confirm. Aborting.")
        return 1

    print("2/3 downloading...")
    _run([fly, "ssh", "sftp", "get", "/data/_backup/export.tar.gz", str(out), "--app", args.app])
    if not out.is_file() or out.stat().st_size == 0:
        print("ERROR: download failed — no local backup file was written.")
        return 1

    print("3/3 cleaning up server temp files...")
    _run([fly, "ssh", "console", "--app", args.app, "-C", "rm -rf /data/_backup"])

    print(f"\nBackup saved: {out} ({out.stat().st_size / 1024:.0f} KB)")
    print("Contains app.db (accounts/picks/friendships) + avatars/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
