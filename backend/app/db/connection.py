from __future__ import annotations

import os
import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PROD_DB_PATH = DATA_DIR / "app.db"
DEMO_DB_PATH = DATA_DIR / "app.demo.db"

_TRUTHY = {"1", "true", "yes", "on"}


def _demo_requested() -> bool:
    return os.environ.get("FIGHTIQ_DEMO", "").strip().lower() in _TRUTHY


def _resolve_default_db() -> Path:
    """Prod by default; FIGHTIQ_DEMO=1 -> an isolated sandbox DB; FIGHTIQ_DB_PATH wins."""
    override = os.environ.get("FIGHTIQ_DB_PATH", "").strip()
    if override:
        return Path(override)
    return DEMO_DB_PATH if _demo_requested() else PROD_DB_PATH


DEFAULT_DB_PATH = _resolve_default_db()

# Module-level so tests can point the whole data layer at a temp DB via set_db_path().
_db_path: Path = DEFAULT_DB_PATH


def is_demo() -> bool:
    """True when the live DB is the isolated demo sandbox (FIGHTIQ_DEMO)."""
    return _db_path == DEMO_DB_PATH


def ensure_demo_db() -> None:
    """Seed the demo sandbox from prod on first run so it has the real fight/model data
    while keeping accounts + picks isolated from production. No-op outside demo mode."""
    if _db_path == DEMO_DB_PATH and not DEMO_DB_PATH.exists() and PROD_DB_PATH.exists():
        DEMO_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROD_DB_PATH, DEMO_DB_PATH)


def get_db_path() -> Path:
    return _db_path


def set_db_path(path: Path | str) -> None:
    """Point the data layer at a different SQLite file. Used by tests."""
    global _db_path
    _db_path = Path(path)


def connect() -> sqlite3.Connection:
    """Open a connection in WAL mode (concurrent readers + one writer), rows as
    dict-like ``sqlite3.Row``. Connect-per-operation keeps it thread-safe under
    FastAPI without a shared connection."""
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Yield a connection wrapped in one atomic transaction: commit on success,
    roll back on any exception, always close."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
