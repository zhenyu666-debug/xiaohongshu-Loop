"""LangChain integration module.

Re-exports LangChain primitives used by the AI module.
"""
from app.ai.llm import LLMClient, LLMResponse, build_default_llm

__all__ = ["LLMClient", "LLMResponse", "build_default_llm"]