from __future__ import annotations

import os

# Hosted-mode switches. Everything defaults to the permissive local-dev behavior;
# a deployed instance sets FIGHTIQ_HOSTED=1 (see DEPLOY.md) which turns on the
# strict behavior in one move. Individual flags can still override.

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}

# The intentionally-obvious dev fallback in app/auth/security.py. A hosted instance
# must never run with it — tokens would be forgeable by anyone who has read the source.
DEV_AUTH_SECRET = "dev-insecure-auth-secret-change-me"
MIN_AUTH_SECRET_LENGTH = 32


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if raw in _TRUTHY:
        return True
    if raw in _FALSY:
        return False
    return default


def is_hosted() -> bool:
    """True when running as a deployed, internet-facing instance."""
    return _env_flag("FIGHTIQ_HOSTED", False)


def require_auth_enabled() -> bool:
    """Require a valid account token on every endpoint except the public shell
    (health, login/register, and the static frontend). Defaults on in hosted mode."""
    return _env_flag("REQUIRE_AUTH", is_hosted())


def registration_enabled() -> bool:
    """Open self-registration. Turn off once your friend group has accounts."""
    return _env_flag("ALLOW_REGISTRATION", True)


def assert_hosted_config() -> None:
    """Fail fast at boot when a hosted instance is misconfigured, instead of
    silently running with forgeable tokens."""
    if not is_hosted():
        return

    secret = os.environ.get("AUTH_SECRET", "").strip()
    if not secret or secret == DEV_AUTH_SECRET:
        raise RuntimeError(
            "FIGHTIQ_HOSTED=1 but AUTH_SECRET is not set (or is the dev default). "
            "Set a long random AUTH_SECRET before exposing this instance: "
            'python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    if len(secret) < MIN_AUTH_SECRET_LENGTH:
        raise RuntimeError(
            f"AUTH_SECRET is too short ({len(secret)} chars); use at least "
            f"{MIN_AUTH_SECRET_LENGTH} random characters."
        )
