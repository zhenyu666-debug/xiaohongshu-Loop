"""Tool registry for managing available tools."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass

from app.ai.tools.base import BaseTool, ToolDefinition, ToolResult


class ToolRegistry:
    """Registry for managing and accessing tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._functions: Dict[str, Callable] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        definition = tool.get_definition()
        self._tools[definition.name] = tool

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
        """Execute a tool by name."""
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
