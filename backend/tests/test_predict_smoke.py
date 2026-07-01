"""
HTTP smoke coverage for the Fight Lab prediction endpoints. Guards the regression where
the account-pick request schema shadowed the fight-prediction schema, making real
`/predict` + `/predict-method` calls fail with 422. Runs through the full app (TestClient).

Runs under pytest, or standalone:  python tests/test_predict_smoke.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.api_hardening as hardening  # noqa: E402
import app.db.connection as db_connection  # noqa: E402
from app.main import app  # noqa: E402

# Long-career, well-represented lightweights — present in the scraped data + features.
FIGHT = {
    "fighter_a": "Charles Oliveira",
    "fighter_b": "Max Holloway",
    "weight_class": "Lightweight",
}


def _client(tmp) -> TestClient:
    db_connection.set_db_path(Path(tmp) / "app.db")
    hardening._limiter._hits.clear()
    return TestClient(app)


def test_predict_accepts_fight_schema(tmp_path=None):
    client = _client(tmp_path or tempfile.mkdtemp())

    r = client.post("/predict", json=FIGHT)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("predicted_winner") in (FIGHT["fighter_a"], FIGHT["fighter_b"])


def test_predict_method_accepts_fight_schema(tmp_path=None):
    client = _client(tmp_path or tempfile.mkdtemp())

    r = client.post("/predict-method", json=FIGHT)
    assert r.status_code == 200, r.text


def test_pick_schema_is_rejected_by_predict(tmp_path=None):
    # The account-pick body must NOT satisfy the fight schema (the shadow bug).
    client = _client(tmp_path or tempfile.mkdtemp())
    r = client.post("/predict", json={"fight_url": "x", "picked_fighter": "y"})
    assert r.status_code == 422


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all predict smoke tests passed")
