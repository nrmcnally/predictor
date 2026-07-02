from __future__ import annotations

import os
import re
from typing import Any

from app.auth import security
from app.repositories import users_repository

MIN_PASSWORD_LENGTH = 8
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_email(email: str) -> str:
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email or ""))


def _clean_display_name(email: str, display_name: str | None) -> str:
    display = (display_name or "").strip()
    if "@" in display:
        raise ValueError("Username cannot be an email address.")
    if len(display) > 60:
        raise ValueError("Username must be 60 characters or fewer.")
    return display or email.split("@")[0]


def _next_available_username(base: str) -> str:
    """A free username derived from `base`, de-duped with a numeric suffix."""
    candidate = base
    suffix = 1
    while users_repository.get_by_display_name(candidate) is not None:
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


def register_user(
    email: str, password: str, display_name: str | None = None, role: str = "user"
) -> dict[str, Any]:
    """Create a new account. Raises ValueError on invalid input or duplicate email."""
    email = _clean_email(email)

    if not is_valid_email(email):
        raise ValueError("Enter a valid email address.")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if users_repository.get_by_email(email):
        raise ValueError("An account with that email already exists.")

    display = _clean_display_name(email, display_name)
    if (display_name or "").strip():
        # An explicitly chosen username must be free (case-insensitive).
        if users_repository.get_by_display_name(display) is not None:
            raise ValueError("That username is taken.")
    else:
        # Derived from the email — silently de-dupe so registration still succeeds.
        display = _next_available_username(display)

    user = users_repository.create_user(
        email, security.hash_password(password), display_name=display, role=role
    )
    return users_repository.public_user(user)


def authenticate(email: str, password: str) -> dict[str, Any]:
    """Return {token, user} on success; raise ValueError on bad credentials.

    The same generic error is used for unknown account vs wrong password.
    """
    email = _clean_email(email)
    user = users_repository.get_by_email(email)

    if user is None or not security.verify_password(password or "", user["password_hash"]):
        raise ValueError("Invalid email or password.")

    users_repository.touch_last_login(user["id"])
    token = security.create_token(
        {"sub": user["id"], "email": user["email"], "role": user["role"]}
    )
    return {"token": token, "user": users_repository.public_user(user)}


def admin_reset_password(target_user_id: Any) -> str:
    """Set a fresh random temporary password on an account and return it ONCE.
    There is no email infrastructure, so lost passwords are recovered by an admin
    handing the temp password to the friend out-of-band. Caller must be admin-gated."""
    import secrets as _secrets

    user = users_repository.get_by_id(target_user_id)
    if user is None:
        raise ValueError("Account not found.")

    temp_password = _secrets.token_urlsafe(9)  # ~12 chars, > MIN_PASSWORD_LENGTH
    users_repository.update_password(target_user_id, security.hash_password(temp_password))
    return temp_password


def change_password(user_id: Any, current_password: str, new_password: str) -> None:
    """Change a user's password after verifying the current one."""
    user = users_repository.get_by_id(user_id)
    if user is None:
        raise ValueError("Account not found.")
    if not security.verify_password(current_password or "", user["password_hash"]):
        raise ValueError("Current password is incorrect.")
    if len(new_password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

    users_repository.update_password(user_id, security.hash_password(new_password))


def set_visibility(user_id: Any, is_public: bool) -> bool:
    """Set whether the account is publicly visible (opt-in for future leaderboards)."""
    return users_repository.set_visibility(user_id, bool(is_public))


def update_profile(
    user_id: Any,
    email: str,
    display_name: str | None,
    current_password: str | None = None,
) -> dict[str, Any]:
    """Update the account's email + username. Changing the EMAIL (the login key)
    additionally requires the current password, so a hijacked session can't silently
    rotate the account's login. Username-only edits need no password."""
    email = _clean_email(email)
    if not is_valid_email(email):
        raise ValueError("Enter a valid email address.")

    me = users_repository.get_by_id(user_id)
    if me is None:
        raise ValueError("Account not found.")
    if email != _clean_email(me["email"]):
        if not security.verify_password(current_password or "", me["password_hash"]):
            raise ValueError("Enter your current password to change your email.")

    existing = users_repository.get_by_email(email)
    if existing is not None and existing["id"] != user_id:
        raise ValueError("That email is already in use.")

    display = _clean_display_name(email, display_name)
    taken = users_repository.get_by_display_name(display)
    if taken is not None and taken["id"] != user_id:
        raise ValueError("That username is taken.")

    users_repository.update_profile(user_id, email, display)
    return users_repository.public_user(users_repository.get_by_id(user_id))


def ensure_seed_admin() -> dict[str, Any] | None:
    """Bootstrap the admin from ADMIN_EMAIL / ADMIN_PASSWORD env vars."""
    email = _clean_email(os.environ.get("ADMIN_EMAIL", ""))
    password = os.environ.get("ADMIN_PASSWORD", "")

    if not email or not password:
        return None

    existing = users_repository.get_by_email(email)
    if existing is not None:
        if existing["role"] != "admin":
            users_repository.set_role(existing["id"], "admin")
        return users_repository.public_user(existing)

    user = users_repository.create_user(
        email,
        security.hash_password(password),
        display_name=_next_available_username(email.split("@")[0]),
        role="admin",
    )
    return users_repository.public_user(user)


def admin_exists() -> bool:
    return users_repository.count_admins() > 0
