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

    def __init__(self, storage_path: str = "data/memory/semantic"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._facts: Dict[str, Fact] = {}
        self._tag_index: Dict[str, Set[str]] = {}  # tag -> fact_ids
        self._load()

    def _load(self) -> None:
        """Load facts from disk."""
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    fact = Fact(
                        id=data["id"],
                        statement=data["statement"],
                        source=data.get("source", "unknown"),
                        confidence=data.get("confidence", 1.0),
                        tags=data.get("tags", []),
                        created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
                        updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
                        metadata=data.get("metadata", {})
                    )
                    self._facts[fact.id] = fact
                    
                    # Update tag index
                    for tag in fact.tags:
                        if tag not in self._tag_index:
                            self._tag_index[tag] = set()
                        self._tag_index[tag].add(fact.id)
            except Exception:
                pass

    def _save(self, fact: Fact) -> None:
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
        import hashlib
        fact_id = hashlib.md5(statement.encode()).hexdigest()[:16]
        
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
        
        self._save(fact)
        return fact_id

    def recall(self, query: str, tags: Optional[List[str]] = None) -> List[Fact]:
        """Recall facts matching query."""
        results = []
        query_lower = query.lower()
        
        # If tags specified, start with those
        if tags:
            candidate_ids = set()
            for tag in tags:
                if tag in self._tag_index:
                    if not candidate_ids:
                        candidate_ids = self._tag_index[tag]
                    else:
                        candidate_ids &= self._tag_index[tag]
            
            candidates = [self._facts[fid] for fid in candidate_ids if fid in self._facts]
        else:
            candidates = self._facts.values()
        
        # Filter by query
        for fact in candidates:
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
            self._save(self._facts[fact_id])
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
