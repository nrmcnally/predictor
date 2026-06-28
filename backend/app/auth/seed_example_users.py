from __future__ import annotations

"""Seed example accounts for local dev: one admin, one regular user. Idempotent.

  python -m app.auth.seed_example_users

These are obvious demo credentials for local use only — change/remove them before
deploying. Note: once an admin exists, admin endpoints stop being dev-open and
require admin auth (Bearer token) or a configured ADMIN_TOKEN.
"""

from app.auth import security
from app.repositories import users_repository

# (username, password, role)
EXAMPLE_USERS = [
    ("admin", "admin12345", "admin"),
    ("demo", "demo12345", "user"),
]


def seed_example_users() -> list[tuple[str, str]]:
    created: list[tuple[str, str]] = []
    for username, password, role in EXAMPLE_USERS:
        if users_repository.get_by_username(username) is not None:
            continue
        users_repository.create_user(
            username, security.hash_password(password), role=role
        )
        created.append((username, role))
    return created


def main() -> None:
    created = seed_example_users()
    if not created:
        print("Example users already exist — nothing to do.")
        return
    for username, role in created:
        print(f"Created {role:5} account: {username}")


if __name__ == "__main__":
    main()
