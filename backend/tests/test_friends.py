"""
Tests for the mutual-accept friends system: request/accept/decline, reverse-request
auto-accept, validation, unfriend, and that friend lists never expose emails.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.connection as db_connection  # noqa: E402
from app.repositories import friends_repository  # noqa: E402
from app.services import auth_service, friends_service  # noqa: E402


def _use_temp_db(tmp):
    db_connection.set_db_path(Path(tmp) / "app.db")


def _raises_value_error(fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
        return False
    except ValueError:
        return True


def _two_users(tmp):
    _use_temp_db(tmp)
    a = auth_service.register_user("ada@example.com", "password123", "Ada")
    b = auth_service.register_user("boz@example.com", "password123", "Boz")
    return a, b


def test_request_accept_overview_no_email_leak(tmp_path=None):
    a, b = _two_users(tmp_path or tempfile.mkdtemp())

    res = friends_service.send_friend_request(a["id"], "boz@example.com")
    assert res["status"] == "pending"

    ov_b = friends_service.get_overview(b["id"])
    assert [f["display_name"] for f in ov_b["incoming"]] == ["Ada"]
    fid = ov_b["incoming"][0]["friendship_id"]

    friends_service.respond_to_request(b["id"], fid, True)
    ov_a = friends_service.get_overview(a["id"])
    assert [f["display_name"] for f in ov_a["friends"]] == ["Boz"]
    assert friends_repository.list_friend_ids(a["id"]) == [b["id"]]

    # No email ever appears in the friend payloads.
    assert "@" not in str(ov_a) and "@" not in str(ov_b)


def test_reverse_request_auto_accepts(tmp_path=None):
    a, b = _two_users(tmp_path or tempfile.mkdtemp())

    friends_service.send_friend_request(a["id"], "boz@example.com")   # a -> b pending
    res = friends_service.send_friend_request(b["id"], "ada@example.com")  # b -> a
    assert res["status"] == "accepted"  # sending back accepts the pending request
    assert friends_repository.list_friend_ids(a["id"]) == [b["id"]]


def test_validation(tmp_path=None):
    a, b = _two_users(tmp_path or tempfile.mkdtemp())

    assert _raises_value_error(friends_service.send_friend_request, a["id"], "ada@example.com")  # self
    assert _raises_value_error(friends_service.send_friend_request, a["id"], "not-an-email")
    assert _raises_value_error(friends_service.send_friend_request, a["id"], "ghost@example.com")  # no account

    friends_service.send_friend_request(a["id"], "boz@example.com")
    assert _raises_value_error(friends_service.send_friend_request, a["id"], "boz@example.com")  # already sent


def test_decline_and_unfriend(tmp_path=None):
    a, b = _two_users(tmp_path or tempfile.mkdtemp())

    friends_service.send_friend_request(a["id"], "boz@example.com")
    fid = friends_service.get_overview(b["id"])["incoming"][0]["friendship_id"]
    friends_service.respond_to_request(b["id"], fid, False)  # decline
    assert friends_service.get_overview(a["id"])["outgoing"] == []
    assert friends_service.get_overview(b["id"])["incoming"] == []

    # Re-request, accept, then unfriend.
    friends_service.send_friend_request(a["id"], "boz@example.com")
    fid2 = friends_service.get_overview(b["id"])["incoming"][0]["friendship_id"]
    friends_service.respond_to_request(b["id"], fid2, True)
    assert friends_service.remove_friend(a["id"], b["id"]) is True
    assert friends_repository.list_friend_ids(a["id"]) == []
    # Unfriending a non-friend is a no-op, not an error.
    assert friends_service.remove_friend(a["id"], b["id"]) is False


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all friends tests passed")
