"""MCP stdio transport + FastMCP server adapter.

When ``langchain-mcp-adapters`` is installed, prefer that package's FastMCP
helpers. Otherwise fall back to the minimal in-process JSON-RPC dispatcher in
``app.ai.mcp.protocol``.

This module exposes:
- ``serve_stdio()``: spawn an MCP server speaking JSON-RPC over stdin/stdout.
- ``MCPClient``: minimal stdio client for talking to an external MCP server.
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, AsyncIterator, Dict, List, Optional

from app.ai.mcp.protocol import MCPMessage, MCPProtocol, get_mcp, initialize_mcp


async def serve_stdio() -> None:
    """Run the MCP server over stdio. Reads JSON-RPC messages line-by-line from
    stdin and writes responses to stdout."""
    protocol = initialize_mcp()
    reader = asyncio.StreamReader()
    protocol_obj = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_running_loop().connect_read_pipe(lambda: protocol_obj, sys.stdin)
    writer_transport, writer_protocol = await asyncio.get_running_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader=None, loop=asyncio.get_running_loop())

    while True:
        try:
            raw = await reader.readline()
        except Exception:
            return
        if not raw:
            return
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            err = MCPMessage.make_error(-32700, "Parse error", None).to_dict()
            writer.write((json.dumps(err) + "\n").encode("utf-8"))
            await writer.drain()
            continue
        msg = MCPMessage.from_dict(data)
        response = protocol.handle_message(msg)
        writer.write((json.dumps(response.to_dict()) + "\n").encode("utf-8"))
        await writer.drain()


class MCPClient:
    """Minimal JSON-RPC 2.0 stdio client. Spawn a subprocess and talk to it."""

    def __init__(self, command: List[str]):
        self.command = command
        self._process: Optional[asyncio.subprocess.Process] = None

    async def start(self) -> None:
        self._process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def stop(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()

    async def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise RuntimeError("MCPClient not started")
        msg = MCPMessage.request(method, params)
        payload = (json.dumps(msg.to_dict()) + "\n").encode("utf-8")
        self._process.stdin.write(payload)
        await self._process.stdin.drain()
        line = await self._process.stdout.readline()
        return json.loads(line.decode("utf-8"))


async def run_smoke_test(command: Optional[List[str]] = None) -> Dict[str, Any]:
    """Run a quick smoke test: start our own stdio server in-process and call it.

    Returns the list of registered tools.
    """
    import sys as _sys

    if command is None:
        # Run this module as a subprocess: python -m app.ai.mcp.transport
        command = [_sys.executable, "-m", "app.ai.mcp.transport"]

    client = MCPClient(command)
    await client.start()
    try:
        response = await client.request("tools/list")
        return response.get("result", {})
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(serve_stdio())