from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.runtime_config import require_auth_enabled

# --- Security headers ----------------------------------------------------------
# Conservative, API-appropriate headers. No CSP (this serves JSON to a separate
# frontend, and a strict CSP would break the built-in /docs UI).
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


# --- Rate limiting -------------------------------------------------------------
# Per-IP sliding-window limiter. In-process (per worker) — fine at this scale; a
# multi-worker/distributed deploy would back this with Redis. Auth endpoints get a
# stricter bucket to blunt credential stuffing / brute force.
GLOBAL_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "240"))
AUTH_LIMIT_PER_MINUTE = int(os.environ.get("AUTH_RATE_LIMIT_PER_MINUTE", "15"))
AUTH_PATHS = {"/auth/login", "/auth/register"}


# Cap the number of tracked (ip, bucket) keys so an attacker rotating spoofed IPs
# can't grow the limiter's memory without bound.
MAX_TRACKED_KEYS = 20_000


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[tuple, deque] = defaultdict(deque)

    def _prune(self, cutoff: float) -> None:
        for key in list(self._hits.keys()):
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if not hits:
                del self._hits[key]

    def allow(self, key: tuple, limit: int, window_seconds: float) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            if len(self._hits) > MAX_TRACKED_KEYS:
                self._prune(cutoff)
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True


_limiter = RateLimiter()


def _too_many() -> JSONResponse:
    return JSONResponse(
        status_code=429, content={"message": "Too many requests. Please slow down."}
    )


def _client_ip(request) -> str:
    """The real client IP. Behind a reverse proxy every request arrives from the
    proxy's address, so with TRUST_PROXY=1 we use the last X-Forwarded-For hop —
    the one appended by OUR proxy (earlier hops are client-controlled and spoofable).
    Never trust the header without the flag."""
    if os.environ.get("TRUST_PROXY", "").strip().lower() in {"1", "true", "yes", "on"}:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            last_hop = forwarded.split(",")[-1].strip()
            if last_hop:
                return last_hop
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        client_ip = _client_ip(request)
        path = request.url.path

        if path in AUTH_PATHS and not _limiter.allow(
            (client_ip, "auth"), AUTH_LIMIT_PER_MINUTE, 60
        ):
            return _too_many()

        if not _limiter.allow((client_ip, "global"), GLOBAL_LIMIT_PER_MINUTE, 60):
            return _too_many()

        return await call_next(request)


# --- Hosted-mode auth wall -------------------------------------------------------
# When REQUIRE_AUTH is on (default in hosted mode), every endpoint needs a valid
# account token except the public shell: health, login/register, and the static
# frontend files the login page itself needs.
PUBLIC_PATHS = {"/", "/health", "/auth/login", "/auth/register"}


def _is_public_path(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return True
    # Static frontend files (JS/CSS/images) — anything with a file extension.
    tail = path.rsplit("/", 1)[-1]
    return "." in tail


class RequireAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Read the flag per request so tests (and ops) can toggle it via env.
        if not require_auth_enabled():
            return await call_next(request)
        if request.method == "OPTIONS" or _is_public_path(request.url.path):
            return await call_next(request)

        # Late import to keep middleware setup free of repository imports.
        from app.auth.dependencies import _user_from_authorization

        user = _user_from_authorization(request.headers.get("Authorization"))
        if user is None:
            return JSONResponse(
                status_code=401,
                content={"detail": {"message": "Authentication required."}},
            )
        return await call_next(request)


def cors_origins() -> list[str]:
    """Allowed CORS origins. Set CORS_ORIGINS (comma-separated) for the deployed
    frontend; defaults to the local Vite dev origins."""
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    # Local Vite dev origins. Vite bumps the port (5173 -> 5174 -> ...) when one is
    # taken, so allow a small range on both hosts to avoid "failed to fetch".
    return [
        f"http://{host}:{port}"
        for host in ("localhost", "127.0.0.1")
        for port in (5173, 5174, 5175)
    ]
