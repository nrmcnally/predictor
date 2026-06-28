"""
End-to-end auth tests — real HTTP requests through the full app (middleware +
routing + dependencies), via FastAPI's TestClient.

Covers: register/login/me, validation + error codes, admin access control,
fresh-role loading after promotion, security headers, and rate limiting.

Runs under pytest, or standalone:  python tests/test_e2e_auth.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.api_hardening as hardening  # noqa: E402
import app.db.connection as db_connection  # noqa: E402
from app.auth import security  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import users_repository  # noqa: E402


def _client(tmp) -> TestClient:
    """A TestClient pointed at a fresh temp DB with a clean rate-limit state."""
    db_connection.set_db_path(Path(tmp) / "app.db")
    hardening._limiter._hits.clear()
    return TestClient(app)


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_register_login_me_flow(tmp_path=None):
    client = _client(tmp_path or tempfile.mkdtemp())

    r = client.post("/auth/register", json={"username": "alice", "password": "password123"})
    assert r.status_code == 200
    assert r.json()["user"]["username"] == "alice"
    assert r.json()["user"]["role"] == "user"

    # Duplicate username -> 400; short password -> 422 (Field validation).
    assert client.post("/auth/register", json={"username": "alice", "password": "password123"}).status_code == 400
    assert client.post("/auth/register", json={"username": "bobby", "password": "short"}).status_code == 422

    # Login -> token.
    r = client.post("/auth/login", json={"username": "alice", "password": "password123"})
    assert r.status_code == 200
    token = r.json()["token"]

    # Wrong password -> 401.
    assert client.post("/auth/login", json={"username": "alice", "password": "wrongpass123"}).status_code == 401

    # /auth/me requires a valid token.
    assert client.get("/auth/me").status_code == 401
    me = client.get("/auth/me", headers=_bearer(token))
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "alice"


def test_admin_access_control_and_promotion(tmp_path=None):
    client = _client(tmp_path or tempfile.mkdtemp())

    # Seed an admin directly + register a regular user.
    users_repository.create_user("boss", security.hash_password("adminpass123"), role="admin")
    client.post("/auth/register", json={"username": "carol", "password": "password123"})

    admin_token = client.post("/auth/login", json={"username": "boss", "password": "adminpass123"}).json()["token"]
    user_token = client.post("/auth/login", json={"username": "carol", "password": "password123"}).json()["token"]

    # Admin can list users; regular user and anonymous are denied (an admin exists).
    listing = client.get("/admin/users", headers=_bearer(admin_token))
    assert listing.status_code == 200
    assert len(listing.json()["users"]) >= 2
    assert client.get("/admin/users", headers=_bearer(user_token)).status_code == 403
    assert client.get("/admin/users").status_code == 403

    # Promote carol; her existing token now grants admin (role loaded fresh from DB).
    carol_id = next(u["id"] for u in listing.json()["users"] if u["username"] == "carol")
    promote = client.post(f"/admin/users/{carol_id}/role", json={"role": "admin"}, headers=_bearer(admin_token))
    assert promote.status_code == 200
    assert client.get("/admin/users", headers=_bearer(user_token)).status_code == 200


def test_security_headers_present(tmp_path=None):
    client = _client(tmp_path or tempfile.mkdtemp())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"


def test_auth_rate_limit_returns_429(tmp_path=None):
    client = _client(tmp_path or tempfile.mkdtemp())

    original = hardening.AUTH_LIMIT_PER_MINUTE
    hardening.AUTH_LIMIT_PER_MINUTE = 3
    hardening._limiter._hits.clear()
    try:
        statuses = [
            client.post("/auth/login", json={"username": "x", "password": "y12345678"}).status_code
            for _ in range(6)
        ]
        assert 429 in statuses  # the stricter auth bucket trips
    finally:
        hardening.AUTH_LIMIT_PER_MINUTE = original
        hardening._limiter._hits.clear()


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
