"""Base tool class for function calling."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolDefinition:
    """Definition of a tool for function calling."""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters.get("properties", {}),
                    "required": self.parameters.get("required", [])
                }
            }
        }


@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata
        }


class BaseTool(ABC):
    """Abstract base class for all tools."""

    @abstractmethod
    def get_definition(self) -> ToolDefinition:
        """Get the tool definition."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool."""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Get JSON schema for this tool."""
        return self.get_definition().to_openai_format()
