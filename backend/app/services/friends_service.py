from __future__ import annotations

from typing import Any

from app.repositories import friends_repository, users_repository
from app.services.auth_service import is_valid_email

# Mutual-accept friends. You add someone by an email you already know (we never hand an
# email back out); everything returned is display-name only, matching the leaderboard.


def _display_name(user: dict[str, Any] | None) -> str:
    name = (user or {}).get("display_name") or ""
    name = name.strip()
    return name if name and "@" not in name else "Unnamed User"


def _friend_view(user_id: Any, friendship_id: Any) -> dict[str, Any]:
    user = users_repository.get_by_id(user_id)
    return {
        "user_id": int(user_id),
        "display_name": _display_name(user),
        "friendship_id": int(friendship_id),
    }


def send_friend_request(me_id: Any, target_email: str) -> dict[str, Any]:
    email = (target_email or "").strip().lower()
    if not is_valid_email(email):
        raise ValueError("Enter a valid email address.")

    target = users_repository.get_by_email(email)
    if target is None:
        raise ValueError("No account uses that email.")
    if target["id"] == me_id:
        raise ValueError("You can't add yourself.")

    existing = friends_repository.get_pair(me_id, target["id"])
    if existing is not None:
        if existing["status"] == "accepted":
            raise ValueError("You're already friends.")
        if existing["requester_id"] == me_id:
            raise ValueError("You already sent them a request.")
        # They had already requested you — sending back accepts it (mutual).
        friends_repository.set_status(existing["id"], "accepted")
        return {"status": "accepted", "friend": _friend_view(target["id"], existing["id"])}

    created = friends_repository.create_request(me_id, target["id"])
    return {"status": "pending", "friend": _friend_view(target["id"], created["id"])}


def respond_to_request(me_id: Any, friendship_id: Any, accept: bool) -> dict[str, Any]:
    row = friends_repository.get_by_id(friendship_id)
    if row is None or row["addressee_id"] != me_id or row["status"] != "pending":
        raise ValueError("No pending request to respond to.")

    if accept:
        friends_repository.set_status(friendship_id, "accepted")
        return {"status": "accepted", "friend": _friend_view(row["requester_id"], friendship_id)}

    friends_repository.delete(friendship_id)
    return {"status": "declined"}


def remove_friend(me_id: Any, other_id: Any) -> bool:
    row = friends_repository.get_pair(me_id, other_id)
    if row is None:
        return False
    return friends_repository.delete(row["id"])


def get_overview(me_id: Any) -> dict[str, Any]:
    """The user's accepted friends plus incoming/outgoing pending requests."""
    friends: list[dict[str, Any]] = []
    incoming: list[dict[str, Any]] = []
    outgoing: list[dict[str, Any]] = []

    for row in friends_repository.list_for_user(me_id):
        other = row["addressee_id"] if row["requester_id"] == me_id else row["requester_id"]
        view = _friend_view(other, row["id"])
        if row["status"] == "accepted":
            friends.append(view)
        elif row["requester_id"] == me_id:
            outgoing.append(view)
        else:
            incoming.append(view)

    return {"friends": friends, "incoming": incoming, "outgoing": outgoing}
