"""Vector store for storing and retrieving embeddings."""
from __future__ import annotations

import json
import os
import pickle
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
        """Add entries to the store."""
        pass

    @abstractmethod

    def _rebuild_cache(self) -> None:
        """Rebuild numpy matrix cache for fast batch search."""
        import numpy as np
        if not self.entries:
            self._matrix_cache = None
            self._id_list = []
            return
        ids = list(self.entries.keys())
        vectors = []
        for entry_id in ids:
            entry = self.entries[entry_id]
            vec = np.asarray(entry.vector, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vectors.append(vec)
        self._matrix_cache = np.vstack(vectors)
        self._id_list = [self.entries[i] for i in ids]

    def search(self, query: List[float], top_k: int = 5) -> List[VectorEntry]:
        """Search for similar entries."""
        pass

    @abstractmethod
    def delete(self, ids: List[str]) -> None:
        """Delete entries by ID."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Get the number of entries."""
        pass


class InMemoryVectorStore(BaseVectorStore):
    """Simple in-memory vector store."""

    def __init__(self, metric: str = "cosine"):
        self.entries: Dict[str, VectorEntry] = {}
        self.metric = metric
        self._matrix_cache = None
        self._id_list = []

    def add(self, entries: List[VectorEntry]) -> None:
        """Add entries to memory."""
        for entry in entries:
            self.entries[entry.id] = entry
        self._rebuild_cache()


    def _rebuild_cache(self) -> None:
        """Rebuild numpy matrix cache for fast batch search."""
        import numpy as np
        if not self.entries:
            self._matrix_cache = None
            self._id_list = []
            return
        ids = list(self.entries.keys())
        vectors = []
        for entry_id in ids:
            entry = self.entries[entry_id]
            vec = np.asarray(entry.vector, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vectors.append(vec)
        self._matrix_cache = np.vstack(vectors)
        self._id_list = [self.entries[i] for i in ids]

    def search(self, query: List[float], top_k: int = 5) -> List[VectorEntry]:
        """Search for similar entries using numpy and heap."""
        import numpy as np
        import heapq

        if self._matrix_cache is None and not self.entries:
            return []

        query_vec = np.asarray(query, dtype=np.float32)
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            query_vec = query_vec / norm

        # Use pre-built matrix cache if available
        if self._matrix_cache is not None and len(self._matrix_cache) == len(self.entries):
            # Batch cosine similarity
            sims = self._matrix_cache @ query_vec  # (N,) dot product
            # Use argpartition for top-k (faster than full sort)
            if len(sims) <= top_k:
                top_indices = np.argsort(-sims)
            else:
                top_indices = np.argpartition(-sims, top_k)[:top_k]
                top_indices = top_indices[np.argsort(-sims[top_indices])]
            return [self._id_list[i] for i in top_indices]
        else:
            # Fallback to original logic
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


    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity."""
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    @staticmethod
    def _euclidean_distance(a: np.ndarray, b: np.ndarray) -> float:
        """Compute euclidean distance."""
        return float(np.linalg.norm(a - b))

    def delete(self, ids: List[str]) -> None:
        """Delete entries by ID."""
        for id in ids:
            if id in self.entries:
                del self.entries[id]

    def count(self) -> int:
        """Get entry count."""
        return len(self.entries)


class ChromaVectorStore(BaseVectorStore):
    """ChromaDB vector store."""

    def __init__(self, persist_directory: str, collection_name: str = "default"):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def _get_collection(self):
        """Get or create ChromaDB collection."""
        if self._collection is None:
            try:
                import chromadb
                self._client = chromadb.PersistentClient(path=self.persist_directory)
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name
                )
            except ImportError:
                raise ImportError("chromadb required: pip install chromadb")
        return self._collection

    def add(self, entries: List[VectorEntry]) -> None:
        """Add entries to ChromaDB."""
        collection = self._get_collection()
        ids = [e.id for e in entries]
        embeddings = [e.vector for e in entries]
        metadatas = [e.metadata for e in entries]
        
        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas
        )


    def _rebuild_cache(self) -> None:
        """Rebuild numpy matrix cache for fast batch search."""
        import numpy as np
        if not self.entries:
            self._matrix_cache = None
            self._id_list = []
            return
        ids = list(self.entries.keys())
        vectors = []
        for entry_id in ids:
            entry = self.entries[entry_id]
            vec = np.asarray(entry.vector, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vectors.append(vec)
        self._matrix_cache = np.vstack(vectors)
        self._id_list = [self.entries[i] for i in ids]

    def search(self, query: List[float], top_k: int = 5) -> List[VectorEntry]:
        """Search ChromaDB."""
        collection = self._get_collection()
        results = collection.query(
            query_embeddings=[query],
            n_results=top_k
        )

        entries = []
        for i, id in enumerate(results["ids"][0]):
            entries.append(VectorEntry(
                id=id,
                vector=results["embeddings"][0][i],
                metadata=results["metadatas"][0][i] if results["metadatas"] else {}
            ))
        return entries

    def delete(self, ids: List[str]) -> None:
        """Delete from ChromaDB."""
        collection = self._get_collection()
        collection.delete(ids=ids)

    def count(self) -> int:
        """Get count from ChromaDB."""
        collection = self._get_collection()
        return collection.count()


class VectorStore:
    """Main vector store facade."""

    def __init__(self, store_type: str = "memory", **kwargs):
        self.store_type = store_type
        if store_type == "chroma":
            self.store = ChromaVectorStore(**kwargs)
        else:
            self.store = InMemoryVectorStore(**kwargs)

    def add(self, entries: List[VectorEntry]) -> None:
        """Add entries."""
        self.store.add(entries)


    def _rebuild_cache(self) -> None:
        """Rebuild numpy matrix cache for fast batch search."""
        import numpy as np
        if not self.entries:
            self._matrix_cache = None
            self._id_list = []
            return
        ids = list(self.entries.keys())
        vectors = []
        for entry_id in ids:
            entry = self.entries[entry_id]
            vec = np.asarray(entry.vector, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vectors.append(vec)
        self._matrix_cache = np.vstack(vectors)
        self._id_list = [self.entries[i] for i in ids]

    def search(self, query: List[float], top_k: int = 5) -> List[VectorEntry]:
        """Search entries."""
        return self.store.search(query, top_k)

    def delete(self, ids: List[str]) -> None:
        """Delete entries."""
        self.store.delete(ids)

    def count(self) -> int:
        """Get entry count."""
        return self.store.count()
