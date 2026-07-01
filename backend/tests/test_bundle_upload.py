"""
E2E tests for the remote data-update endpoint: an admin uploads a bundle tar.gz over
HTTP; the server merges shared tables (preserving accounts/picks), writes model
artifacts, rejects non-admins, and refuses bundles with unexpected paths.
"""

from __future__ import annotations

import io
import sqlite3
import sys
import tarfile
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.api_hardening as hardening  # noqa: E402
import app.db.connection as db_connection  # noqa: E402
import app.services.data_bundle_service as bundle_service  # noqa: E402
from app.auth import security  # noqa: E402
from app.db import schema  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import users_repository  # noqa: E402


def _client(tmp: Path) -> TestClient:
    db_connection.set_db_path(tmp / "app.db")
    hardening._limiter._hits.clear()
    return TestClient(app)


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_bundle_bytes(tmp: Path) -> bytes:
    """A tiny but real bundle: a DB with fresh event_fights + one model file."""
    bundle_db = tmp / "bundle_source.db"
    conn = sqlite3.connect(bundle_db)
    schema.init_db(conn)
    conn.execute(
        "INSERT INTO event_fights (fight_url, fighter_1, fighter_2, winner) "
        "VALUES ('u/fresh', 'A', 'B', 'A')"
    )
    conn.commit()
    conn.close()

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        tar.add(bundle_db, arcname="data/app.db")
        model = tmp / "best_winner_model.joblib"
        model.write_bytes(b"fake-model-bytes")
        tar.add(model, arcname="models/best_winner_model.joblib")
    return buffer.getvalue()


def test_upload_bundle_merges_and_writes_artifacts(tmp_path=None):
    tmp = Path(tmp_path or tempfile.mkdtemp())
    client = _client(tmp)

    # Live state: an admin, a regular user with a pick, and a stale result.
    users_repository.create_user("boss@example.com", security.hash_password("adminpass123"), role="admin")
    client.post("/auth/register", json={"email": "fan@example.com", "password": "password123", "display_name": "Fan"})
    conn = sqlite3.connect(db_connection.get_db_path())
    conn.execute(
        "INSERT INTO user_predictions (user_id, fight_url, picked_fighter, status) "
        "VALUES (2, 'u/f1', 'A', 'open')"
    )
    conn.execute(
        "INSERT INTO event_fights (fight_url, fighter_1, fighter_2, winner) "
        "VALUES ('u/stale', 'X', 'Y', 'X')"
    )
    conn.commit()
    conn.close()

    admin_token = client.post(
        "/auth/login", json={"email": "boss@example.com", "password": "adminpass123"}
    ).json()["token"]
    user_token = client.post(
        "/auth/login", json={"email": "fan@example.com", "password": "password123"}
    ).json()["token"]

    body = _make_bundle_bytes(tmp)

    # Non-admin -> 403; unauthenticated -> 403.
    assert client.post("/admin/data/upload-bundle", content=body, headers=_bearer(user_token)).status_code == 403
    assert client.post("/admin/data/upload-bundle", content=body).status_code == 403
    # Empty body -> 400.
    assert client.post("/admin/data/upload-bundle", content=b"", headers=_bearer(admin_token)).status_code == 400

    # Redirect artifact writes away from the real backend tree.
    saved_root = bundle_service.BACKEND_ROOT
    bundle_service.BACKEND_ROOT = tmp / "server_root"
    try:
        response = client.post(
            "/admin/data/upload-bundle", content=body, headers=_bearer(admin_token)
        )
    finally:
        bundle_service.BACKEND_ROOT = saved_root

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["db"]["event_fights"] == 1
    assert result["files_updated"] == 1  # the model file

    # Shared table replaced; personal rows preserved.
    check = sqlite3.connect(db_connection.get_db_path())
    urls = {r[0] for r in check.execute("SELECT fight_url FROM event_fights")}
    assert urls == {"u/fresh"}
    assert check.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2
    assert check.execute("SELECT COUNT(*) FROM user_predictions").fetchone()[0] == 1
    check.close()
    # Model artifact landed relative to the (redirected) backend root.
    assert (tmp / "server_root" / "models" / "best_winner_model.joblib").read_bytes() == b"fake-model-bytes"


def test_upload_rejects_unexpected_paths(tmp_path=None):
    tmp = Path(tmp_path or tempfile.mkdtemp())
    client = _client(tmp)
    users_repository.create_user("boss@example.com", security.hash_password("adminpass123"), role="admin")
    token = client.post(
        "/auth/login", json={"email": "boss@example.com", "password": "adminpass123"}
    ).json()["token"]

    evil = io.BytesIO()
    with tarfile.open(fileobj=evil, mode="w:gz") as tar:
        payload = tmp / "evil.txt"
        payload.write_text("nope")
        tar.add(payload, arcname="app/main.py")  # outside data/ and models/

    response = client.post(
        "/admin/data/upload-bundle", content=evil.getvalue(), headers=_bearer(token)
    )
    assert response.status_code == 400
    assert "Unexpected path" in response.text


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all bundle-upload tests passed")
