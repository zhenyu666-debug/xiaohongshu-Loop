"""Answer generator using LLM."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from app.ai.rag.retriever import SearchResult


@dataclass
class GenerationResult:
    """Result from generation."""
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float


class Generator:
    """Generate answers using retrieved context."""

    def __init__(
        self,
        llm_provider: str = "mock",
        model: str = "gpt-4o",
        api_key: Optional[str] = None
    ):
        self.llm_provider = llm_provider
        self.model = model
        self.api_key = api_key

    async def generate(
        self,
        query: str,
        context: List[SearchResult],
        system_prompt: Optional[str] = None
    ) -> GenerationResult:
        """Generate answer using context."""
        # Build context string
        context_str = self._build_context(context)
        
        # Build prompt
        prompt = self._build_prompt(query, context_str)
        
        if self.llm_provider == "openai":
            return await self._generate_openai(prompt, context)
        elif self.llm_provider == "anthropic":
            return await self._generate_anthropic(prompt, context)
        else:
            return self._generate_mock(query, context)

    def _build_context(self, context: List[SearchResult]) -> str:
        """Build context string from search results."""
        parts = []
        for i, result in enumerate(context, 1):
            text = result.entry.metadata.get("text", "")
            source = result.entry.metadata.get("source", "unknown")
            parts.append(f"[{i}] Source: {source}\n{text}\n")
        return "\n".join(parts)

    def _build_prompt(self, query: str, context: str) -> str:
        """Build prompt for generation."""
        return f"""Based on the following context, answer the question.

Context:
{context}

Question: {query}

Answer (in Chinese if the question is in Chinese):"""

    async def _generate_openai(self, prompt: str, context: List[SearchResult]) -> GenerationResult:
        """Generate using OpenAI."""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            answer = response.choices[0].message.content
            
            return GenerationResult(
                answer=answer,
                sources=[{
                    "text": r.entry.metadata.get("text", "")[:200],
                    "source": r.entry.metadata.get("source", "unknown"),
                    "score": r.score
                } for r in context],
                confidence=0.8
            )
        except Exception as e:
            return GenerationResult(
                answer=f"Error: {str(e)}",
                sources=[],
                confidence=0.0
            )

    async def _generate_anthropic(self, prompt: str, context: List[SearchResult]) -> GenerationResult:
        """Generate using Anthropic."""
        # Similar to OpenAI but with Claude API
        return await self._generate_openai(prompt, context)

    def _generate_mock(self, query: str, context: List[SearchResult]) -> GenerationResult:
        """Generate mock response for testing."""
        if not context:
            return GenerationResult(
                answer="No relevant information found.",
                sources=[],
                confidence=0.0
            )

        top_text = context[0].entry.metadata.get("text", "")[:200]
        return GenerationResult(
            answer=f"Based on the retrieved information: {top_text}...",
            sources=[{
                "text": top_text,
                "source": context[0].entry.metadata.get("source", "unknown"),
                "score": context[0].score
            }],
            confidence=0.7
        )


class RAGPipeline:
    """Complete RAG pipeline."""

    def __init__(
        self,
        embedder,
        vector_store,
        retriever,
        generator
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.retriever = retriever
        self.generator = generator

    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Index documents for retrieval."""
        texts = [doc["content"] for doc in documents]
        metadata = [{"source": doc.get("source", "unknown")} for doc in documents]
        self.retriever.index(texts, metadata)

    async def query(self, question: str, top_k: int = 5) -> GenerationResult:
        """Query the RAG pipeline."""
        results = self.retriever.retrieve(question, top_k=top_k)
        return await self.generator.generate(question, results)
