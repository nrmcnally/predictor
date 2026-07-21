from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "deploy"))

import push_update  # noqa: E402


class _Response:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _WarmSession:
    def __init__(self):
        self.calls = 0

    def get(self, url, timeout):
        self.calls += 1
        if self.calls == 1:
            raise requests.ReadTimeout("cold start")
        return _Response(200)


class _LoginSession:
    def __init__(self):
        self.calls = 0

    def post(self, url, json, timeout):
        self.calls += 1
        if self.calls == 1:
            raise requests.ReadTimeout("cold start")
        return _Response(200, {"token": "token-value"})


def test_warm_host_retries_a_cold_start(monkeypatch):
    monkeypatch.setattr(push_update.time, "sleep", lambda _seconds: None)
    session = _WarmSession()

    assert push_update.warm_host(session, "https://example.test") is True
    assert session.calls == 2


def test_login_retries_transient_timeout_without_exposing_password(monkeypatch, capsys):
    monkeypatch.setattr(push_update.time, "sleep", lambda _seconds: None)
    session = _LoginSession()

    token = push_update.login_with_retries(
        session,
        "https://example.test",
        "admin@example.test",
        "top-secret-password",
    )

    assert token == "token-value"
    assert session.calls == 2
    assert "top-secret-password" not in capsys.readouterr().out


def test_login_does_not_retry_bad_credentials(monkeypatch):
    monkeypatch.setattr(push_update.time, "sleep", lambda _seconds: None)

    class BadCredentialSession:
        calls = 0

        def post(self, url, json, timeout):
            self.calls += 1
            return _Response(401, text="invalid credentials")

    session = BadCredentialSession()
    assert (
        push_update.login_with_retries(
            session,
            "https://example.test",
            "admin@example.test",
            "wrong-password",
        )
        is None
    )
    assert session.calls == 1
