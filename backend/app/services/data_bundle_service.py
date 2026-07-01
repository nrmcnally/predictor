from __future__ import annotations

import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from app.db import connection
from app.db.bundle_sync import sync_shared_tables

# Applies an uploaded deploy bundle (deploy/make_bundle.py output) to THIS instance:
# merges the DB's shared tables (accounts/picks/friendships are never touched) and
# overwrites the global model/CSV artifacts. This is the HTTP-upload counterpart of
# deploy/update_from_bundle.sh, so updates need no SSH access.

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Bundle members may only land in these top-level dirs (defense in depth on top of
# tarfile's "data" filter, which already blocks absolute paths and traversal).
_ALLOWED_TOPLEVEL = {"data", "models"}


def apply_bundle(tar_path: Path | str, backend_root: Path | None = None) -> dict[str, Any]:
    """Extract + apply a bundle tar.gz. Returns a summary of what changed."""
    tar_path = Path(tar_path)
    root = Path(backend_root) if backend_root else BACKEND_ROOT

    with tempfile.TemporaryDirectory(prefix="fightiq_bundle_") as tmp:
        incoming = Path(tmp)
        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar.getmembers():
                top = member.name.split("/", 1)[0]
                if top not in _ALLOWED_TOPLEVEL:
                    raise ValueError(f"Unexpected path in bundle: {member.name}")
            tar.extractall(incoming, filter="data")

        summary: dict[str, Any] = {"db": None, "files_updated": 0}

        # 1. The DB: merge shared tables into the live DB (or install it wholesale on
        #    a first boot with no DB yet).
        bundle_db = incoming / "data" / "app.db"
        live_db = connection.get_db_path()
        if bundle_db.is_file():
            if live_db.is_file():
                summary["db"] = sync_shared_tables(live_db, bundle_db)
            else:
                live_db.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(bundle_db, live_db)
                summary["db"] = "installed (first boot)"
            bundle_db.unlink()

        # 2. Everything else (models, raw/processed CSVs) is global: overwrite in place.
        for path in sorted(incoming.rglob("*")):
            if not path.is_file():
                continue
            destination = root / path.relative_to(incoming)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            summary["files_updated"] += 1

    return summary
