"""Tests for MCP protocol module."""
import os
import sys
import tempfile

import pytest

from app.ai.mcp.protocol import (
    MCPMessage, MCPProtocol, MCPTool, MCPResource, MCPToolKind, get_mcp, initialize_mcp,
)


def test_mcp_message_request():
    msg = MCPMessage.request("test_method", {"x": 1})
    assert msg.jsonrpc == "2.0"
    assert msg.method == "test_method"
    assert msg.params == {"x": 1}


def test_mcp_message_response():
    msg = MCPMessage.response({"data": "test"}, "123")
    assert msg.result == {"data": "test"}
    assert msg.id == "123"


def test_mcp_message_error():
    msg = MCPMessage.make_error(-32600, "Invalid Request", "123")
    assert msg.error == {"code": -32600, "message": "Invalid Request"}


def test_mcp_message_to_dict():
    msg = MCPMessage.request("test", {"x": 1})
    data = msg.to_dict()
    assert data["jsonrpc"] == "2.0"


def test_mcp_message_from_dict():
    data = {"jsonrpc": "2.0", "id": "123", "method": "test", "params": {"x": 1}}
    msg = MCPMessage.from_dict(data)
    assert msg.method == "test"


def test_mcp_tool_creation():
    tool = MCPTool(name="t", description="d", input_schema={"type": "object"})
    assert tool.kind == MCPToolKind.FUNCTION


def test_mcp_tool_to_dict():
    tool = MCPTool(name="t", description="d", input_schema={"type": "object"})
    data = tool.to_dict()
    assert data["name"] == "t"


def test_mcp_resource_creation():
    resource = MCPResource(uri="file://test", name="Test")
    assert resource.uri == "file://test"


def test_mcp_resource_to_dict():
    resource = MCPResource(uri="test://r", name="R")
    data = resource.to_dict()
    assert data["uri"] == "test://r"


def test_mcp_protocol_register_tool():
    protocol = MCPProtocol()
    tool = MCPTool(name="t", description="d", input_schema={"type": "object"})
    protocol.register_tool(tool)
    assert "t" in protocol.tools


def test_mcp_protocol_register_resource():
    protocol = MCPProtocol()
    resource = MCPResource(uri="test://r", name="R")
    protocol.register_resource(resource)
    assert "test://r" in protocol.resources


def test_mcp_protocol_list_tools():
    protocol = MCPProtocol()
    protocol.register_tool(MCPTool(name="t1", description="d", input_schema={"type": "object"}))
    msg = MCPMessage.request("tools/list")
    response = protocol.handle_message(msg)
    assert response.result is not None


def test_mcp_protocol_list_resources():
    protocol = MCPProtocol()
    protocol.register_resource(MCPResource(uri="r1", name="R1"))
    msg = MCPMessage.request("resources/list")
    response = protocol.handle_message(msg)
    assert response.result is not None


def test_mcp_protocol_call_tool():
    protocol = MCPProtocol()
    protocol.register_tool(MCPTool(name="echo", description="Echo", input_schema={"type": "object"}))
    protocol.register_handler("tool:echo", lambda args: f"Echoed: {args}")
    msg = MCPMessage.request("tools/call", {"name": "echo", "arguments": {"text": "hello"}})
    response = protocol.handle_message(msg)
    assert response.result is not None


def test_mcp_protocol_unknown_tool():
    protocol = MCPProtocol()
    msg = MCPMessage.request("tools/call", {"name": "unknown", "arguments": {}})
    response = protocol.handle_message(msg)
    assert response.error is not None


def test_mcp_protocol_unknown_method():
    protocol = MCPProtocol()
    msg = MCPMessage.request("unknown_method")
    response = protocol.handle_message(msg)
    assert response.error is not None


def test_mcp_protocol_invalid_request():
    protocol = MCPProtocol()
    msg = MCPMessage(id="123")
    response = protocol.handle_message(msg)
    assert response.error is not None


def test_mcp_protocol_get_all_definitions():
    protocol = MCPProtocol()
    protocol.register_tool(MCPTool(name="t1", description="d", input_schema={}))
    protocol.register_resource(MCPResource(uri="r1", name="r"))
    defs = protocol.get_all_definitions()
    assert "tools" in defs
    assert "resources" in defs


def test_mcp_prompts_list():
    protocol = MCPProtocol()
    msg = MCPMessage.request("prompts/list")
    response = protocol.handle_message(msg)
    assert response.result is not None


def test_mcp_get_prompt():
    protocol = MCPProtocol()
    msg = MCPMessage.request("prompts/get", {
        "name": "content_creator",
        "arguments": {"topic": "AI", "style": "casual", "length": "short"}
    })
    response = protocol.handle_message(msg)
    assert response.result is not None


def test_get_mcp_singleton():
    mcp1 = get_mcp()
    mcp2 = get_mcp()
    assert mcp1 is mcp2


def test_initialize_mcp():
    mcp = initialize_mcp()
    assert mcp is not None


@pytest.mark.asyncio
async def test_mcp_in_process_round_trip():
    """Exercise the protocol + transport helpers without spawning a subprocess."""
    import json
    from app.ai.mcp.protocol import MCPProtocol, MCPMessage, initialize_mcp

    protocol = initialize_mcp()
    msg = MCPMessage.request("tools/list")
    response = protocol.handle_message(msg)
    payload = json.dumps(response.to_dict())
    parsed = json.loads(payload)
    assert "result" in parsed
    assert "tools" in parsed["result"]

    # Round-trip through from_dict/to_dict
    msg2 = MCPMessage.from_dict(parsed)
    assert msg2.jsonrpc == "2.0"
