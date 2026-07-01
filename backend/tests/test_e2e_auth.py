"""
End-to-end auth tests — real HTTP requests through the full app (middleware +
routing + dependencies), via FastAPI's TestClient. Email-based accounts.

Runs under pytest, or standalone:  python tests/test_e2e_auth.py
"""

from __future__ import annotations

import sys
import tempfile
import json
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.api_hardening as hardening  # noqa: E402
import app.db.connection as db_connection  # noqa: E402
from app.auth import security  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import users_repository  # noqa: E402


def _client(tmp) -> TestClient:
    db_connection.set_db_path(Path(tmp) / "app.db")
    hardening._limiter._hits.clear()
    return TestClient(app)


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_register_login_me_flow(tmp_path=None):
    client = _client(tmp_path or tempfile.mkdtemp())

    r = client.post("/auth/register", json={"email": "alice@example.com", "password": "password123"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "alice@example.com"
    assert r.json()["user"]["role"] == "user"

    # Duplicate email -> 400; short password -> 422 (Field validation).
    assert client.post("/auth/register", json={"email": "alice@example.com", "password": "password123"}).status_code == 400
    assert client.post("/auth/register", json={"email": "bob@example.com", "password": "short"}).status_code == 422

    r = client.post("/auth/login", json={"email": "alice@example.com", "password": "password123"})
    assert r.status_code == 200
    token = r.json()["token"]

    assert client.post("/auth/login", json={"email": "alice@example.com", "password": "wrongpass123"}).status_code == 401

    assert client.get("/auth/me").status_code == 401
    me = client.get("/auth/me", headers=_bearer(token))
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "alice@example.com"


def test_admin_access_control_and_promotion(tmp_path=None):
    client = _client(tmp_path or tempfile.mkdtemp())

    users_repository.create_user("boss@example.com", security.hash_password("adminpass123"), role="admin")
    client.post("/auth/register", json={"email": "carol@example.com", "password": "password123"})

    admin_token = client.post("/auth/login", json={"email": "boss@example.com", "password": "adminpass123"}).json()["token"]
    user_token = client.post("/auth/login", json={"email": "carol@example.com", "password": "password123"}).json()["token"]

    listing = client.get("/admin/users", headers=_bearer(admin_token))
    assert listing.status_code == 200
    assert len(listing.json()["users"]) >= 2
    assert client.get("/admin/users", headers=_bearer(user_token)).status_code == 403
    assert client.get("/admin/users").status_code == 403

    carol_id = next(u["id"] for u in listing.json()["users"] if u["email"] == "carol@example.com")
    promote = client.post(f"/admin/users/{carol_id}/role", json={"role": "admin"}, headers=_bearer(admin_token))
    assert promote.status_code == 200
    assert client.get("/admin/users", headers=_bearer(user_token)).status_code == 200


def test_user_leaderboard_does_not_expose_emails_to_regular_users(tmp_path=None):
    client = _client(tmp_path or tempfile.mkdtemp())

    client.post(
        "/auth/register",
        json={
            "email": "alice@example.com",
            "password": "password123",
            "display_name": "Alice",
        },
    )
    token = client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "password123"}
    ).json()["token"]
    client.post("/auth/visibility", json={"is_public": True}, headers=_bearer(token))

    client.post(
        "/auth/register",
        json={
            "email": "bob@example.com",
            "password": "password123",
            "display_name": "Bob",
        },
    )
    bob_token = client.post(
        "/auth/login", json={"email": "bob@example.com", "password": "password123"}
    ).json()["token"]
    client.post("/auth/visibility", json={"is_public": True}, headers=_bearer(bob_token))

    response = client.get("/leaderboard/users", headers=_bearer(token))

    assert response.status_code == 200
    rows = response.json()["leaderboard"]
    payload = json.dumps(response.json())
    assert "alice@example.com" not in payload
    assert "bob@example.com" not in payload
    assert all("email" not in row for row in rows)
    assert {row["display_name"] for row in rows} >= {"Alice", "Bob"}

    legacy = client.get("/leaderboard/predictors", headers=_bearer(token))
    assert legacy.status_code == 200
    assert "example.com" not in json.dumps(legacy.json())


def test_change_password_endpoint(tmp_path=None):
    client = _client(tmp_path or tempfile.mkdtemp())

    client.post("/auth/register", json={"email": "erin@example.com", "password": "password123"})
    token = client.post("/auth/login", json={"email": "erin@example.com", "password": "password123"}).json()["token"]

    # Wrong current -> 400.
    bad = client.post("/auth/change-password", json={"current_password": "nope", "new_password": "newpassword123"}, headers=_bearer(token))
    assert bad.status_code == 400
    # Correct -> 200, and the new password logs in.
    ok = client.post("/auth/change-password", json={"current_password": "password123", "new_password": "newpassword123"}, headers=_bearer(token))
    assert ok.status_code == 200
    assert client.post("/auth/login", json={"email": "erin@example.com", "password": "newpassword123"}).status_code == 200


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
            client.post("/auth/login", json={"email": "x@example.com", "password": "y12345678"}).status_code
            for _ in range(6)
        ]
        assert 429 in statuses
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
