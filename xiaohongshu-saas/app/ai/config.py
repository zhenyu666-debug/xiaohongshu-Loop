"""AI configuration settings."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    """AI-related configuration."""

    model_config = SettingsConfigDict(env_prefix="AI_", extra="ignore")

    # LLM Settings
    llm_provider: Literal["openai", "anthropic", "ollama"] = "openai"
    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_base_url: str = "https://api.anthropic.com"
    default_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"

    # RAG Settings
    vector_store_type: Literal["chroma", "faiss", "qdrant"] = "chroma"
    vector_store_path: str = "data/embeddings"
    chunk_size: int = 512
    chunk_overlap: int = 50
    retrieval_top_k: int = 5
    use_reranker: bool = True

    # Agent Settings
    max_iterations: int = 10
    timeout_seconds: int = 120
    enable_multimodal: bool = False

    # Memory Settings
    memory_backend: Literal["redis", "sqlite", "memory"] = "memory"
    redis_url: Optional[str] = None
    short_term_max_items: int = 50
    long_term_importance_threshold: float = 0.7

    # MCP Settings
    mcp_enabled: bool = False
    mcp_server_url: Optional[str] = None

    @property
    def llm_api_key(self) -> Optional[str]:
        if self.llm_provider == "openai":
            return self.openai_api_key
        elif self.llm_provider == "anthropic":
            return self.anthropic_api_key
        return None


settings = AISettings()
