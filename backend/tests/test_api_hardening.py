"""
Tests for Phase 2 API hardening: the per-IP rate limiter, CORS origin config, and
security headers.

Runs under pytest, or standalone:  python tests/test_api_hardening.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api_hardening import (  # noqa: E402
    SECURITY_HEADERS,
    RateLimiter,
    cors_origins,
)


def test_rate_limiter_allows_up_to_limit_then_blocks():
    limiter = RateLimiter()
    key = ("1.2.3.4", "global")

    assert all(limiter.allow(key, limit=5, window_seconds=60) for _ in range(5))
    assert not limiter.allow(key, limit=5, window_seconds=60)  # 6th over the limit


def test_rate_limiter_keys_are_independent():
    limiter = RateLimiter()
    assert limiter.allow(("ip-a", "global"), limit=1, window_seconds=60)
    assert not limiter.allow(("ip-a", "global"), limit=1, window_seconds=60)
    # A different IP (or bucket) is tracked separately.
    assert limiter.allow(("ip-b", "global"), limit=1, window_seconds=60)
    assert limiter.allow(("ip-a", "auth"), limit=1, window_seconds=60)


def test_cors_origins_default_and_env_override():
    os.environ.pop("CORS_ORIGINS", None)
    assert "http://localhost:5173" in cors_origins()

    os.environ["CORS_ORIGINS"] = "https://app.example.com, https://www.example.com"
    try:
        assert cors_origins() == ["https://app.example.com", "https://www.example.com"]
    finally:
        os.environ.pop("CORS_ORIGINS", None)


def test_security_headers_are_set():
    assert SECURITY_HEADERS["X-Content-Type-Options"] == "nosniff"
    assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in SECURITY_HEADERS


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
