from __future__ import annotations

import os
from typing import Any

from app.auth import security
from app.repositories import users_repository

MIN_USERNAME_LENGTH = 3
MIN_PASSWORD_LENGTH = 8


def register_user(username: str, password: str, role: str = "user") -> dict[str, Any]:
    """Create a new account. Raises ValueError on invalid input or duplicate username."""
    username = (username or "").strip()

    if len(username) < MIN_USERNAME_LENGTH:
        raise ValueError(f"Username must be at least {MIN_USERNAME_LENGTH} characters.")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if users_repository.get_by_username(username):
        raise ValueError("Username is already taken.")

    user = users_repository.create_user(
        username, security.hash_password(password), role=role
    )
    return users_repository.public_user(user)


def authenticate(username: str, password: str) -> dict[str, Any]:
    """Return {token, user} on success; raise ValueError on bad credentials.

    The same generic error is used for unknown user vs wrong password (no enumeration).
    """
    username = (username or "").strip()
    user = users_repository.get_by_username(username)

    if user is None or not security.verify_password(password or "", user["password_hash"]):
        raise ValueError("Invalid username or password.")

    token = security.create_token(
        {"sub": user["id"], "username": user["username"], "role": user["role"]}
    )
    return {"token": token, "user": users_repository.public_user(user)}


def ensure_seed_admin() -> dict[str, Any] | None:
    """Bootstrap the admin from ADMIN_USERNAME / ADMIN_PASSWORD env vars.

    Creates the admin if missing; promotes the account to admin if it exists with a
    lower role. No-op when the env vars aren't set.
    """
    username = os.environ.get("ADMIN_USERNAME", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")

    if not username or not password:
        return None

    existing = users_repository.get_by_username(username)
    if existing is not None:
        if existing["role"] != "admin":
            users_repository.set_role(existing["id"], "admin")
        return users_repository.public_user(existing)

    user = users_repository.create_user(
        username, security.hash_password(password), role="admin"
    )
    return users_repository.public_user(user)


def admin_exists() -> bool:
    return users_repository.count_admins() > 0
