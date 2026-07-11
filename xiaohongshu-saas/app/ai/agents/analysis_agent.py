"""Analysis agent as a StateGraph: plan -> query_rag -> synthesize -> format."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.ai.agents.base import AgentConfig, AgentMessage, AgentRole, BaseAgent
from app.ai.agents.graph import END, StateGraph
from app.ai.config import settings
from app.ai.llm import build_default_llm
from app.ai.rag.rag_pipeline import build_default_rag_pipeline


ANALYSIS_SYSTEM = """You are a data analysis expert focused on Xiaohongshu account operations.

Output format:
```json
{"score": 0-100, "strengths": [...], "weaknesses": [...], "recommendations": [...]}
```
"""


class AnalysisAgent(BaseAgent):
    """StateGraph-backed analysis agent that uses the RAG pipeline as a node."""

    def __init__(self, llm_provider: Optional[str] = None, llm_model: Optional[str] = None, rag=None):
        super().__init__(AgentConfig(
            name="data_analyst",
            role=AgentRole.REVIEWER,
            system_prompt=ANALYSIS_SYSTEM,
        ))
        self.llm_provider = llm_provider or settings.llm_provider
        self.llm_model = llm_model or settings.default_model
        self.rag = rag  # optional pre-built RAGPipeline

    def build_graph(self) -> StateGraph:
        graph = StateGraph()

        async def plan(state: Dict[str, Any]) -> Dict[str, Any]:
            return {"query": f"Performance analysis for account {state['account_id']}"}

        async def query_rag(state: Dict[str, Any]) -> Dict[str, Any]:
            pipeline = self.rag or build_default_rag_pipeline(provider=self.llm_provider, model=self.llm_model)
            results = pipeline.retriever.retrieve(state["query"], top_k=3)
            return {"context": [r.entry.metadata.get("text", "") for r in results]}

        async def synthesize(state: Dict[str, Any]) -> Dict[str, Any]:
            llm = build_default_llm(provider=self.llm_provider, model=self.llm_model)
            if self.llm_provider == "mock":
                return {
                    "analysis": {
                        "score": 72,
                        "strengths": ["Accurate topic selection"],
                        "weaknesses": ["Low engagement rate"],
                        "recommendations": [{"action": "Add Q&A content", "expected_impact": "+15% engagement"}],
                    }
                }
            prompt = (
                f"Account: {state['account_id']}\n"
                f"Context:\n" + "\n".join(state.get("context", []))
                + "\n\nProvide the analysis in the specified JSON format."
            )
            response = await llm.ainvoke([
                {"role": "system", "content": ANALYSIS_SYSTEM},
                {"role": "user", "content": prompt},
            ])
            return {"analysis": _try_parse_json(response.content) or {"raw": response.content}}

        graph.add_node("plan", plan)
        graph.add_node("query_rag", query_rag)
        graph.add_node("synthesize", synthesize)
        graph.set_entry_point("plan")
        graph.add_edge("plan", "query_rag")
        graph.add_edge("query_rag", "synthesize")
        graph.add_edge("synthesize", END())
        return graph

    async def analyze_account(self, account_id: str, period: str = "7d") -> Dict[str, Any]:
        graph = self.build_graph().compile()
        result = await graph.ainvoke({"account_id": account_id, "period": period})
        return result.get("analysis", {})

    async def think(self, context):  # legacy hook
        last = context[-1].content if context else ""
        return f"Analyzing data: {last[:100]}"

    async def act(self, thought: str):  # legacy hook
        return [AgentMessage(role="assistant", content=thought, sender=self.name)]


def _try_parse_json(text: str) -> Optional[dict]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(line for line in lines if not line.startswith("```"))
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return None
    return None