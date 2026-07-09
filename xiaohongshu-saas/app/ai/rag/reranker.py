"""Reranker for improving search results."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.ai.rag.retriever import SearchResult


class Reranker:
    """Rerank search results for better relevance."""

    def __init__(self, model: str = "mock"):
        self.model = model

    def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_n: int = 5
    ) -> List[SearchResult]:
        """Rerank results based on query relevance."""
        if not results:
            return []

        scored_results = []
        for result in results:
            score = self._compute_relevance(query, result)
            scored_results.append((score, result))

        # Sort by score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        return [r for _, r in scored_results[:top_n]]

    def _compute_relevance(self, query: str, result: SearchResult) -> float:
        """Compute relevance score."""
        query_lower = query.lower()
        text = result.entry.metadata.get("text", "").lower()
        
        # Keyword overlap
        query_words = set(query_lower.split())
        text_words = set(text.split())
        overlap = len(query_words & text_words)
        
        # BM25-like scoring
        base_score = result.score if result.score else 0.5
        
        # Boost for exact matches
        if query_lower in text:
            base_score *= 1.5
        
        # Boost for word overlap
        if overlap > 0:
            base_score *= (1 + overlap * 0.1)

        return min(base_score, 1.0)
