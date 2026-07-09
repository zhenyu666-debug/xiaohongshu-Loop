"""LLM client wrappers using LangChain."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

from app.ai.config import settings


@dataclass
class LLMResponse:
    """A normalized LLM response."""
    content: str
    model: str
    usage: Dict[str, int] = None
    tool_calls: List[Dict[str, Any]] = None


class LLMClient:
    """LangChain-based LLM client supporting OpenAI, Anthropic, Ollama, and mock."""

    MOCK_RESPONSE = "(mock LLM response)"

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
    ):
        requested = provider or settings.llm_provider
        # Auto-fallback to mock when no API key is configured for the requested provider
        if requested in ("openai", "anthropic") and not (api_key or settings.llm_api_key):
            self.provider = "mock"
        else:
            self.provider = requested
        self.model = model or settings.default_model
        self.api_key = api_key or settings.llm_api_key
        self.base_url = base_url
        self.temperature = temperature
        self._chat = None
        self._embeddings = None

    def _get_chat(self):
        """Lazily build the LangChain chat model."""
        if self._chat is not None:
            return self._chat

        if self.provider == "openai":
            from langchain_openai import ChatOpenAI

            kwargs = {
                "model": self.model,
                "temperature": self.temperature,
            }
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._chat = ChatOpenAI(**kwargs)
        elif self.provider == "anthropic":
            try:
                from langchain_anthropic import ChatAnthropic
            except ImportError:
                raise ImportError(
                    "anthropic support requires langchain-anthropic: "
                    "pip install langchain-anthropic"
                )
            kwargs = {
                "model": self.model,
                "temperature": self.temperature,
            }
            if self.api_key:
                kwargs["api_key"] = self.api_key
            self._chat = ChatAnthropic(**kwargs)
        elif self.provider == "ollama":
            from langchain_community.chat_models import ChatOllama

            self._chat = ChatOllama(model=self.model, temperature=self.temperature)
        elif self.provider == "mock":
            self._chat = None
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

        return self._chat

    def _get_embeddings(self):
        """Lazily build the LangChain embeddings model."""
        if self._embeddings is not None:
            return self._embeddings

        if self.provider == "openai":
            from langchain_openai import OpenAIEmbeddings

            kwargs = {"model": settings.embedding_model}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            self._embeddings = OpenAIEmbeddings(**kwargs)
        else:
            from langchain_community.embeddings import FakeEmbeddings

            self._embeddings = FakeEmbeddings(size=1536)
        return self._embeddings

    async def ainvoke(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Async invoke the chat model."""
        if self.provider == "mock":
            return LLMResponse(content=self.MOCK_RESPONSE, model=self.model)

        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        chat = self._get_chat()
        lc_messages = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        invoke_kwargs = dict(kwargs)
        if tools:
            invoke_kwargs["tools"] = tools

        result = await chat.ainvoke(lc_messages, **invoke_kwargs)
        tool_calls = None
        if hasattr(result, "tool_calls") and result.tool_calls:
            tool_calls = [
                {"name": tc.get("name"), "args": tc.get("args"), "id": tc.get("id")}
                for tc in result.tool_calls
            ]
        return LLMResponse(
            content=result.content if isinstance(result.content, str) else str(result.content),
            model=self.model,
            tool_calls=tool_calls,
        )

    async def astream(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream tokens from the chat model."""
        if self.provider == "mock":
            yield self.MOCK_RESPONSE
            return

        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        chat = self._get_chat()
        lc_messages = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        async for chunk in chat.astream(lc_messages, **kwargs):
            if isinstance(chunk.content, str):
                yield chunk.content

    def bind_tools(self, tools: List[Any]):
        """Bind tools for OpenAI function calling."""
        if self.provider == "mock":
            return None
        chat = self._get_chat()
        return chat.bind_tools(tools)


def build_default_llm(**kwargs) -> LLMClient:
    """Build the default LLM client from settings."""
    return LLMClient(**kwargs)