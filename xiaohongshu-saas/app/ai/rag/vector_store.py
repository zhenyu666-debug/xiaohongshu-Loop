"""Vector store for storing and retrieving embeddings."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class VectorEntry:
    """A vector entry with metadata."""
    id: str
    vector: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseVectorStore(ABC):
    """Abstract base class for vector stores."""

    @abstractmethod
    def add(self, entries: List[VectorEntry]) -> None:
        pass

    @abstractmethod
    def search(self, query: List[float], top_k: int = 5) -> List[VectorEntry]:
        pass

    @abstractmethod
    def delete(self, ids: List[str]) -> None:
        pass

    @abstractmethod
    def count(self) -> int:
        pass


class InMemoryVectorStore(BaseVectorStore):
    """In-memory numpy vector store with cosine similarity."""

    def __init__(self, metric: str = "cosine"):
        self.entries: Dict[str, VectorEntry] = {}
        self.metric = metric
        self._matrix_cache: Optional[np.ndarray] = None
        self._id_list: List[str] = []

    def add(self, entries: List[VectorEntry]) -> None:
        for entry in entries:
            self.entries[entry.id] = entry
        self._rebuild_cache()

    def _rebuild_cache(self) -> None:
        if not self.entries:
            self._matrix_cache = None
            self._id_list = []
            return
        ids = list(self.entries.keys())
        vectors = []
        for entry_id in ids:
            vec = np.asarray(self.entries[entry_id].vector, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vectors.append(vec)
        self._matrix_cache = np.vstack(vectors)
        self._id_list = ids

    def search(self, query: List[float], top_k: int = 5) -> List[VectorEntry]:
        if not self.entries:
            return []

        query_vec = np.asarray(query, dtype=np.float32)
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            query_vec = query_vec / norm

        if self._matrix_cache is not None and len(self._matrix_cache) == len(self.entries):
            sims = self._matrix_cache @ query_vec
            if len(sims) <= top_k:
                top_indices = np.argsort(-sims)
            else:
                top_indices = np.argpartition(-sims, top_k)[:top_k]
                top_indices = top_indices[np.argsort(-sims[top_indices])]
            return [self.entries[self._id_list[i]] for i in top_indices]

        results = []
        for entry in self.entries.values():
            vec = np.array(entry.vector, dtype=np.float32)
            vec_norm = np.linalg.norm(vec)
            if vec_norm > 0:
                vec = vec / vec_norm
            similarity = float(np.dot(query_vec, vec))
            results.append((similarity, entry))
        results.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in results[:top_k]]

    def delete(self, ids: List[str]) -> None:
        for id in ids:
            self.entries.pop(id, None)
        self._rebuild_cache()

    def count(self) -> int:
        return len(self.entries)


class ChromaVectorStore(BaseVectorStore):
    """ChromaDB-backed vector store with on-disk persistence."""

    def __init__(self, persist_directory: str, collection_name: str = "default"):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            import chromadb

            self._client = chromadb.PersistentClient(path=self.persist_directory)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def add(self, entries: List[VectorEntry]) -> None:
        collection = self._get_collection()
        collection.add(
            ids=[e.id for e in entries],
            embeddings=[e.vector for e in entries],
            metadatas=[e.metadata for e in entries],
        )

    def search(self, query: List[float], top_k: int = 5) -> List[VectorEntry]:
        collection = self._get_collection()
        results = collection.query(query_embeddings=[query], n_results=top_k)
        entries = []
        ids = results.get("ids", [[]])[0]
        embs = results.get("embeddings", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        for i, id in enumerate(ids):
            entries.append(VectorEntry(
                id=id,
                vector=embs[i] if i < len(embs) else [],
                metadata=metas[i] if i < len(metas) and metas[i] else {},
            ))
        return entries

    def delete(self, ids: List[str]) -> None:
        collection = self._get_collection()
        collection.delete(ids=ids)

    def count(self) -> int:
        return self._get_collection().count()


class VectorStore:
    """Main vector store facade."""

    def __init__(self, store_type: str = "memory", **kwargs):
        self.store_type = store_type
        if store_type == "chroma":
            self.store: BaseVectorStore = ChromaVectorStore(**kwargs)
        else:
            self.store = InMemoryVectorStore(**kwargs)

    def add(self, entries: List[VectorEntry]) -> None:
        self.store.add(entries)

    def search(self, query: List[float], top_k: int = 5) -> List[VectorEntry]:
        return self.store.search(query, top_k)

    def delete(self, ids: List[str]) -> None:
        self.store.delete(ids)

    def count(self) -> int:
        return self.store.count()