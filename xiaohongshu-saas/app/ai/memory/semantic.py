"""Semantic memory for storing factual knowledge."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from pathlib import Path


@dataclass
class Fact:
    """A factual knowledge item."""
    id: str
    statement: str
    source: str
    confidence: float = 1.0
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SemanticMemory:
    """Store factual knowledge and concepts."""

    def __init__(
        self,
        storage_path: str = "data/memory/semantic",
        auto_save: bool = True,
        save_batch_size: int = 500,
    ):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._facts: Dict[str, Fact] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self.auto_save = auto_save
        self._dirty = False
        self._pending_count = 0
        self.save_batch_size = save_batch_size
        self._word_index: Dict[str, Set[str]] = {}
        self._load()

    def _load(self) -> None:
        """Load facts from disk (supports both index and individual files)."""
        index_path = self.storage_path / "_index.json"
        if index_path.exists():
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for fact_data in data.get("facts", []):
                    fact = self._make_fact(fact_data)
                    if fact is None:
                        continue
                    self._facts[fact.id] = fact
                    for tag in fact.tags:
                        if tag not in self._tag_index:
                            self._tag_index[tag] = set()
                        self._tag_index[tag].add(fact.id)
                    for word in set(fact.statement.lower().split()):
                        if len(word) > 2:
                            if word not in self._word_index:
                                self._word_index[word] = set()
                            self._word_index[word].add(fact.id)
                return
            except Exception:
                pass
        # Fallback: load individual files
        for file_path in self.storage_path.glob("*.json"):
            if file_path.name == "_index.json":
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                fact = self._make_fact(data)
                if fact is None:
                    continue
                self._facts[fact.id] = fact
                for tag in fact.tags:
                    if tag not in self._tag_index:
                        self._tag_index[tag] = set()
                    self._tag_index[tag].add(fact.id)
                for word in set(fact.statement.lower().split()):
                    if len(word) > 2:
                        if word not in self._word_index:
                            self._word_index[word] = set()
                        self._word_index[word].add(fact.id)
            except Exception:
                continue

    def _make_fact(self, data: Dict[str, Any]) -> "Fact":
        """Construct a Fact from raw dict."""
        try:
            return Fact(
                id=data["id"],
                statement=data["statement"],
                source=data.get("source", "unknown"),
                confidence=data.get("confidence", 1.0),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
                metadata=data.get("metadata", {})
            )
        except Exception:
            return None

    def flush(self) -> None:
        """Flush all facts in a single batched JSON file."""
        if not self._dirty:
            return
        index_path = self.storage_path / "_index.json"
        index_data = {
            "version": 1,
            "facts": [
                {
                    "id": fact.id,
                    "statement": fact.statement,
                    "source": fact.source,
                    "confidence": fact.confidence,
                    "tags": list(fact.tags),
                    "created_at": fact.created_at.isoformat(),
                    "updated_at": fact.updated_at.isoformat(),
                    "metadata": fact.metadata
                }
                for fact in self._facts.values()
            ]
        }
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False)
        # Delete individual files
        for fact_id in list(self._facts.keys()):
            individual = self.storage_path / f"{fact_id}.json"
            if individual.exists():
                try:
                    individual.unlink()
                except OSError:
                    pass
        self._dirty = False
        self._pending_count = 0

    def _save_one(self, fact: Fact) -> None:
        """Save fact to disk."""
        file_path = self.storage_path / f"{fact.id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({
                "id": fact.id,
                "statement": fact.statement,
                "source": fact.source,
                "confidence": fact.confidence,
                "tags": fact.tags,
                "created_at": fact.created_at.isoformat(),
                "updated_at": fact.updated_at.isoformat(),
                "metadata": fact.metadata
            }, f, ensure_ascii=False, indent=2)

    def store(
        self,
        statement: str,
        source: str,
        tags: Optional[List[str]] = None,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a fact."""
        import uuid
        fact_id = uuid.uuid4().hex[:16]
        
        fact = Fact(
            id=fact_id,
            statement=statement,
            source=source,
            tags=tags or [],
            confidence=confidence,
            metadata=metadata or {}
        )
        
        self._facts[fact_id] = fact
        
        # Update tag index
        for tag in fact.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(fact_id)

        # Update word index
        for word in set(fact.statement.lower().split()):
            if len(word) > 2:
                if word not in self._word_index:
                    self._word_index[word] = set()
                self._word_index[word].add(fact_id)

        if self.auto_save:
            self._dirty = True
            self._pending_count += 1
            if self._pending_count >= self.save_batch_size:
                self.flush()
        else:
            self._save_one(fact)
        return fact_id

    def recall(self, query: str, tags: Optional[List[str]] = None) -> List[Fact]:
        """Recall facts using inverted index for fast lookup."""
        if not query or not query.strip():
            return []

        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 2]

        # Build candidate set
        candidate_ids = None
        if tags:
            candidate_ids = set()
            for tag in tags:
                if tag in self._tag_index:
                    if not candidate_ids:
                        candidate_ids = set(self._tag_index[tag])
                    else:
                        candidate_ids &= self._tag_index[tag]

        # Use word index to find candidates
        for word in query_words:
            word_candidates = self._word_index.get(word, set())
            if candidate_ids is None:
                candidate_ids = set(word_candidates)
            else:
                candidate_ids &= word_candidates

        # Fallback to full scan if no candidates
        if candidate_ids is None:
            candidate_ids = set(self._facts.keys())

        results = []
        for fid in candidate_ids:
            fact = self._facts.get(fid)
            if fact is None:
                continue
            if (query_lower in fact.statement.lower() or
                any(query_lower in tag.lower() for tag in fact.tags)):
                results.append((fact.confidence, fact))

        results.sort(key=lambda x: x[0], reverse=True)
        return [fact for _, fact in results]

    def get_by_tags(self, tags: List[str]) -> List[Fact]:
        """Get facts by tags (union)."""
        result_ids = set()
        for tag in tags:
            if tag in self._tag_index:
                result_ids |= self._tag_index[tag]
        
        return [self._facts[fid] for fid in result_ids if fid in self._facts]

    def update_confidence(self, fact_id: str, confidence: float) -> bool:
        """Update fact confidence."""
        if fact_id in self._facts:
            self._facts[fact_id].confidence = confidence
            self._facts[fact_id].updated_at = datetime.now()
            self._save_one(self._facts[fact_id])
            return True
        return False

    def delete(self, fact_id: str) -> bool:
        """Delete a fact."""
        if fact_id in self._facts:
            fact = self._facts[fact_id]
            
            # Remove from tag index
            for tag in fact.tags:
                if tag in self._tag_index:
                    self._tag_index[tag].discard(fact_id)
            
            # Remove file
            file_path = self.storage_path / f"{fact_id}.json"
            if file_path.exists():
                file_path.unlink()
            
            del self._facts[fact_id]
            return True
        return False

    def get_all_tags(self) -> List[str]:
        """Get all unique tags."""
        return list(self._tag_index.keys())

    @property
    def fact_count(self) -> int:
        """Get total number of facts."""
        return len(self._facts)
