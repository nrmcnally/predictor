"""
Tests for the admin-control batch: evaluation endpoints are admin-only, the hosted
instance refuses server-side Data Ops updates, registration pause/unpause works at
runtime, last-login is tracked, avatars are validated + re-encoded, and friends'
upcoming picks stay hidden until you commit your own.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.api_hardening as hardening  # noqa: E402
import app.db.connection as db_connection  # noqa: E402
import app.services.avatar_service as avatar_service  # noqa: E402
from app.auth import security  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import future_cards_repository, users_repository  # noqa: E402
from app.services import auth_service, friends_compare_service, friends_service, predictions_service  # noqa: E402


def _client(tmp: Path) -> TestClient:
    db_connection.set_db_path(tmp / "app.db")
    hardening._limiter._hits.clear()
    return TestClient(app)


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _admin_and_user(client):
    users_repository.create_user("boss@example.com", security.hash_password("adminpass123"), role="admin")
    client.post("/auth/register", json={"email": "u@example.com", "password": "password123", "display_name": "U"})
    admin = client.post("/auth/login", json={"email": "boss@example.com", "password": "adminpass123"}).json()["token"]
    user = client.post("/auth/login", json={"email": "u@example.com", "password": "password123"}).json()["token"]
    return admin, user


def test_evaluations_are_admin_only(tmp_path=None):
    client = _client(Path(tmp_path or tempfile.mkdtemp()))
    admin, user = _admin_and_user(client)

    for path in ("/model-snapshot-evaluation", "/clv-evaluation", "/model-vs-market-evaluation"):
        assert client.get(path, headers=_bearer(user)).status_code == 403, path
        assert client.get(path, headers=_bearer(admin)).status_code == 200, path
    # The data-age banner source stays available to everyone.
    assert client.get("/data-quality", headers=_bearer(user)).status_code == 200


def test_hosted_blocks_server_side_update(tmp_path=None):
    client = _client(Path(tmp_path or tempfile.mkdtemp()))
    admin, _ = _admin_and_user(client)

    # Only the hosted flag — changing AUTH_SECRET mid-test would invalidate the token.
    os.environ["FIGHTIQ_HOSTED"] = "1"
    try:
        response = client.post("/admin/update/start", headers=_bearer(admin))
        assert response.status_code == 503
        assert "push_update" in response.text
    finally:
        os.environ.pop("FIGHTIQ_HOSTED", None)


def test_registration_toggle_runtime(tmp_path=None):
    client = _client(Path(tmp_path or tempfile.mkdtemp()))
    admin, user = _admin_and_user(client)

    listing = client.get("/admin/users", headers=_bearer(admin)).json()
    assert listing["registration_open"] is True
    assert any(u.get("last_login_at") for u in listing["users"])  # login was tracked

    # Non-admin can't flip it; admin pauses it; registration then 403s; unpause restores.
    assert client.post("/admin/settings/registration", json={"open": False}, headers=_bearer(user)).status_code == 403
    assert client.post("/admin/settings/registration", json={"open": False}, headers=_bearer(admin)).status_code == 200
    assert client.post("/auth/register", json={"email": "late@example.com", "password": "password123"}).status_code == 403
    client.post("/admin/settings/registration", json={"open": True}, headers=_bearer(admin))
    assert client.post("/auth/register", json={"email": "late@example.com", "password": "password123"}).status_code == 200


def _png_bytes(size=(600, 400), color=(200, 30, 60)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_avatar_upload_reencodes_and_serves(tmp_path=None):
    tmp = Path(tmp_path or tempfile.mkdtemp())
    client = _client(tmp)
    _, user = _admin_and_user(client)

    saved_dir = avatar_service.AVATARS_DIR
    avatar_service.AVATARS_DIR = tmp / "avatars"
    try:
        # Junk that isn't an image -> 400. Oversize -> 413. Valid -> 200.
        assert client.post("/auth/avatar", content=b"not an image", headers=_bearer(user)).status_code == 400
        assert client.post(
            "/auth/avatar", content=b"x" * (avatar_service.MAX_UPLOAD_BYTES + 1), headers=_bearer(user)
        ).status_code == 413
        assert client.post("/auth/avatar", content=_png_bytes(), headers=_bearer(user)).status_code == 200

        # Served re-encoded at the fixed size — never the original bytes.
        me = client.get("/auth/me", headers=_bearer(user)).json()["user"]
        served = client.get(f"/avatars/{me['id']}.png")
        assert served.status_code == 200
        image = Image.open(io.BytesIO(served.content))
        assert image.size == (avatar_service.AVATAR_SIZE, avatar_service.AVATAR_SIZE)

        # Delete works; missing avatar -> 404.
        assert client.delete("/auth/avatar", headers=_bearer(user)).json()["removed"] is True
        assert client.get(f"/avatars/{me['id']}.png").status_code == 404
    finally:
        avatar_service.AVATARS_DIR = saved_dir


def _seed_two_fight_card():
    event = {
        "event_id": "evt1", "event_name": "UFC 999", "event_date": "December 31, 2099",
        "event_location": "LV", "event_url": "u",
    }
    future_cards_repository.replace_upcoming_events([event])
    future_cards_repository.replace_upcoming_fights([
        {**event, "fight_url": f"http://ufcstats.com/fight-details/f{i}",
         "fighter_1": f"A{i}", "fighter_2": f"B{i}", "weight_class": "LW"}
        for i in range(2)
    ])


def test_upcoming_compare_hides_friend_pick_until_committed(tmp_path=None):
    db_connection.set_db_path(Path(tmp_path or tempfile.mkdtemp()) / "app.db")
    me = auth_service.register_user("me@example.com", "password123", "Me")
    pal = auth_service.register_user("pal@example.com", "password123", "Pal")
    friends_service.send_friend_request(me["id"], "Pal")
    fid = friends_service.get_overview(pal["id"])["incoming"][0]["friendship_id"]
    friends_service.respond_to_request(pal["id"], fid, True)

    _seed_two_fight_card()
    # Pal picks both fights; I pick only fight 0.
    predictions_service.make_prediction(pal["id"], "http://ufcstats.com/fight-details/f0", "A0")
    predictions_service.make_prediction(pal["id"], "http://ufcstats.com/fight-details/f1", "B1")
    predictions_service.make_prediction(me["id"], "http://ufcstats.com/fight-details/f0", "A0")

    upcoming = friends_compare_service.build_compare(me["id"], pal["id"])["upcoming"]
    assert len(upcoming) == 1
    fights = {f["fighter_1"]: f for f in upcoming[0]["fights"]}

    # Fight 0: I committed -> their pick revealed, agreement computed.
    assert fights["A0"]["their_pick"] == "A0"
    assert fights["A0"]["agree"] is True
    # Fight 1: I haven't picked -> hidden flag; their pick/method never leak.
    assert fights["A1"]["their_pick"] is None
    assert fights["A1"]["their_method"] is None
    assert fights["A1"]["their_pick_hidden"] is True
    assert upcoming[0]["their_hidden"] == 1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all admin-control tests passed")
