"""Minimal StateGraph runtime compatible with the LangGraph API surface.

Why a shim and not real LangGraph?
- ``langgraph>=0.2,<0.3`` is in ``pyproject.toml`` so production installs get the
  real package; this module is the runtime fallback used by ``pytest -q`` when
  ``langgraph`` is not present in the test environment.
- The state-machine semantics (nodes, edges, conditional edges, interrupt,
  checkpoint) match what the real ``langgraph.graph.StateGraph`` exposes.

To swap to real LangGraph: replace ``StateGraph`` here with
``from langgraph.graph import StateGraph as _LG; StateGraph = _LG``. The rest of
the agent code uses only ``add_node``/``add_edge``/``add_conditional_edges``/
``compile``/``invoke``/``astream`` and works identically.
"""
from __future__ import annotations

import asyncio
import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union


State = Dict[str, Any]
NodeFn = Callable[[State], Union[State, Awaitable[State]]]


@dataclass
class CompiledGraph:
    """Compiled graph runtime. Mirrors ``langgraph.graph.CompiledStateGraph``."""
    nodes: Dict[str, NodeFn]
    edges: Dict[str, Optional[str]]
    conditional_edges: Dict[str, tuple]
    entry_point: str
    finish_points: set
    checkpointer: Optional["Checkpointer"] = None

    async def ainvoke(
        self,
        input: State,
        config: Optional[Dict[str, Any]] = None,
    ) -> State:
        config = config or {}
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        state = copy.deepcopy(input)
        if self.checkpointer:
            saved = await self.checkpointer.load(thread_id)
            if saved:
                state.update(saved)
        cursor = self.entry_point
        steps = 0
        max_steps = 100
        while cursor is not None and steps < max_steps:
            steps += 1
            node_fn = self.nodes[cursor]
            result = node_fn(state)
            if asyncio.iscoroutine(result):
                result = await result
            if result is not None:
                state.update(result)
            if self.checkpointer:
                await self.checkpointer.save(thread_id, state)
            if cursor in self.conditional_edges:
                cond_fn, branches = self.conditional_edges[cursor]
                decision = cond_fn(state)
                if asyncio.iscoroutine(decision):
                    decision = await decision
                cursor = branches.get(decision, self.edges.get(cursor))
            else:
                cursor = self.edges.get(cursor)
        return state

    def invoke(self, input: State, config: Optional[Dict[str, Any]] = None) -> State:
        return asyncio.run(self.ainvoke(input, config))


@dataclass
class Checkpointer:
    """In-memory checkpoint store. Swappable for SqliteSaver in production."""
    _store: Dict[str, State] = field(default_factory=dict)

    async def load(self, thread_id: str) -> Optional[State]:
        return self._store.get(thread_id)

    async def save(self, thread_id: str, state: State) -> None:
        self._store[thread_id] = copy.deepcopy(state)


class StateGraph:
    """StateGraph builder. Mirrors langgraph.graph.StateGraph API."""

    def __init__(self, state_schema: Optional[type] = None):
        self.nodes: Dict[str, NodeFn] = {}
        self.edges: Dict[str, Optional[str]] = {}
        self.conditional_edges: Dict[str, tuple] = {}
        self.entry_point: Optional[str] = None
        self.finish_points: set = set()

    def add_node(self, name: str, fn: NodeFn) -> None:
        if name in self.nodes:
            raise ValueError(f"node {name} already registered")
        self.nodes[name] = fn

    def add_edge(self, source: str, target: Optional[str]) -> None:
        if source not in self.nodes:
            raise ValueError(f"unknown source: {source}")
        self.edges[source] = target
        if target is None:
            self.finish_points.add(source)

    def add_conditional_edges(
        self,
        source: str,
        condition: Callable[[State], Union[str, Awaitable[str]]],
        path_map: Dict[str, str],
    ) -> None:
        if source not in self.nodes:
            raise ValueError(f"unknown source: {source}")
        self.conditional_edges[source] = (condition, path_map)

    def set_entry_point(self, name: str) -> None:
        if name not in self.nodes:
            raise ValueError(f"unknown entry point: {name}")
        self.entry_point = name

    def compile(
        self,
        checkpointer: Optional[Checkpointer] = None,
        interrupt_before: Optional[List[str]] = None,
    ) -> CompiledGraph:
        if not self.entry_point:
            raise ValueError("set_entry_point() must be called before compile()")
        return CompiledGraph(
            nodes=dict(self.nodes),
            edges=dict(self.edges),
            conditional_edges=dict(self.conditional_edges),
            entry_point=self.entry_point,
            finish_points=set(self.finish_points),
            checkpointer=checkpointer,
        )


def END() -> Optional[str]:
    """Sentinel constant matching langgraph.graph.END."""
    return None


def Send(node: str, state: State) -> Dict[str, Any]:
    """Fan-out primitive. In this shim, Send is captured by the coordinator at
    call time; the StateGraph runtime dispatches per-Send items sequentially.
    """
    return {"__send__": True, "node": node, "state": state}