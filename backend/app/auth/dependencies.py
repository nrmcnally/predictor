from __future__ import annotations

import os
from typing import Any

from fastapi import Header, HTTPException

from app.auth import security
from app.repositories import users_repository


def _user_from_authorization(authorization: str | None) -> dict[str, Any] | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    payload = security.decode_token(token)
    if not payload:
        return None
    # Load fresh from the DB so role changes / deletions take effect immediately.
    return users_repository.get_by_id(payload.get("sub"))


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _user_from_authorization(authorization)
    if user is None:
        raise HTTPException(
            status_code=401, detail={"message": "Authentication required."}
        )
    return users_repository.public_user(user)


def get_optional_user(authorization: str | None = Header(default=None)) -> dict[str, Any] | None:
    user = _user_from_authorization(authorization)
    return users_repository.public_user(user) if user is not None else None


def require_admin(
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> dict[str, Any] | None:
    """Gate admin/heavy endpoints. Order:

      1. A valid Bearer token belonging to an admin account.
      2. The legacy ADMIN_TOKEN header (back-compat during the transition).
      3. Local-dev open: nothing is configured yet (no admin account, no token).

    Otherwise 403.
    """
    user = _user_from_authorization(authorization)
    if user is not None and user.get("role") == "admin":
        return users_repository.public_user(user)

    legacy_token = os.environ.get("ADMIN_TOKEN", "").strip()
    if legacy_token and x_admin_token == legacy_token:
        return None

    if not legacy_token and users_repository.count_admins() == 0:
        return None

    raise HTTPException(
        status_code=403, detail={"message": "Admin privileges required."}
    )
