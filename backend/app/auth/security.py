from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

# --- Password hashing (PBKDF2-SHA256, Django-style "$"-delimited format) ---------

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000  # OWASP-recommended floor for PBKDF2-HMAC-SHA256


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, hash_hex = stored.split("$")
        if algorithm != PBKDF2_ALGORITHM:
            return False
        derived = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(derived.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


# --- Signed tokens (HS256, JWT-compatible encoding) ------------------------------

DEFAULT_TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 days


def _secret() -> bytes:
    # Set AUTH_SECRET in production. The dev fallback is intentionally obvious.
    return os.environ.get("AUTH_SECRET", "dev-insecure-auth-secret-change-me").encode("utf-8")


def _b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(payload: dict[str, Any], ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    body = {**payload, "iat": now, "exp": now + ttl_seconds}

    header_b64 = _b64u_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    body_b64 = _b64u_encode(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{body_b64}".encode("ascii")
    signature = hmac.new(_secret(), signing_input, hashlib.sha256).digest()

    return f"{header_b64}.{body_b64}.{_b64u_encode(signature)}"


def decode_token(token: str) -> dict[str, Any] | None:
    """Return the payload if the signature is valid and the token isn't expired, else None."""
    try:
        header_b64, body_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{body_b64}".encode("ascii")
        expected = hmac.new(_secret(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64u_decode(signature_b64)):
            return None

        payload = json.loads(_b64u_decode(body_b64))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
