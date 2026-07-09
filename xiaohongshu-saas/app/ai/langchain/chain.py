"""LangChain integration for AI agents."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ChainConfig:
    """Configuration for a chain."""
    name: str
    llm_provider: str = "mock"
    model: str = "gpt-4o"
    temperature: float = 0.7
    system_prompt: Optional[str] = None


class BaseChain:
    """Base class for LangChain-like chains."""

    def __init__(self, config: ChainConfig):
        self.config = config

    async def run(self, input: str, **kwargs) -> str:
        """Run the chain."""
        raise NotImplementedError


class SimpleChain(BaseChain):
    """Simple chain: prompt -> LLM -> output."""

    async def run(self, input: str, **kwargs) -> str:
        """Run simple chain."""
        # Mock LLM response
        return f"Processed: {input}"


class RetrievalChain(BaseChain):
    """RAG chain: retrieve -> generate."""

    def __init__(self, config: ChainConfig, retriever=None, generator=None):
        super().__init__(config)
        self.retriever = retriever
        self.generator = generator

    async def run(self, input: str, **kwargs) -> Dict[str, Any]:
        """Run retrieval chain."""
        if not self.retriever:
            return {"answer": f"No retriever: {input}", "sources": []}
        
        results = self.retriever.retrieve(input)
        
        if not self.generator:
            return {
                "answer": f"Found {len(results)} results for: {input}",
                "sources": [r.entry.metadata for r in results]
            }
        
        generation = await self.generator.generate(input, results)
        return {
            "answer": generation.answer,
            "sources": generation.sources,
            "confidence": generation.confidence
        }


class AgentChain(BaseChain):
    """Agent chain with tool usage."""

    def __init__(self, config: ChainConfig, agent=None, tools: List[Any] = None):
        super().__init__(config)
        self.agent = agent
        self.tools = tools or []

    async def run(self, input: str, **kwargs) -> str:
        """Run agent chain."""
        if not self.agent:
            return f"Agent response for: {input}"
        
        from app.ai.agents.base import AgentMessage
        msg = AgentMessage(role="user", content=input)
        response = await self.agent.run(msg)
        return response.content


class ConversationChain(BaseChain):
    """Conversation chain with memory."""

    def __init__(self, config: ChainConfig, memory_manager=None, llm=None):
        super().__init__(config)
        self.memory = memory_manager
        self.llm = llm

    async def run(self, input: str, **kwargs) -> str:
        """Run conversation chain."""
        # Add to memory
        if self.memory:
            await self.memory.add(input, memory_type="short")
        
        # Get context
        context = ""
        if self.memory:
            context = self.memory.get_context()
        
        # Generate response (mock)
        response = f"Context-aware response to: {input}"
        if context:
            response = f"Based on context: {context[:100]}... Response: {response}"
        
        return response


def create_chain(chain_type: str, config: ChainConfig, **kwargs) -> BaseChain:
    """Create a chain by type."""
    if chain_type == "simple":
        return SimpleChain(config)
    elif chain_type == "retrieval":
        return RetrievalChain(config, kwargs.get("retriever"), kwargs.get("generator"))
    elif chain_type == "agent":
        return AgentChain(config, kwargs.get("agent"), kwargs.get("tools"))
    elif chain_type == "conversation":
        return ConversationChain(config, kwargs.get("memory"), kwargs.get("llm"))
    else:
        return SimpleChain(config)


async def run_chain(chain: BaseChain, input: str, **kwargs) -> Any:
    """Run a chain."""
    result = await chain.run(input, **kwargs)
    return result
