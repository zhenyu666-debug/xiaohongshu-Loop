"""Rerankers for search results. Cross-encoder is the production path."""
from __future__ import annotations

from typing import List, Optional

from app.ai.rag.retriever import SearchResult


class Reranker:
    """Keyword-overlap reranker. Lightweight, no model dependency, used as a fallback."""

    def __init__(self, model: str = "keyword"):
        self.model = model

    def rerank(self, query: str, results: List[SearchResult], top_n: int = 5) -> List[SearchResult]:
        if not results:
            return []
        scored = [(self._compute_relevance(query, r), r) for r in results]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:top_n]]

    @staticmethod
    def _compute_relevance(query: str, result: SearchResult) -> float:
        query_lower = query.lower()
        text = result.entry.metadata.get("text", "").lower()
        q_words = set(query_lower.split())
        t_words = set(text.split())
        overlap = len(q_words & t_words)
        base = result.score if result.score else 0.5
        if query_lower in text:
            base *= 1.5
        if overlap:
            base *= (1 + overlap * 0.1)
        return min(base, 1.0)


class CrossEncoderReranker:
    """Cross-encoder reranker backed by sentence-transformers.

    Falls back to keyword Reranker if the model can't be loaded (e.g. offline CI).
    """

    DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: str = DEFAULT_MODEL, fallback: Optional[Reranker] = None):
        self.model_name = model_name
        self._model = None
        self._fallback = fallback or Reranker()
        self._load_error: Optional[str] = None

    def _load_model(self):
        if self._model is not None or self._load_error is not None:
            return
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
        except Exception as e:
            self._load_error = str(e)
            self._model = None

    def rerank(self, query: str, results: List[SearchResult], top_n: int = 5) -> List[SearchResult]:
        if not results:
            return []
        self._load_model()
        if self._model is None:
            return self._fallback.rerank(query, results, top_n)
        pairs = [(query, r.entry.metadata.get("text", "")) for r in results]
        try:
            scores = self._model.predict(pairs).tolist()
        except Exception:
            return self._fallback.rerank(query, results, top_n)
        scored = list(zip(scores, results))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:top_n]]