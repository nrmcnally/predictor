"""
Tests for file_aware_cache: caches auto-invalidate when source files change on
disk (the fix for stale predictions after an out-of-process retrain/rebuild).

Runs under pytest, or standalone:  python tests/test_file_aware_cache.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.prediction_service import file_aware_cache  # noqa: E402


def test_reloads_when_file_changes():
    tmp = Path(tempfile.gettempdir()) / "fa_cache_test.txt"
    tmp.write_text("v1")
    calls = {"n": 0}

    @file_aware_cache(lambda: [tmp])
    def loader():
        calls["n"] += 1
        return tmp.read_text()

    assert loader() == "v1"
    assert loader() == "v1"
    assert calls["n"] == 1  # second call served from cache

    # Simulate an out-of-process rebuild: new contents + newer mtime.
    tmp.write_text("v2")
    os.utime(tmp, (time.time() + 10, time.time() + 10))

    assert loader() == "v2"      # picked up the change with no restart
    assert calls["n"] == 2

    loader.cache_clear()         # explicit clear still works
    assert loader() == "v2"
    assert calls["n"] == 3

    tmp.unlink()


def test_missing_file_is_stable():
    missing = Path(tempfile.gettempdir()) / "fa_cache_missing_xyz.txt"
    if missing.exists():
        missing.unlink()
    calls = {"n": 0}

    @file_aware_cache(lambda: [missing])
    def loader():
        calls["n"] += 1
        return "ok"

    assert loader() == "ok"
    assert loader() == "ok"
    assert calls["n"] == 1  # a missing file yields a stable signature, still cached


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
