"""
Tests for the mutual-accept friends system: request/accept/decline by username,
reverse-request auto-accept, validation, unfriend, and that friend lists never expose
emails.
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

    res = friends_service.send_friend_request(a["id"], "Boz")
    assert res["status"] == "pending"

    ov_b = friends_service.get_overview(b["id"])
    assert [f["display_name"] for f in ov_b["incoming"]] == ["Ada"]
    fid = ov_b["incoming"][0]["friendship_id"]

    friends_service.respond_to_request(b["id"], fid, True)
    ov_a = friends_service.get_overview(a["id"])
    assert [f["display_name"] for f in ov_a["friends"]] == ["Boz"]
    assert friends_repository.list_friend_ids(a["id"]) == [b["id"]]

    assert "@" not in str(ov_a) and "@" not in str(ov_b)


def test_add_by_username_is_case_insensitive(tmp_path=None):
    a, b = _two_users(tmp_path or tempfile.mkdtemp())
    # "boz" resolves to the "Boz" account.
    res = friends_service.send_friend_request(a["id"], "boz")
    assert res["status"] == "pending"


def test_reverse_request_auto_accepts(tmp_path=None):
    a, b = _two_users(tmp_path or tempfile.mkdtemp())

    friends_service.send_friend_request(a["id"], "Boz")   # a -> b pending
    res = friends_service.send_friend_request(b["id"], "Ada")  # b -> a
    assert res["status"] == "accepted"
    assert friends_repository.list_friend_ids(a["id"]) == [b["id"]]


def test_validation(tmp_path=None):
    a, b = _two_users(tmp_path or tempfile.mkdtemp())

    assert _raises_value_error(friends_service.send_friend_request, a["id"], "Ada")  # self
    assert _raises_value_error(friends_service.send_friend_request, a["id"], "")  # empty
    assert _raises_value_error(friends_service.send_friend_request, a["id"], "Ghost")  # no user

    friends_service.send_friend_request(a["id"], "Boz")
    assert _raises_value_error(friends_service.send_friend_request, a["id"], "Boz")  # already sent


def test_decline_and_unfriend(tmp_path=None):
    a, b = _two_users(tmp_path or tempfile.mkdtemp())

    friends_service.send_friend_request(a["id"], "Boz")
    fid = friends_service.get_overview(b["id"])["incoming"][0]["friendship_id"]
    friends_service.respond_to_request(b["id"], fid, False)  # decline
    assert friends_service.get_overview(a["id"])["outgoing"] == []
    assert friends_service.get_overview(b["id"])["incoming"] == []

    friends_service.send_friend_request(a["id"], "Boz")
    fid2 = friends_service.get_overview(b["id"])["incoming"][0]["friendship_id"]
    friends_service.respond_to_request(b["id"], fid2, True)
    assert friends_service.remove_friend(a["id"], b["id"]) is True
    assert friends_repository.list_friend_ids(a["id"]) == []
    assert friends_service.remove_friend(a["id"], b["id"]) is False


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all friends tests passed")
