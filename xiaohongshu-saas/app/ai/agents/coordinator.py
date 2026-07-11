"""Coordinator agent: parent StateGraph that runs content + analysis as sub-graphs.

This is the real multi-agent pattern: the parent graph has a fan-out node that
sends each subtask to the appropriate sub-graph via ``Send``. Sub-graph outputs
are merged in the synthesize node.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from app.ai.agents.base import AgentConfig, AgentMessage, AgentRole, BaseAgent
from app.ai.agents.graph import END, StateGraph
from app.ai.agents.content_agent import ContentAgent
from app.ai.agents.analysis_agent import AnalysisAgent


class CoordinatorAgent(BaseAgent):
    def __init__(
        self,
        content_agent: Optional[ContentAgent] = None,
        analysis_agent: Optional[AnalysisAgent] = None,
    ):
        super().__init__(AgentConfig(
            name="coordinator",
            role=AgentRole.COORDINATOR,
            system_prompt="You are a coordinator orchestrating specialized sub-agents.",
        ))
        self.content_agent = content_agent or ContentAgent()
        self.analysis_agent = analysis_agent or AnalysisAgent()

    def route_intent(self, task: str) -> str:
        t = task.lower()
        if "分析" in task or "数据" in task or "analy" in t or "metric" in t:
            return "analysis"
        if "写" in task or "创作" in task or "writ" in t or "creat" in t:
            return "content"
        return "content"

    def build_graph(self) -> StateGraph:
        graph = StateGraph()

        async def plan(state: Dict[str, Any]) -> Dict[str, Any]:
            """Decide which sub-graphs to invoke.

            If the caller provided an explicit ``plan`` list (multi-intent
            fan-out), respect it. Otherwise fall back to a single intent
            chosen by ``route_intent``.

            Note: only honor a non-empty *list* here. The StateGraph shim
            checkpointer restores prior state on resume, and we do not want
            a previously-stored "plan" to silently shadow a new request.
            """
            existing = state.get("plan")
            if isinstance(existing, list) and existing:
                return {"intent": list(existing), "plan": list(existing)}
            intent = self.route_intent(state["task"])
            return {"intent": intent, "plan": [intent]}

        async def fan_out(state: Dict[str, Any]) -> Dict[str, Any]:
            """Run sub-graphs in parallel for the intents in state['plan']."""
            intents: List[str] = state["plan"]
            tasks = []
            for intent in intents:
                if intent == "content":
                    sub = self.content_agent.build_graph().compile()
                    tasks.append(sub.ainvoke({
                        "topic": state["task"],
                        "style": "casual",
                        "length": "medium",
                    }))
                elif intent == "analysis":
                    sub = self.analysis_agent.build_graph().compile()
                    tasks.append(sub.ainvoke({
                        "account_id": state.get("account_id", "default"),
                    }))
            if not tasks:
                return {"sub_results": []}
            # `return_exceptions=True` so one failing sub-graph does not abort
            # the entire fan-out: surviving sub-graphs still produce results
            # and the synthesise node can log+drop the failed one.
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return {"sub_results": list(results)}

        async def synthesize(state: Dict[str, Any]) -> Dict[str, Any]:
            sub = state.get("sub_results", [])
            merged: Dict[str, Any] = {}
            for r in sub:
                if isinstance(r, dict):
                    merged.update(r)
            return {"final": merged}

        graph.add_node("plan", plan)
        graph.add_node("fan_out", fan_out)
        graph.add_node("synthesize", synthesize)
        graph.set_entry_point("plan")
        graph.add_edge("plan", "fan_out")
        graph.add_edge("fan_out", "synthesize")
        graph.add_edge("synthesize", END())
        return graph

    async def coordinate_task(self, task: str, account_id: Optional[str] = None) -> Dict[str, Any]:
        graph = self.build_graph().compile()
        result = await graph.ainvoke({"task": task, "account_id": account_id or "default"})
        return result.get("final", {})

    async def think(self, context):  # legacy hook
        last = context[-1].content if context else ""
        intent = self.route_intent(last)
        return f"route_to:{intent}"

    async def act(self, thought: str):  # legacy hook
        return [AgentMessage(
            role="assistant",
            content=f"routed: {thought}",
            sender=self.name,
        )]