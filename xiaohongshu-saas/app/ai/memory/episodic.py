"""Episodic memory for storing experience sequences."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path


@dataclass
class Episode:
    """An episodic memory episode."""
    id: str
    events: List[Dict[str, Any]]
    summary: str
    start_time: datetime
    end_time: datetime
    context: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class EpisodicMemory:
    """Store sequences of experiences as episodes."""

    def __init__(self, storage_path: str = "data/memory/episodes"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._episodes: Dict[str, Episode] = {}
        self._current_episode: List[Dict[str, Any]] = []
        self._episode_start: Optional[datetime] = None
        self._load()

    def _load(self) -> None:
        """Load episodes from disk."""
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    episode = Episode(
                        id=data["id"],
                        events=data["events"],
                        summary=data["summary"],
                        start_time=datetime.fromisoformat(data["start_time"]),
                        end_time=datetime.fromisoformat(data["end_time"]),
                        context=data.get("context", ""),
                        metadata=data.get("metadata", {})
                    )
                    self._episodes[episode.id] = episode
            except Exception:
                pass

    def _save(self, episode: Episode) -> None:
        """Save episode to disk."""
        file_path = self.storage_path / f"{episode.id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({
                "id": episode.id,
                "events": episode.events,
                "summary": episode.summary,
                "start_time": episode.start_time.isoformat(),
                "end_time": episode.end_time.isoformat(),
                "context": episode.context,
                "metadata": episode.metadata
            }, f, ensure_ascii=False, indent=2)

    def start_episode(self, context: str = "") -> None:
        """Start a new episode."""
        import hashlib
        self._current_episode = []
        self._episode_start = datetime.now()
        self._episode_context = context

    def add_event(self, event: Dict[str, Any]) -> None:
        """Add an event to the current episode."""
        event_with_time = {
            **event,
            "timestamp": datetime.now().isoformat()
        }
        self._current_episode.append(event_with_time)

    def end_episode(self, summary: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """End the current episode and store it."""
        if not self._current_episode or not self._episode_start:
            return ""
        
        import hashlib
        episode_id = hashlib.md5(
            f"{summary}{self._episode_start.isoformat()}".encode()
        ).hexdigest()[:16]
        
        episode = Episode(
            id=episode_id,
            events=self._current_episode.copy(),
            summary=summary,
            start_time=self._episode_start,
            end_time=datetime.now(),
            context=getattr(self, "_episode_context", ""),
            metadata=metadata or {}
        )
        
        self._episodes[episode_id] = episode
        self._save(episode)
        
        self._current_episode = []
        self._episode_start = None
        
        return episode_id

    def get_episode(self, episode_id: str) -> Optional[Episode]:
        """Get an episode by ID."""
        return self._episodes.get(episode_id)

    def get_recent_episodes(self, limit: int = 10) -> List[Episode]:
        """Get recent episodes."""
        sorted_episodes = sorted(
            self._episodes.values(),
            key=lambda x: x.end_time,
            reverse=True
        )
        return sorted_episodes[:limit]

    def search_episodes(self, query: str) -> List[Episode]:
        """Search episodes by summary or context."""
        query_lower = query.lower()
        results = []
        
        for episode in self._episodes.values():
            if (query_lower in episode.summary.lower() or
                query_lower in episode.context.lower()):
                results.append(episode)
        
        return results

    def get_current_episode(self) -> List[Dict[str, Any]]:
        """Get events from the current episode."""
        return self._current_episode.copy()

    @property
    def episode_count(self) -> int:
        """Get total number of episodes."""
        return len(self._episodes)
