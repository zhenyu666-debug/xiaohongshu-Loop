"""Embedder for text vectorization."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
import hashlib

import numpy as np

from app.ai.config import settings


class BaseEmbedder(ABC):
    """Abstract base class for text embedders."""

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        pass

    @abstractmethod
    def embed_sync(self, texts: List[str]) -> List[List[float]]:
        pass


class MockEmbedder(BaseEmbedder):
    """Deterministic mock embedder (used for tests only)."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    async def embed(self, texts: List[str]) -> List[List[float]]:
        return self.embed_sync(texts)

    def embed_sync(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            h = hashlib.md5(text.encode("utf-8", errors="ignore")).digest()
            seed = int.from_bytes(h[:4], "big")
            rng = np.random.default_rng(seed)
            embeddings.append(rng.standard_normal(self.dim).tolist())
        return embeddings


class LangChainEmbedder(BaseEmbedder):
    """LangChain-based embedder. Defaults to OpenAI."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.provider = provider or settings.llm_provider
        self.model = model or settings.embedding_model
        self.api_key = api_key or settings.llm_api_key
        self._embeddings = None

    def _get_embeddings(self):
        if self._embeddings is not None:
            return self._embeddings
        if self.provider == "openai":
            from langchain_openai import OpenAIEmbeddings

            kwargs = {"model": self.model}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            self._embeddings = OpenAIEmbeddings(**kwargs)
        elif self.provider == "huggingface":
            from langchain_community.embeddings import HuggingFaceEmbeddings

            self._embeddings = HuggingFaceEmbeddings(model_name=self.model)
        else:
            from langchain_community.embeddings import FakeEmbeddings

            self._embeddings = FakeEmbeddings(size=1536)
        return self._embeddings

    async def embed(self, texts: List[str]) -> List[List[float]]:
        embeddings = self._get_embeddings()
        return await embeddings.aembed_documents(texts)

    def embed_sync(self, texts: List[str]) -> List[List[float]]:
        embeddings = self._get_embeddings()
        if hasattr(embeddings, "embed_documents"):
            return embeddings.embed_documents(texts)
        return [embeddings.embed_query(t) for t in texts]


class Embedder:
    """Main embedder facade. Defaults to OpenAI when a key is available."""

    def __init__(self, provider: Optional[str] = None, **kwargs):
        env_provider = provider or settings.llm_provider
        # Auto-fallback to mock when no API key is configured
        if env_provider in ("openai", "anthropic") and not settings.llm_api_key:
            env_provider = "mock"
        if env_provider == "mock":
            self.embedder: BaseEmbedder = MockEmbedder(**kwargs)
        else:
            self.embedder = LangChainEmbedder(provider=env_provider, **kwargs)

    async def embed(self, texts: List[str]) -> List[List[float]]:
        return await self.embedder.embed(texts)

    def embed_sync(self, texts: List[str]) -> List[List[float]]:
        return self.embedder.embed_sync(texts)

    @property
    def dimension(self) -> int:
        if isinstance(self.embedder, MockEmbedder):
            return self.embedder.dim
        return 1536