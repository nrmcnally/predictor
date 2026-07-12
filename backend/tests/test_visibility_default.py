"""
Tests for opt-out leaderboard visibility (2026-07-13): new accounts are public
by default, the one-shot v1 migration flips pre-existing accounts, and a
deliberate opt-out survives restarts (the migration never re-runs).

Runs under pytest, or standalone:  python tests/test_visibility_default.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.db import schema  # noqa: E402
from app.repositories import users_repository  # noqa: E402


def _fresh_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _create(email):
    return users_repository.create_user(
        email=email, display_name=email.split("@")[0], password_hash="x"
    )


def test_new_accounts_are_public_by_default():
    with tempfile.TemporaryDirectory() as tmp:
        _fresh_db(tmp)
        user = _create("ada@example.com")
        assert users_repository.get_by_id(user["id"])["is_public"]
        assert any(
            u["id"] == user["id"] for u in users_repository.list_public_users()
        )


def test_opt_out_survives_restarts():
    with tempfile.TemporaryDirectory() as tmp:
        _fresh_db(tmp)
        user = _create("boz@example.com")
        users_repository.set_visibility(user["id"], False)

        # Simulate a server restart: init_db runs again on a fresh connection.
        with db_connection.transaction() as conn:
            schema.init_db(conn)

        assert not users_repository.get_by_id(user["id"])["is_public"]


def test_v1_migration_flips_pre_existing_accounts_once():
    with tempfile.TemporaryDirectory() as tmp:
        _fresh_db(tmp)
        user = _create("cid@example.com")

        # Recreate the pre-migration world: opted-out rows, version 0.
        with db_connection.transaction() as conn:
            conn.execute("UPDATE users SET is_public = 0")
            conn.execute("PRAGMA user_version = 0")

        with db_connection.transaction() as conn:
            schema.init_db(conn)

        assert users_repository.get_by_id(user["id"])["is_public"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all visibility tests passed")
