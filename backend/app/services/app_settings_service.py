from __future__ import annotations

from app import runtime_config
from app.repositories import settings_repository
from app.utils.bool_parsing import parse_bool

# Runtime switches the admin flips from the Users admin UI. The DB setting wins;
# the ALLOW_REGISTRATION env var is only the fallback default for fresh installs.

REGISTRATION_KEY = "registration_open"


def registration_open() -> bool:
    stored = settings_repository.get(REGISTRATION_KEY)
    if stored is not None:
        return bool(parse_bool(stored, default=True))
    return runtime_config.registration_enabled()


def set_registration_open(is_open: bool) -> bool:
    settings_repository.set(REGISTRATION_KEY, "1" if is_open else "0")
    return is_open
