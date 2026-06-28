"""
Tests for Phase 2 auth: password hashing, signed tokens, register/login, the
admin seed, and the require_admin gate.

Runs under pytest, or standalone:  python tests/test_auth.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.auth import dependencies, security  # noqa: E402
from app.repositories import users_repository  # noqa: E402
from app.services import auth_service  # noqa: E402
from fastapi import HTTPException  # noqa: E402


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _raises_value_error(fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
        return False
    except ValueError:
        return True


# --- password hashing ---------------------------------------------------------

def test_password_hash_verifies_and_is_salted():
    stored = security.hash_password("hunter2pass")
    assert security.verify_password("hunter2pass", stored)
    assert not security.verify_password("wrong-password", stored)
    # Salted: hashing the same password twice yields different stored values.
    assert security.hash_password("hunter2pass") != stored


# --- tokens -------------------------------------------------------------------

def test_token_roundtrip_and_tamper_rejected():
    token = security.create_token({"sub": 7, "role": "admin"})
    payload = security.decode_token(token)
    assert payload["sub"] == 7 and payload["role"] == "admin"
    assert security.decode_token(token + "tamper") is None
    assert security.decode_token("not.a.token") is None


def test_expired_token_rejected():
    token = security.create_token({"sub": 1}, ttl_seconds=-5)  # already expired
    assert security.decode_token(token) is None


# --- register / authenticate --------------------------------------------------

def test_register_and_authenticate(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    user = auth_service.register_user("alice", "password123")
    assert user["username"] == "alice"
    assert user["role"] == "user"
    assert "password_hash" not in user  # never leak the hash

    result = auth_service.authenticate("alice", "password123")
    assert "token" in result
    assert result["user"]["username"] == "alice"
    assert security.decode_token(result["token"])["sub"] == user["id"]


def test_register_validation_and_duplicates(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    assert _raises_value_error(auth_service.register_user, "ab", "password123")  # short username
    assert _raises_value_error(auth_service.register_user, "alice", "short")     # short password

    auth_service.register_user("bob", "password123")
    assert _raises_value_error(auth_service.register_user, "bob", "password123")  # duplicate


def test_authenticate_bad_credentials(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    auth_service.register_user("carol", "password123")
    assert _raises_value_error(auth_service.authenticate, "carol", "wrong-password")
    assert _raises_value_error(auth_service.authenticate, "ghost", "password123")


# --- admin seed ---------------------------------------------------------------

def test_seed_admin_from_env_is_idempotent(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    os.environ["ADMIN_USERNAME"] = "root"
    os.environ["ADMIN_PASSWORD"] = "rootpassword"
    try:
        auth_service.ensure_seed_admin()
        seeded = users_repository.get_by_username("root")
        assert seeded is not None and seeded["role"] == "admin"
        assert auth_service.admin_exists()

        auth_service.ensure_seed_admin()  # idempotent
        assert users_repository.count_admins() == 1
    finally:
        os.environ.pop("ADMIN_USERNAME", None)
        os.environ.pop("ADMIN_PASSWORD", None)


# --- require_admin gate -------------------------------------------------------

def test_require_admin_allows_admin_jwt(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    os.environ.pop("ADMIN_TOKEN", None)

    admin = users_repository.create_user(
        "admin1", security.hash_password("password123"), role="admin"
    )
    token = security.create_token({"sub": admin["id"], "role": "admin"})

    result = dependencies.require_admin(authorization=f"Bearer {token}", x_admin_token=None)
    assert result["role"] == "admin"


def test_require_admin_denies_regular_user(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    os.environ.pop("ADMIN_TOKEN", None)

    # An admin exists, so the dev-open path is off.
    users_repository.create_user("admin1", security.hash_password("password123"), role="admin")
    user = users_repository.create_user("user1", security.hash_password("password123"), role="user")
    token = security.create_token({"sub": user["id"], "role": "user"})

    try:
        dependencies.require_admin(authorization=f"Bearer {token}", x_admin_token=None)
        assert False, "regular user should be denied"
    except HTTPException as error:
        assert error.status_code == 403


def test_require_admin_dev_open_when_unconfigured(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)
    os.environ.pop("ADMIN_TOKEN", None)

    # No admin account + no ADMIN_TOKEN -> open for local dev.
    assert dependencies.require_admin(authorization=None, x_admin_token=None) is None


def test_require_admin_legacy_token(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    _use_temp_db(tmp)

    os.environ["ADMIN_TOKEN"] = "secret-token"
    try:
        assert dependencies.require_admin(authorization=None, x_admin_token="secret-token") is None
        try:
            dependencies.require_admin(authorization=None, x_admin_token="wrong-token")
            assert False, "wrong token should be denied"
        except HTTPException as error:
            assert error.status_code == 403
    finally:
        os.environ.pop("ADMIN_TOKEN", None)


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
