"""Tool registry for managing available tools."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass

from app.ai.tools.base import BaseTool, ToolDefinition, ToolResult
from app.ai.tools.rate_limit import RateLimiterRegistry, RateLimitExceeded


class ToolRegistry:
    """Registry for managing and accessing tools.

    Each tool may be configured with a per-tool token-bucket rate limit
    via :meth:`configure_rate_limit`. Calls that exceed the budget are
    rejected with :class:`RateLimitExceeded` (returned as a failed
    ``ToolResult`` from :meth:`execute`).
    """

    def __init__(
        self,
        default_rate_per_minute: float = 60.0,
        default_capacity: float = 10.0,
        rate_limiter: Optional[RateLimiterRegistry] = None,
    ):
        self._tools: Dict[str, BaseTool] = {}
        self._functions: Dict[str, Callable] = {}
        self._rate_limiter = rate_limiter or RateLimiterRegistry(
            default_rate_per_minute=default_rate_per_minute,
            default_capacity=default_capacity,
        )
        self._disabled: set[str] = set()

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        definition = tool.get_definition()
        self._tools[definition.name] = tool
        # Auto-create a rate-limit bucket for the tool at the registry's default
        # rate. Tools can override via configure_rate_limit() after registration.
        self._rate_limiter.get(definition.name)

    def configure_rate_limit(
        self,
        tool_name: str,
        rate_per_minute: float,
        capacity: float = 10.0,
    ) -> None:
        """Set or override the rate limit for a registered tool.

        ``rate_per_minute <= 0`` disables limiting for the tool.
        """
        self._rate_limiter.configure(
            tool_name,
            rate_per_minute=rate_per_minute,
            capacity=capacity,
        )

    def disable_tool(self, tool_name: str) -> None:
        """Disable a tool. Calls return an error result without execution."""
        self._disabled.add(tool_name)

    def enable_tool(self, tool_name: str) -> None:
        """Re-enable a previously disabled tool."""
        self._disabled.discard(tool_name)

    def is_disabled(self, tool_name: str) -> bool:
        return tool_name in self._disabled

    @property
    def rate_limiter(self) -> RateLimiterRegistry:
        return self._rate_limiter

    def register_function(self, name: str, func: Callable, description: str = "") -> None:
        """Register a simple function as a tool."""
        self._functions[name] = {
            "func": func,
            "description": description
        }

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_function(self, name: str) -> Optional[Callable]:
        """Get a function by name."""
        func_data = self._functions.get(name)
        return func_data["func"] if func_data else None

    def list_tools(self) -> List[ToolDefinition]:
        """List all registered tool definitions."""
        return [tool.get_definition() for tool in self._tools.values()]

    def list_function_definitions(self) -> List[Dict[str, Any]]:
        """List all function definitions."""
        return [
            {
                "name": name,
                "description": data["description"],
                "parameters": {"type": "object", "properties": {}}
            }
            for name, data in self._functions.items()
        ]

    async def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name.

        - Disabled tools return ``ToolResult(success=False, error="disabled")``
        - Over-budget calls return ``ToolResult(success=False, error="rate_limited")``
          with metadata ``retry_after`` and ``limit_per_minute`` for backoff
        - Exceptions in the tool body are caught and returned as failed results
        """
        if name in self._disabled:
            return ToolResult(
                success=False,
                error=f"Tool '{name}' is disabled",
                metadata={"reason": "disabled"},
            )

        if not await self._rate_limiter.get(name).acquire():
            bucket = self._rate_limiter.get(name)
            # ``retry_after`` may be sync (in-process bucket) or async
            # (Redis-backed bucket). Await only when needed.
            ra = bucket.retry_after()
            if asyncio.iscoroutine(ra):
                ra = await ra
            return ToolResult(
                success=False,
                error=f"Rate limit exceeded for tool '{name}'",
                metadata={
                    "reason": "rate_limited",
                    "retry_after": ra,
                    "limit_per_minute": bucket.rate_per_minute,
                },
            )

        tool = self.get(name)
        if tool:
            try:
                return await tool.execute(**kwargs)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        func = self.get_function(name)
        if func:
            try:
                result = func(**kwargs)
                if hasattr(result, "__await__"):
                    result = await result
                return ToolResult(success=True, data=result)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        return ToolResult(success=False, error=f"Tool '{name}' not found")

    def get_all_definitions(self) -> List[Dict[str, Any]]:
        """Get all tool definitions (both BaseTool and functions)."""
        definitions = []
        
        # Add BaseTool definitions
        for tool in self._tools.values():
            definitions.append(tool.get_schema())
        
        # Add function definitions
        for name, data in self._functions.items():
            definitions.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": data["description"],
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            })
        
        return definitions


# Global registry instance
tool_registry = ToolRegistry()


def register_tool(tool: BaseTool) -> None:
    """Register a tool to the global registry."""
    tool_registry.register(tool)


def get_tool(name: str) -> Optional[BaseTool]:
    """Get a tool from the global registry."""
    return tool_registry.get(name)


def list_all_tools() -> List[ToolDefinition]:
    """List all tools in the global registry."""
    return tool_registry.list_tools()
