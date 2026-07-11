"""Unit tests for CoordinatorAgent.fan_out partial-failure handling.

Bug #3: prior to the fix, ``asyncio.gather(*tasks)`` would raise the first
exception and drop every other sub-graph result. With ``return_exceptions=True``
the surviving sub-graphs still contribute their outputs and the synthesise
node can log the failures.
"""
from __future__ import annotations

import pytest

from app.ai.agents.coordinator import CoordinatorAgent


class _AlwaysFailContentAgent:
    """ContentAgent whose compiled graph raises on every invocation."""

    def __init__(self, *args, **kwargs):
        pass

    def build_graph(self):
        class _G:
            def compile(self):
                class _C:
                    async def ainvoke(self_inner, state):
                        raise RuntimeError("content sub-graph exploded")

                return _C()

        return _G()


class _AlwaysSucceedAnalysisAgent:
    """AnalysisAgent whose compiled graph returns a small success dict."""

    def __init__(self, *args, **kwargs):
        pass

    def build_graph(self):
        class _G:
            def compile(self):
                class _C:
                    async def ainvoke(self_inner, state):
                        return {"analysis": {"score": 99, "ok": True}}

                return _C()

        return _G()


class _AlwaysSucceedContentAgent:
    def __init__(self, *args, **kwargs):
        pass

    def build_graph(self):
        class _G:
            def compile(self):
                class _C:
                    async def ainvoke(self_inner, state):
                        return {"draft": {"title": "t", "body": "b"}}

                return _C()

        return _G()


class _AlwaysFailAnalysisAgent:
    def __init__(self, *args, **kwargs):
        pass

    def build_graph(self):
        class _G:
            def compile(self):
                class _C:
                    async def ainvoke(self_inner, state):
                        raise RuntimeError("analysis sub-graph exploded")

                return _C()

        return _G()


@pytest.mark.asyncio
async def test_fan_out_continues_when_content_subgraph_raises():
    """A raising content sub-graph must NOT abort the analysis sub-graph."""
    coord = CoordinatorAgent(
        content_agent=_AlwaysFailContentAgent(),
        analysis_agent=_AlwaysSucceedAnalysisAgent(),
    )
    g = coord.build_graph()
    compiled = g.compile()
    final = await compiled.ainvoke({
        "task": "test",
        "plan": ["content", "analysis"],
        "account_id": "acct-1",
    })

    sub_results = final.get("sub_results", [])
    assert len(sub_results) == 2, (
        f"both sub-graphs must produce a slot in sub_results, got {len(sub_results)}"
    )
    # First slot is the exception (preserved by return_exceptions=True)
    assert isinstance(sub_results[0], BaseException), (
        f"first sub-result should be the captured exception, got {type(sub_results[0])}"
    )
    # Second slot is the analysis dict
    assert isinstance(sub_results[1], dict)
    assert sub_results[1].get("analysis", {}).get("score") == 99

    # Synthesise merges dicts, skips exceptions. The analysis result must
    # therefore still surface.
    merged = final.get("final", {})
    assert "analysis" in merged, (
        f"analysis must survive partial failure; final keys={sorted(merged.keys())}"
    )
    assert merged["analysis"]["ok"] is True


@pytest.mark.asyncio
async def test_fan_out_continues_when_analysis_subgraph_raises():
    """A raising analysis sub-graph must NOT abort the content sub-graph."""
    coord = CoordinatorAgent(
        content_agent=_AlwaysSucceedContentAgent(),
        analysis_agent=_AlwaysFailAnalysisAgent(),
    )
    g = coord.build_graph()
    compiled = g.compile()
    final = await compiled.ainvoke({
        "task": "test",
        "plan": ["content", "analysis"],
        "account_id": "acct-1",
    })

    sub_results = final.get("sub_results", [])
    assert len(sub_results) == 2
    assert isinstance(sub_results[0], dict)
    assert sub_results[0].get("draft", {}).get("title") == "t"
    assert isinstance(sub_results[1], BaseException)

    merged = final.get("final", {})
    assert "draft" in merged, "content draft must survive partial failure"
    # analysis should NOT be in merged (it raised)
    assert "analysis" not in merged


@pytest.mark.asyncio
async def test_fan_out_does_not_raise_when_both_subgraphs_fail():
    """Even if every sub-graph raises, the coordinator must not propagate the
    exception to the caller. ``sub_results`` carries the failures."""
    coord = CoordinatorAgent(
        content_agent=_AlwaysFailContentAgent(),
        analysis_agent=_AlwaysFailAnalysisAgent(),
    )
    g = coord.build_graph()
    compiled = g.compile()
    # If return_exceptions were missing this would raise.
    final = await compiled.ainvoke({
        "task": "test",
        "plan": ["content", "analysis"],
        "account_id": "acct-1",
    })

    sub_results = final.get("sub_results", [])
    assert len(sub_results) == 2
    assert all(isinstance(r, BaseException) for r in sub_results), (
        f"both sub-results should be exceptions, got types: {[type(r).__name__ for r in sub_results]}"
    )
    # Merged dict is empty since no dict sub-results exist.
    assert final.get("final", {}) == {}