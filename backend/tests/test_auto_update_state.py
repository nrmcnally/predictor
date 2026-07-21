from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "deploy" / "auto_update.py"
SPEC = importlib.util.spec_from_file_location("fightiq_auto_update", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
auto_update = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(auto_update)


def test_already_pushed_today_requires_valid_same_day_timestamp(tmp_path, monkeypatch):
    state_path = tmp_path / "last_successful_push.json"
    monkeypatch.setattr(auto_update, "SUCCESS_STATE_PATH", state_path)
    now = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)

    assert auto_update._already_pushed_today(now) is False

    state_path.write_text("not json", encoding="utf-8")
    assert auto_update._already_pushed_today(now) is False

    state_path.write_text(
        json.dumps({"last_successful_push_at": "2026-07-20T23:59:00+00:00"}),
        encoding="utf-8",
    )
    assert auto_update._already_pushed_today(now) is False

    state_path.write_text(
        json.dumps({"last_successful_push_at": "2026-07-21T00:01:00+00:00"}),
        encoding="utf-8",
    )
    assert auto_update._already_pushed_today(now) is True


def test_write_success_state_is_readable_and_records_degraded(tmp_path, monkeypatch):
    state_path = tmp_path / "last_successful_push.json"
    monkeypatch.setattr(auto_update, "SUCCESS_STATE_PATH", state_path)

    auto_update._write_success_state(server="https://example.test", degraded=True)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert datetime.fromisoformat(state["last_successful_push_at"])
    assert state["server"] == "https://example.test"
    assert state["degraded"] is True
    assert not state_path.with_suffix(".tmp").exists()
