"""Embedder for text vectorization."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
import numpy as np


class BaseEmbedder(ABC):
    """Abstract base class for text embedders."""

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts into vectors."""
        pass

    @abstractmethod
    def embed_sync(self, texts: List[str]) -> List[List[float]]:
        """Synchronous embedding."""
        pass


class MockEmbedder(BaseEmbedder):
    """Mock embedder for testing."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Return mock embeddings."""
        return self.embed_sync(texts)

    def embed_sync(self, texts: List[str]) -> List[List[float]]:
        """Generate deterministic mock embeddings."""
        embeddings = []
        for text in texts:
            # Simple hash-based mock embedding
            seed = sum(ord(c) for c in text[:100])
            np.random.seed(seed)
            vector = np.random.randn(384).tolist()
            embeddings.append(vector)
        return embeddings


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI text embedder."""

    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts using OpenAI API."""
        client = self._get_client()
        try:
            response = await client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            raise RuntimeError(f"OpenAI embedding failed: {e}")

    def embed_sync(self, texts: List[str]) -> List[List[float]]:
        """Synchronous embedding using OpenAI."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            response = client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except ImportError:
            raise ImportError("openai package required: pip install openai")


class Embedder:
    """Main embedder facade."""

    def __init__(self, provider: str = "mock", **kwargs):
        self.provider = provider
        if provider == "openai":
            self.embedder = OpenAIEmbedder(**kwargs)
        else:
            self.embedder = MockEmbedder()

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts."""
        return await self.embedder.embed(texts)

    def embed_sync(self, texts: List[str]) -> List[List[float]]:
        """Synchronous embedding."""
        return self.embedder.embed_sync(texts)

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        if isinstance(self.embedder, MockEmbedder):
            return 384
        return 1536  # OpenAI default
