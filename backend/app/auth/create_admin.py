from __future__ import annotations

"""Create or promote an admin account.

  python -m app.auth.create_admin <email> <password>

If the email already has an account it's promoted to admin; otherwise a new admin
is created.
"""

import sys

from app.auth import security
from app.repositories import users_repository


def create_or_promote_admin(email: str, password: str) -> tuple[int, str]:
    existing = users_repository.get_by_email(email)
    if existing is not None:
        users_repository.set_role(existing["id"], "admin")
        return int(existing["id"]), "promoted"

    user = users_repository.create_user(
        email, security.hash_password(password),
        display_name=email.split("@")[0], role="admin",
    )
    return int(user["id"]), "created"


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python -m app.auth.create_admin <email> <password>")
        raise SystemExit(1)

    user_id, action = create_or_promote_admin(sys.argv[1], sys.argv[2])
    print(f"Admin {action}: {sys.argv[1]} (id={user_id})")


if __name__ == "__main__":
    main()
