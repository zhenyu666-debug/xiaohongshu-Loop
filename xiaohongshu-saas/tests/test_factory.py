"""Unit tests for the content factory."""
from __future__ import annotations

from app.content_factory.factory import render
from app.schemas import TemplateSpec


def test_render_basic():
    tpl = TemplateSpec(
        key="demo",
        title_prefix="今日好物",
        body="这是正文 {emoji} {hour}",
        topics=["#好物"],
    )
    c = render(tpl)
    assert c.title.startswith("今日好物")
    assert "{emoji}" not in c.body and "{hour}" not in c.body
    assert c.topics == ["#好物"]


def test_render_is_randomized():
    tpl = TemplateSpec(key="demo", title_prefix="t", body="b")
    a = render(tpl)
    b = render(tpl)
    # titles include a random 4-digit suffix; extremely unlikely to collide
    assert a.title != b.title