"""Episodic memory: sequence of events as episodes.

Key fix vs. the legacy implementation: ``start_episode()`` now auto-closes any
in-flight episode (persisting it) before opening a new one. The legacy version
silently dropped the previous episode's events on each ``start_episode`` call.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.memory.db import MemoryDB


@dataclass
class Episode:
    id: str
    events: List[Dict[str, Any]]
    summary: str
    start_time: float
    end_time: float
    context: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class EpisodicMemory:
    """Episodic memory with auto-close on new start."""

    def __init__(
        self,
        db: MemoryDB,
        agent_id: str = "default",
        tenant_id: str = "default",
    ):
        self.db = db
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self._current_events: List[Dict[str, Any]] = []
        self._episode_start: Optional[float] = None
        self._episode_context: str = ""

    async def start_episode(self, context: str = "") -> None:
        """Start a new episode. If a previous episode is still open, persist it first."""
        if self._episode_start is not None and self._current_events:
            await self.end_episode(
                summary=self._episode_context or "(auto-closed)",
                metadata={"auto_closed": True},
            )
        self._current_events = []
        self._episode_start = time.time()
        self._episode_context = context

    async def add_event(self, event: Dict[str, Any]) -> None:
        if self._episode_start is None:
            await self.start_episode()
        event_with_time = {**event, "timestamp": time.time()}
        self._current_events.append(event_with_time)

    async def end_episode(
        self,
        summary: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if self._episode_start is None:
            return ""
        episode_id = uuid.uuid4().hex
        await self.db.upsert_episode(
            episode_id=episode_id,
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            summary=summary,
            context=self._episode_context,
            events=self._current_events,
            metadata=metadata or {},
            start_time=self._episode_start,
            end_time=time.time(),
        )
        self._current_events = []
        self._episode_start = None
        self._episode_context = ""
        return episode_id

    async def search(self, query: str, limit: int = 10) -> List[Episode]:
        episodes = await self.db.query_episodes(
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            limit=200,
        )
        q_lower = query.lower()
        scored = []
        for e in episodes:
            score = 0
            if q_lower in e["summary"].lower():
                score += 2
            if q_lower in e["context"].lower():
                score += 1
            for ev in e["events"]:
                blob = str(ev).lower()
                if q_lower in blob:
                    score += 1
                    break
            scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            Episode(
                id=e["id"],
                events=e["events"],
                summary=e["summary"],
                start_time=e["start_time"],
                end_time=e["end_time"],
                context=e["context"],
                metadata=e["metadata"],
            )
            for _, e in scored[:limit] if scored and scored[0][0] > 0
        ] or []

    @property
    def episode_count(self) -> int:
        return 0  # sync stub