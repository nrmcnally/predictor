"""
Tests for display name as a unique, case-insensitive username: registration + profile
update reject duplicates, derived names de-dupe silently, and the migration back-fills
existing accounts to unique names before the unique index is created.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.db import schema  # noqa: E402
from app.services import auth_service  # noqa: E402


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _raises_value_error(fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
        return False
    except ValueError:
        return True


def test_registration_rejects_duplicate_username(tmp_path=None):
    _use_temp_db(tmp_path or tempfile.mkdtemp())
    auth_service.register_user("a@example.com", "password123", "Nate")

    # Exact + different case are both taken.
    assert _raises_value_error(auth_service.register_user, "b@example.com", "password123", "Nate")
    assert _raises_value_error(auth_service.register_user, "c@example.com", "password123", "nate")


def test_derived_username_dedupes_silently(tmp_path=None):
    _use_temp_db(tmp_path or tempfile.mkdtemp())
    # Both derive from the "nate" email local-part; the second gets a suffix.
    a = auth_service.register_user("nate@example.com", "password123")
    b = auth_service.register_user("nate@other.com", "password123")
    assert a["display_name"] == "nate"
    assert b["display_name"] == "nate2"


def test_profile_update_rejects_taken_username(tmp_path=None):
    _use_temp_db(tmp_path or tempfile.mkdtemp())
    auth_service.register_user("a@example.com", "password123", "Ada")
    b = auth_service.register_user("b@example.com", "password123", "Boz")

    assert _raises_value_error(auth_service.update_profile, b["id"], "b@example.com", "Ada")
    # Keeping your own username is fine.
    same = auth_service.update_profile(b["id"], "b@example.com", "Boz")
    assert same["display_name"] == "Boz"


def test_migration_backfills_duplicate_display_names(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    # Simulate a legacy DB with duplicate/blank display names (no unique index yet).
    conn = sqlite3.connect(Path(tmp) / "app.db")
    conn.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL "
        "UNIQUE, display_name TEXT, password_hash TEXT NOT NULL, role TEXT NOT NULL "
        "DEFAULT 'user', is_public INTEGER NOT NULL DEFAULT 0, created_at TEXT)"
    )
    for i, (email, name) in enumerate(
        [("a@x.com", "Nate"), ("b@x.com", "Nate"), ("c@x.com", "")], start=1
    ):
        conn.execute(
            "INSERT INTO users (id, email, display_name, password_hash) VALUES (?, ?, ?, 'h')",
            (i, email, name),
        )
    conn.commit()

    schema.init_db(conn)

    names = [r[0] for r in conn.execute("SELECT display_name FROM users ORDER BY id")]
    assert len(names) == len(set(n.lower() for n in names))  # all unique now
    assert names[0] == "Nate" and names[1] == "Nate2" and names[2] == "c"
    conn.close()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all username tests passed")
