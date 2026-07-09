"""MCP protocol implementation for tool standardization."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MCPMessageType(str, Enum):
    """MCP message types."""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"


class MCPToolKind(str, Enum):
    """Tool kinds in MCP."""
    FUNCTION = "function"
    PROMPT = "prompt"
    RESOURCE = "resource"


@dataclass
class MCPTool:
    """An MCP tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    kind: MCPToolKind = MCPToolKind.FUNCTION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "kind": self.kind.value
        }


@dataclass
class MCPResource:
    """An MCP resource."""
    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type
        }


@dataclass
class MCPMessage:
    """An MCP message."""
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def request(
        cls,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        msg_id: Optional[str] = None
    ) -> "MCPMessage":
        """Create a request message."""
        return cls(
            jsonrpc="2.0",
            id=msg_id or str(datetime.now().timestamp()),
            method=method,
            params=params
        )

    @classmethod
    def response(
        cls,
        result: Any,
        msg_id: str
    ) -> "MCPMessage":
        """Create a response message."""
        return cls(
            jsonrpc="2.0",
            id=msg_id,
            result=result
        )

    @classmethod
    def make_error(
        cls,
        code: int,
        message: str,
        msg_id: Optional[str] = None
    ) -> "MCPMessage":
        """Create an error message."""
        return cls(
            jsonrpc="2.0",
            id=msg_id,
            error={"code": code, "message": message}
        )

    def to_dict(self) -> Dict[str, Any]:
        result = {"jsonrpc": self.jsonrpc}
        
        if self.id is not None:
            result["id"] = self.id
        if self.method is not None:
            result["method"] = self.method
        if self.params is not None:
            result["params"] = self.params
        if self.result is not None:
            result["result"] = self.result
        if self.error is not None:
            result["error"] = self.error
        
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPMessage":
        """Parse from dictionary."""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error")
        )


class MCPProtocol:
    """MCP protocol handler."""

    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self._handlers: Dict[str, callable] = {}

    def register_tool(self, tool: MCPTool) -> None:
        """Register a tool."""
        self.tools[tool.name] = tool

    def register_resource(self, resource: MCPResource) -> None:
        """Register a resource."""
        self.resources[resource.uri] = resource

    def register_handler(self, method: str, handler: callable) -> None:
        """Register a method handler."""
        self._handlers[method] = handler

    def handle_message(self, message: MCPMessage) -> MCPMessage:
        """Handle an MCP message."""
        if message.method is None:
            return MCPMessage.make_error(-32600, "Invalid Request", message.id)

        # Built-in methods
        if message.method == "tools/list":
            return self._handle_list_tools(message)
        elif message.method == "tools/call":
            return self._handle_call_tool(message)
        elif message.method == "resources/list":
            return self._handle_list_resources(message)
        elif message.method == "resources/read":
            return self._handle_read_resource(message)
        elif message.method == "prompts/list":
            return self._handle_list_prompts(message)
        elif message.method == "prompts/get":
            return self._handle_get_prompt(message)
        
        # Custom handlers
        handler = self._handlers.get(message.method)
        if handler:
            try:
                result = handler(message.params or {})
                return MCPMessage.response(result, message.id or "")
            except Exception as e:
                return MCPMessage.make_error(-32603, str(e), message.id)

        return MCPMessage.make_error(-32601, f"Method not found: {message.method}", message.id)

    def _handle_list_tools(self, message: MCPMessage) -> MCPMessage:
        """Handle tools/list."""
        tools_list = [tool.to_dict() for tool in self.tools.values()]
        return MCPMessage.response({"tools": tools_list}, message.id or "")

    def _handle_call_tool(self, message: MCPMessage) -> MCPMessage:
        """Handle tools/call."""
        params = message.params or {}
        tool_name = params.get("name")
        
        if tool_name not in self.tools:
            return MCPMessage.make_error(-32602, f"Tool not found: {tool_name}", message.id)
        
        tool = self.tools[tool_name]
        arguments = params.get("arguments", {})
        
        # Execute tool
        handler = self._handlers.get(f"tool:{tool_name}")
        if handler:
            try:
                result = handler(arguments)
                return MCPMessage.response({"content": result}, message.id or "")
            except Exception as e:
                return MCPMessage.make_error(-32603, str(e), message.id)
        
        return MCPMessage.response({"content": f"Tool {tool_name} executed"}, message.id or "")

    def _handle_list_resources(self, message: MCPMessage) -> MCPMessage:
        """Handle resources/list."""
        resources_list = [r.to_dict() for r in self.resources.values()]
        return MCPMessage.response({"resources": resources_list}, message.id or "")

    def _handle_read_resource(self, message: MCPMessage) -> MCPMessage:
        """Handle resources/read."""
        params = message.params or {}
        uri = params.get("uri")
        
        if uri not in self.resources:
            return MCPMessage.make_error(-32602, f"Resource not found: {uri}", message.id)
        
        resource = self.resources[uri]
        return MCPMessage.response({
            "contents": [{
                "uri": uri,
                "mimeType": resource.mime_type,
                "text": f"Resource: {resource.name}"
            }]
        }, message.id or "")

    def _handle_list_prompts(self, message: MCPMessage) -> MCPMessage:
        """Handle prompts/list."""
        from app.ai.prompts.templates import list_templates
        prompts = [{"name": name} for name in list_templates()]
        return MCPMessage.response({"prompts": prompts}, message.id or "")

    def _handle_get_prompt(self, message: MCPMessage) -> MCPMessage:
        """Handle prompts/get."""
        params = message.params or {}
        name = params.get("name")
        arguments = params.get("arguments", {})
        
        from app.ai.prompts.templates import load_prompt, get_template
        template = get_template(name)
        if not template:
            return MCPMessage.make_error(-32602, f"Prompt not found: {name}", message.id)
        
        prompt_text = template.render(**arguments)
        return MCPMessage.response({
            "messages": [{"role": "user", "content": prompt_text}]
        }, message.id or "")

    def get_all_definitions(self) -> Dict[str, Any]:
        """Get all MCP definitions."""
        return {
            "tools": [tool.to_dict() for tool in self.tools.values()],
            "resources": [r.to_dict() for r in self.resources.values()]
        }


# Global MCP instance
_mcp_protocol: Optional[MCPProtocol] = None


def get_mcp() -> MCPProtocol:
    """Get the global MCP protocol instance."""
    global _mcp_protocol
    if _mcp_protocol is None:
        _mcp_protocol = MCPProtocol()
    return _mcp_protocol


def initialize_mcp() -> MCPProtocol:
    """Initialize MCP with tools and resources."""
    mcp = get_mcp()
    
    # Register tools from tool registry
    from app.ai.tools.registry import tool_registry
    for tool_def in tool_registry.list_tools():
        mcp.register_tool(MCPTool(
            name=tool_def.name,
            description=tool_def.description,
            input_schema={"type": "object", "properties": tool_def.parameters.get("properties", {})}
        ))
    
    return mcp
