"""
Tests for centralized API error handling (ROADMAP §8b Phase 0, item #1).

Verifies the three exception handlers return the right status + body envelope
that the frontend already parses, and that they're wired onto the app for the
right exception types. Handlers are exercised directly (rather than over HTTP)
so the suite needs no httpx/TestClient dependency.

Runs under pytest, or standalone:  python tests/test_error_handling.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main as main  # noqa: E402
from app.services.prediction_service import FighterNotFoundError  # noqa: E402


class _FakeURL:
    path = "/some/path"


class _FakeRequest:
    method = "GET"
    url = _FakeURL()


def _body(response):
    return json.loads(response.body)


def test_fighter_not_found_handler_keeps_message_and_suggestions():
    exc = FighterNotFoundError("Bogus Fighter", ["Real One", "Real Two"])
    response = asyncio.run(main.fighter_not_found_handler(_FakeRequest(), exc))

    assert response.status_code == 404
    detail = _body(response)["detail"]
    assert detail["message"] == "Could not find fighter: Bogus Fighter"
    assert detail["suggestions"] == ["Real One", "Real Two"]


def test_value_error_handler_returns_404_with_message():
    response = asyncio.run(
        main.value_error_handler(_FakeRequest(), ValueError("Unknown card: zzz"))
    )

    assert response.status_code == 404
    assert _body(response)["detail"]["message"] == "Unknown card: zzz"


def test_unhandled_exception_handler_is_generic_and_non_leaky():
    secret = "C:/server/secret/path/leak.csv"
    response = asyncio.run(
        main.unhandled_exception_handler(_FakeRequest(), RuntimeError(secret))
    )

    assert response.status_code == 500
    assert _body(response) == {"message": "Internal server error."}
    # Internal details (paths, messages) must never reach the client.
    assert secret not in response.body.decode()


def test_handlers_are_registered_for_the_right_exceptions():
    handlers = main.app.exception_handlers
    # FighterNotFoundError subclasses ValueError, so it must be registered
    # explicitly to win the MRO resolution over the generic ValueError handler.
    assert FighterNotFoundError in handlers
    assert ValueError in handlers
    assert Exception in handlers


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
