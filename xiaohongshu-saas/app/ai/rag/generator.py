"""Answer generator using LangChain chat models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

from app.ai.config import settings
from app.ai.rag.retriever import SearchResult


@dataclass
class GenerationResult:
    """Result from generation."""
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float


class Generator:
    """Generate answers using retrieved context, with anti-hallucination guard."""

    DEFAULT_SYSTEM_PROMPT = (
        "You are a careful research assistant. Answer the user's question using ONLY the "
        "numbered context snippets provided below. If the answer cannot be derived from the "
        "context, reply exactly: I don't know. Cite sources inline as [1], [2], etc. Never "
        "fabricate facts, numbers, or names that are not present in the context. Reply in the "
        "same language as the user's question."
    )

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        self.provider = provider or settings.llm_provider
        self.model = model or settings.default_model
        self.api_key = api_key or settings.llm_api_key
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

    def _build_messages(
        self,
        query: str,
        context: List[SearchResult],
    ) -> List[Dict[str, str]]:
        context_str = self._build_context(context)
        user_prompt = (
            f"Context snippets (cite inline as [1], [2], ...):\n"
            f"{context_str}\n\n"
            f"Question: {query}\n\n"
            f"Answer:"
        )
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    @staticmethod
    def _build_context(context: List[SearchResult]) -> str:
        parts = []
        for i, result in enumerate(context, 1):
            text = result.entry.metadata.get("text", "")
            source = result.entry.metadata.get("source", "unknown")
            parts.append(f"[{i}] Source: {source}\n{text}\n")
        return "\n".join(parts)

    async def generate(
        self,
        query: str,
        context: List[SearchResult],
    ) -> GenerationResult:
        if not context:
            return GenerationResult(
                answer="I don't know.",
                sources=[],
                confidence=0.0,
            )
        from app.ai.llm import build_default_llm

        llm = build_default_llm(
            provider=self.provider,
            model=self.model,
            api_key=self.api_key,
        )
        messages = self._build_messages(query, context)
        try:
            response = await llm.ainvoke(messages)
            answer = response.content
            sources = [
                {
                    "text": r.entry.metadata.get("text", "")[:200],
                    "source": r.entry.metadata.get("source", "unknown"),
                    "score": float(r.score),
                }
                for r in context
            ]
            confidence = 0.0 if "I don't know" in answer else 0.85
            return GenerationResult(answer=answer, sources=sources, confidence=confidence)
        except Exception as e:
            return GenerationResult(
                answer=f"Error generating answer: {e}",
                sources=[],
                confidence=0.0,
            )

    async def generate_stream(
        self,
        query: str,
        context: List[SearchResult],
    ) -> AsyncIterator[str]:
        if not context:
            yield "I don't know."
            return
        from app.ai.llm import build_default_llm

        llm = build_default_llm(
            provider=self.provider,
            model=self.model,
            api_key=self.api_key,
        )
        messages = self._build_messages(query, context)
        async for token in llm.astream(messages):
            yield token


class RAGPipeline:
    """Complete RAG pipeline."""

    def __init__(self, embedder, vector_store, retriever, generator):
        self.embedder = embedder
        self.vector_store = vector_store
        self.retriever = retriever
        self.generator = generator

    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        texts = [doc["content"] for doc in documents]
        metadata = [{"source": doc.get("source", "unknown")} for doc in documents]
        self.retriever.index(texts, metadata)

    async def query(self, question: str, top_k: int = 5) -> GenerationResult:
        results = self.retriever.retrieve(question, top_k=top_k)
        return await self.generator.generate(question, results)

    async def query_stream(self, question: str, top_k: int = 5) -> AsyncIterator[str]:
        results = self.retriever.retrieve(question, top_k=top_k)
        async for token in self.generator.generate_stream(question, results):
            yield token