"""Retriever for hybrid search."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np

from app.ai.rag.vector_store import VectorEntry


@dataclass
class SearchResult:
    """A search result with score."""
    entry: VectorEntry
    score: float
    source: str = "vector"


class Retriever:
    """Hybrid retriever combining vector and keyword search."""

    def __init__(
        self,
        vector_store,
        embedder,
        top_k: int = 5,
        enable_rerank: bool = True
    ):
        self.vector_store = vector_store
        self.embedder = embedder
        self.top_k = top_k
        self.enable_rerank = enable_rerank
        self._texts: List[str] = []

    def index(self, texts: List[str], metadata: Optional[List[dict]] = None) -> None:
        """Index texts for retrieval."""
        self._texts = texts
        embeddings = self.embedder.embed_sync(texts)
        metadata = metadata or [{}] * len(texts)

        from app.ai.rag.vector_store import VectorEntry
        entries = [
            VectorEntry(
                id=f"doc_{i}",
                vector=emb,
                metadata={**meta, "text": text}
            )
            for i, (emb, text, meta) in enumerate(zip(embeddings, texts, metadata))
        ]
        self.vector_store.add(entries)

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[SearchResult]:
        """Retrieve relevant documents."""
        k = top_k or self.top_k

        # Vector search
        query_embedding = self.embedder.embed_sync([query])[0]
        results = self.vector_store.search(query_embedding, top_k=k)

        search_results = []
        for entry in results:
            # Compute simple keyword score
            score = 1.0
            query_words = set(query.lower().split())
            text_words = set(entry.metadata.get("text", "").lower().split())
            overlap = len(query_words & text_words)
            if overlap > 0:
                score = score * (1 + overlap * 0.1)

            search_results.append(SearchResult(
                entry=entry,
                score=score,
                source="vector"
            ))

        # Rerank if enabled
        if self.enable_rerank and len(search_results) > 1:
            search_results = self._rerank(query, search_results)

        return search_results[:k]

    def _rerank(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        """Rerank results using simple scoring."""
        query_words = set(query.lower().split())
        
        def rerank_score(result: SearchResult) -> float:
            text = result.entry.metadata.get("text", "").lower()
            text_words = set(text.split())
            
            # Position score (earlier is better)
            pos_score = 1.0 / (1 + result.entry.metadata.get("chunk_index", 0) * 0.01)
            
            # Keyword match score
            match_score = len(query_words & text_words) / max(len(query_words), 1)
            
            return result.score * 0.5 + pos_score * 0.2 + match_score * 0.3

        return sorted(results, key=rerank_score, reverse=True)
