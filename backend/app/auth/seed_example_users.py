from __future__ import annotations

"""Seed example accounts for local dev: one admin, one regular user. Idempotent.

  python -m app.auth.seed_example_users

Obvious demo credentials for local use only — change/remove before deploying.
"""

from app.auth import security
from app.repositories import users_repository

# (email, password, display_name, role)
EXAMPLE_USERS = [
    ("admin@fightiq.local", "admin12345", "admin", "admin"),
    ("demo@fightiq.local", "demo12345", "demo", "user"),
]


def seed_example_users() -> list[tuple[str, str]]:
    created: list[tuple[str, str]] = []
    for email, password, display_name, role in EXAMPLE_USERS:
        if users_repository.get_by_email(email) is not None:
            continue
        users_repository.create_user(
            email, security.hash_password(password), display_name=display_name, role=role
        )
        created.append((email, role))
    return created


def main() -> None:
    created = seed_example_users()
    if not created:
        print("Example users already exist — nothing to do.")
        return
    for email, role in created:
        print(f"Created {role:5} account: {email}")


if __name__ == "__main__":
    main()
