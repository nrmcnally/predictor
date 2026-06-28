from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

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


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[tuple, deque] = defaultdict(deque)

    def allow(self, key: tuple, limit: int, window_seconds: float) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
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


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        if path in AUTH_PATHS and not _limiter.allow(
            (client_ip, "auth"), AUTH_LIMIT_PER_MINUTE, 60
        ):
            return _too_many()

        if not _limiter.allow((client_ip, "global"), GLOBAL_LIMIT_PER_MINUTE, 60):
            return _too_many()

        return await call_next(request)


def cors_origins() -> list[str]:
    """Allowed CORS origins. Set CORS_ORIGINS (comma-separated) for the deployed
    frontend; defaults to the local Vite dev origins."""
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]
