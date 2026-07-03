"""Smoke tests for the public API surface (no DB)."""
from __future__ import annotations

from app.schemas import AccountCreate, TaskCreate, TemplateSpec


def test_account_create():
    a = AccountCreate(id="acc_001", nickname="test")
    assert a.channel == "xiaohongshu"


def test_task_create_defaults():
    t = TaskCreate(name="t1", template_key="beauty_瞳_v1")
    assert t.kind.value == "loop"
    assert t.interval_minutes == 60


def test_template_spec():
    t = TemplateSpec(key="x", title_prefix="T", topics=["#a"])
    assert t.topics == ["#a"]