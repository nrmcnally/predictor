"""
Tests for hosted-mode hardening: the AUTH_SECRET boot check, the require-auth
middleware wall, the registration kill-switch, the credential-stripped demo seed,
and the proxy-aware/bounded rate limiter.

Runs under pytest, or standalone:  python tests/test_hosted_mode.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.api_hardening as hardening  # noqa: E402
import app.db.connection as db_connection  # noqa: E402
from app import runtime_config  # noqa: E402
from app.db import schema  # noqa: E402
from app.main import app  # noqa: E402


def _set_env(**values):
    """Set env vars, returning a restore function."""
    saved = {key: os.environ.get(key) for key in values}
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    def restore():
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    return restore


def _client(tmp) -> TestClient:
    db_connection.set_db_path(Path(tmp) / "app.db")
    hardening._limiter._hits.clear()
    return TestClient(app)


# --- AUTH_SECRET boot check -----------------------------------------------------

def test_hosted_boot_requires_real_secret():
    restore = _set_env(FIGHTIQ_HOSTED="1", AUTH_SECRET=None)
    try:
        for bad in (None, runtime_config.DEV_AUTH_SECRET, "short"):
            inner = _set_env(AUTH_SECRET=bad)
            try:
                try:
                    runtime_config.assert_hosted_config()
                    raise AssertionError(f"expected RuntimeError for secret={bad!r}")
                except RuntimeError:
                    pass
            finally:
                inner()

        ok = _set_env(AUTH_SECRET="x" * 48)
        try:
            runtime_config.assert_hosted_config()  # must not raise
        finally:
            ok()
    finally:
        restore()

    # Not hosted -> no check at all.
    runtime_config.assert_hosted_config()


# --- require-auth wall ------------------------------------------------------------

def test_require_auth_walls_data_endpoints(tmp_path=None):
    client = _client(tmp_path or tempfile.mkdtemp())
    restore = _set_env(REQUIRE_AUTH="1")
    try:
        # Public shell stays open.
        assert client.get("/health").status_code == 200
        assert client.post(
            "/auth/register",
            json={"email": "wall@example.com", "password": "password123", "display_name": "Wall"},
        ).status_code == 200
        token = client.post(
            "/auth/login", json={"email": "wall@example.com", "password": "password123"}
        ).json()["token"]

        # Data endpoints are walled anonymously, open with a token.
        assert client.get("/future-cards").status_code == 401
        assert client.get("/recent-cards").status_code == 401
        assert client.get("/docs").status_code == 401
        # The schema is a recon map; the ".json" extension must not open the wall.
        assert client.get("/openapi.json").status_code == 401
        authed = client.get("/future-cards", headers={"Authorization": f"Bearer {token}"})
        assert authed.status_code == 200

        # Static-looking paths pass the wall (404 from routing, not 401).
        assert client.get("/vite.svg").status_code != 401
    finally:
        restore()

    # Flag off -> anonymous data access again (local dev behavior).
    assert client.get("/future-cards").status_code == 200


def test_registration_kill_switch(tmp_path=None):
    client = _client(tmp_path or tempfile.mkdtemp())
    restore = _set_env(ALLOW_REGISTRATION="0")
    try:
        response = client.post(
            "/auth/register", json={"email": "late@example.com", "password": "password123"}
        )
        assert response.status_code == 403
    finally:
        restore()


# --- demo seed strips personal data ----------------------------------------------

def test_demo_seed_strips_credentials():
    tmp = Path(tempfile.mkdtemp())
    fake_prod = tmp / "prod.db"
    fake_demo = tmp / "demo.db"

    conn = sqlite3.connect(fake_prod)
    schema.init_db(conn)
    conn.execute(
        "INSERT INTO users (email, display_name, password_hash) VALUES (?, ?, ?)",
        ("real@example.com", "Real", "pbkdf2_sha256$1$aa$bb"),
    )
    conn.execute(
        "INSERT INTO event_fights (fight_url, fighter_1, fighter_2, winner) "
        "VALUES ('u1', 'A', 'B', 'A')"
    )
    conn.commit()
    conn.close()

    saved = (db_connection.PROD_DB_PATH, db_connection.DEMO_DB_PATH, db_connection._db_path)
    try:
        db_connection.PROD_DB_PATH = fake_prod
        db_connection.DEMO_DB_PATH = fake_demo
        db_connection._db_path = fake_demo
        db_connection.ensure_demo_db()
    finally:
        (db_connection.PROD_DB_PATH, db_connection.DEMO_DB_PATH, db_connection._db_path) = saved

    check = sqlite3.connect(fake_demo)
    assert check.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    assert check.execute("SELECT COUNT(*) FROM event_fights").fetchone()[0] == 1
    # The raw file must not contain the credentials either (VACUUM ran).
    assert b"real@example.com" not in fake_demo.read_bytes()
    check.close()


# --- rate limiter -----------------------------------------------------------------

def _fake_request(host="9.9.9.9", forwarded=None):
    headers = {"x-forwarded-for": forwarded} if forwarded else {}
    return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers)


def test_client_ip_honors_proxy_only_when_trusted():
    request = _fake_request(host="10.0.0.1", forwarded="6.6.6.6, 203.0.113.9")

    restore = _set_env(TRUST_PROXY=None)
    try:
        assert hardening._client_ip(request) == "10.0.0.1"  # header ignored
    finally:
        restore()

    restore = _set_env(TRUST_PROXY="1")
    try:
        # Last hop = appended by OUR proxy; earlier entries are client-spoofable.
        assert hardening._client_ip(request) == "203.0.113.9"
        assert hardening._client_ip(_fake_request(host="10.0.0.1")) == "10.0.0.1"
    finally:
        restore()


def test_rate_limiter_prunes_stale_keys():
    limiter = hardening.RateLimiter()
    saved = hardening.MAX_TRACKED_KEYS
    hardening.MAX_TRACKED_KEYS = 10
    try:
        # 50 one-shot "IPs" whose hits all expire immediately (window in the past).
        # Without pruning the dict would hold all 50 keys; with it, crossing the cap
        # sweeps stale keys, so the dict stays bounded near MAX_TRACKED_KEYS.
        for i in range(50):
            limiter.allow((f"ip{i}", "global"), limit=5, window_seconds=-1)
        limiter.allow(("fresh", "global"), limit=5, window_seconds=60)
        assert len(limiter._hits) <= hardening.MAX_TRACKED_KEYS + 1
    finally:
        hardening.MAX_TRACKED_KEYS = saved


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all hosted-mode tests passed")
