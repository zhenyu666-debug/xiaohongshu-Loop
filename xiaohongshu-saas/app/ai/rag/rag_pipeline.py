"""RAG pipeline factory helpers."""
from __future__ import annotations

from typing import Any, Optional

from app.ai.config import settings
from app.ai.rag.embedder import Embedder
from app.ai.rag.generator import Generator, RAGPipeline
from app.ai.rag.reranker import Reranker, CrossEncoderReranker
from app.ai.rag.retriever import Retriever
from app.ai.rag.vector_store import VectorStore


def build_default_rag_pipeline(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    use_cross_encoder: bool = False,
    store_type: Optional[str] = None,
) -> RAGPipeline:
    """Build a complete RAG pipeline from settings.

    Defaults to in-memory vector store and keyword reranker unless overridden.
    Set ``use_cross_encoder=True`` for the production reranker (requires the
    ``sentence-transformers`` package and a downloaded model). The default
    ``store_type`` is ``memory`` to avoid requiring ChromaDB initialization;
    pass ``store_type="chroma"`` explicitly when persist_directory is set.
    """
    embedder = Embedder(provider=provider or "mock")
    store = VectorStore(store_type=store_type or "memory")
    retriever = Retriever(
        vector_store=store.store,
        embedder=embedder,
        top_k=settings.retrieval_top_k,
        enable_rerank=settings.use_reranker,
    )
    reranker = CrossEncoderReranker() if use_cross_encoder else Reranker()
    generator = Generator(provider=provider or "mock", model=model or settings.default_model)
    return RAGPipeline(embedder=embedder, vector_store=store.store, retriever=retriever, generator=generator)