"""Tests for the dual-layer memory helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.memory.dynamic_memory import DYNAMIC_PATH, build_dynamic_memory
from app.memory.static_memory import STATIC_PATH, ensure_static_memory, load_static_memory


def test_static_memory_is_created() -> None:
    ensure_static_memory()
    assert STATIC_PATH.exists()
    text = STATIC_PATH.read_text(encoding="utf-8")
    assert "fraud-risk-engine" in text


def test_static_memory_load_returns_dict() -> None:
    payload = load_static_memory()
    assert payload["ok"] is True
    assert payload["char_count"] > 100
    assert payload["markdown"].startswith("# Static Memory")


def test_dynamic_memory_handles_empty_run() -> None:
    payload = build_dynamic_memory(None, None)
    assert payload["ok"] is True
    assert "No detection run" in payload["markdown"]


def test_dynamic_memory_with_run(tmp_path: Path, monkeypatch) -> None:
    import tempfile
    # Redirect dynamic memory to a tmp file so the test does not pollute
    # the repo's ``data/output`` directory.
    new_dir = tmp_path / "memory"
    new_dir.mkdir(parents=True, exist_ok=True)
    new_target = new_dir / "MEMORY-DYNAMIC.md"
    monkeypatch.setattr("app.memory.dynamic_memory.DYNAMIC_PATH", new_target)
    # Also patch the ROOT used for the relative_to call so the
    # payload's ``path`` field stays valid.
    monkeypatch.setattr("app.memory.dynamic_memory.ROOT", new_dir)
    run = {
        "run_id": "abc",
        "ended_at": "2026-07-16T13:00:00Z",
        "status": "ok",
        "alerts": [
            {"severity": "high", "kind": "transaction_ring", "score": 0.7, "title": "Ring"},
            {"severity": "low", "kind": "pagerank", "score": 0.3, "title": "Top"},
        ],
        "snapshot": {
            "vertices": {"Account": 1200, "Device": 900},
            "edges": {"USES_DEVICE": 1200, "FROM_ACCOUNT": 20000},
            "planted_rings": [{"ring_id": 0, "accounts": ["A0", "A1", "A2"], "shared_device": "D0", "shared_ip": "IP0"}],
        },
    }
    payload = build_dynamic_memory(run, None)
    assert payload["alert_count"] == 2
    assert "Ring" in payload["markdown"]
    assert "Top" in payload["markdown"]
    assert "Graph snapshot" in payload["markdown"]
