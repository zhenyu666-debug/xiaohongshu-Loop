"""Content creation agent as a StateGraph: route -> plan -> generate -> review -> revise."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from app.ai.agents.base import AgentConfig, AgentMessage, AgentRole, BaseAgent
from app.ai.agents.graph import END, StateGraph
from app.ai.config import settings
from app.ai.llm import build_default_llm
from app.ai.prompts.templates import load_prompt


SYSTEM_PROMPT = """You are an expert Xiaohongshu content creator.

Your abilities:
1. Analyze user needs and generate engaging titles
2. Create posts in Xiaohongshu style (conversational, emoji-rich, rhythmic)
3. Recommend appropriate hashtags
4. Optimize content based on performance data

Writing style:
- Conversational, like chatting with a friend
- 2-3 sentences per paragraph, with blank lines between
- Use emojis appropriately to add vitality
- Avoid exaggerated marketing language
- Titles under 20 characters

Output format:
```json
{"title": "...", "body": "...", "hashtags": ["..."], "tips": ["..."]}
```
"""


REVIEW_PROMPT = """You are a strict Xiaohongshu content reviewer. Given the draft below,
decide if it should be REVISED or APPROVED.

Criteria for REVISED:
- Title is missing or longer than 20 characters
- Body lacks conversational tone
- Fewer than 2 hashtags

Reply with one word on the first line: REVISED or APPROVED.
Then on a new line, one sentence of feedback.

Draft:
{draft}
"""


class ContentAgent(BaseAgent):
    """StateGraph-backed content agent: 5-node graph with revise loop."""

    def __init__(self, llm_provider: Optional[str] = None, llm_model: Optional[str] = None):
        super().__init__(AgentConfig(
            name="content_creator",
            role=AgentRole.EXECUTOR,
            system_prompt=SYSTEM_PROMPT,
        ))
        self.llm_provider = llm_provider or settings.llm_provider
        self.llm_model = llm_model or settings.default_model

    def build_graph(self) -> StateGraph:
        graph = StateGraph()

        async def route(state: Dict[str, Any]) -> Dict[str, Any]:
            topic = state.get("topic", "")
            return {"topic": topic, "intent": "create"}

        async def plan(state: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "style": state.get("style", "casual"),
                "length": state.get("length", "medium"),
                "plan": f"Write a Xiaohongshu post about {state['topic']}",
            }

        async def generate(state: Dict[str, Any]) -> Dict[str, Any]:
            llm = build_default_llm(provider=self.llm_provider, model=self.llm_model)
            prompt = load_prompt(
                "content_creator",
                topic=state["topic"],
                style=state.get("style", "casual"),
                length=state.get("length", "medium"),
            )
            response = await llm.ainvoke([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ])
            text = response.content
            # Try to extract JSON
            draft = _try_parse_json(text)
            if draft is None:
                draft = {"title": state["topic"][:18], "body": text, "hashtags": []}
            state.setdefault("revisions", 0)
            return {"draft": draft, "raw": text}

        async def review(state: Dict[str, Any]) -> Dict[str, Any]:
            llm = build_default_llm(provider=self.llm_provider, model=self.llm_model)
            if self.llm_provider == "mock":
                # Don't burn an LLM call in tests; treat any draft as approved.
                return {"verdict": "APPROVED", "feedback": "(skipped in mock)"}
            review_text = REVIEW_PROMPT.format(draft=json.dumps(state["draft"], ensure_ascii=False))
            resp = await llm.ainvoke([{"role": "user", "content": review_text}])
            verdict = "REVISED" if "REVISED" in resp.content.upper() else "APPROVED"
            return {"verdict": verdict, "feedback": resp.content}

        async def revise(state: Dict[str, Any]) -> Dict[str, Any]:
            return {"revisions": state.get("revisions", 0) + 1}

        def route_to_revise_or_finish(state: Dict[str, Any]) -> str:
            verdict = state.get("verdict", "APPROVED")
            revisions = state.get("revisions", 0)
            if verdict == "REVISED" and revisions < 2:
                return "revise"
            return "finish"

        graph.add_node("route", route)
        graph.add_node("plan", plan)
        graph.add_node("generate", generate)
        graph.add_node("review", review)
        graph.add_node("revise", revise)

        graph.set_entry_point("route")
        graph.add_edge("route", "plan")
        graph.add_edge("plan", "generate")
        graph.add_edge("generate", "review")
        graph.add_conditional_edges("review", route_to_revise_or_finish, {"revise": "revise", "finish": END()})
        graph.add_edge("revise", "generate")
        return graph

    async def create_content(self, topic: str, style: str = "casual", length: str = "medium") -> dict:
        graph = self.build_graph().compile()
        result = await graph.ainvoke({"topic": topic, "style": style, "length": length})
        return result.get("draft", {"title": topic, "body": "", "hashtags": []})

    async def think(self, context):  # legacy hook
        last = context[-1].content if context else ""
        return f"Creating content for: {last}"

    async def act(self, thought: str):  # legacy hook
        return [AgentMessage(role="assistant", content=thought, sender=self.name)]


def _try_parse_json(text: str) -> Optional[dict]:
    text = text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(line for line in lines if not line.startswith("```"))
    try:
        return json.loads(text)
    except Exception:
        # Find first {...} block
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return None
    return None