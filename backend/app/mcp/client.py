from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from contextlib import AsyncExitStack
from typing import Any

from app.mcp.errors import MCPError, MCPTimeoutError, MCPToolError
from app.mcp.models import MCPConfig, MCPServerConfig

logger = logging.getLogger(__name__)


class MCPClientManager:
    def __init__(self, config: MCPConfig) -> None:
        self.config = config
        self._exit_stack = AsyncExitStack()
        self._sessions: dict[str, Any] = {}
        self._init_errors: dict[str, str] = {}

    async def initialize(self, server_names: Iterable[str] | None = None) -> None:
        selected_servers = set(server_names) if server_names is not None else None

        for server_name, server_config in self.config.servers.items():
            if selected_servers is not None and server_name not in selected_servers:
                continue
            if not server_config.enabled:
                continue
            try:
                await asyncio.wait_for(
                    self._connect_local_server(server_name, server_config),
                    timeout=min(server_config.timeout_seconds, 8.0),
                )
            except Exception as exc:
                logger.exception("MCP server %s failed to initialize", server_name)
                self._sessions[server_name] = None
                self._init_errors[server_name] = self._format_init_error(server_config, exc)

    async def close(self) -> None:
        await self._exit_stack.aclose()
        self._sessions.clear()
        self._init_errors.clear()

    async def call(self, server_name: str, tool: str, params: dict[str, Any]) -> dict[str, Any]:
        server = self.config.servers.get(server_name)
        if not server:
            raise MCPToolError(f"Server {server_name} not found")

        return await self._call_local(server_name, server, tool, params)

    async def _call_local(
        self, server_name: str, server: MCPServerConfig, tool: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        session = self._sessions.get(server_name)
        if session is None:
            detail = self._init_errors.get(server_name)
            if detail:
                raise MCPToolError(f"MCP server {server_name} not connected: {detail}")
            raise MCPToolError(
                f"MCP server {server_name} not connected. "
                "It was not initialized for this request or startup did not complete."
            )

        try:
            result = await asyncio.wait_for(
                session.call_tool(tool, arguments=params),
                timeout=server.timeout_seconds,
            )
            return self._parse_mcp_result(result)
        except asyncio.TimeoutError:
            raise MCPTimeoutError(f"MCP tool {tool} timed out")
        except Exception as exc:
            raise MCPToolError(f"MCP tool call failed: {exc}")

    async def _connect_local_server(self, server_name: str, server: MCPServerConfig) -> None:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            raise MCPError("Python package 'mcp' is not installed")

        if not server.command:
            raise MCPError(f"Server {server_name} missing command")

        parameters = StdioServerParameters(
            command=server.command,
            args=server.args,
            env=server.env,
        )
        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(parameters)
        )
        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()
        self._sessions[server_name] = session
        logger.info("MCP server %s initialized", server_name)

    def _format_init_error(self, server: MCPServerConfig, exc: Exception) -> str:
        command = " ".join([server.command or "", *server.args]).strip()
        if not command:
            command = "<missing command>"
        error = str(exc).strip() or exc.__class__.__name__
        return (
            f"failed to start command `{command}` within "
            f"{min(server.timeout_seconds, 8.0):.0f}s; error={error}. "
            "Check that Node.js/npm can run npx, network access is available for first-time "
            "package download, and required environment variables are configured."
        )

    def _parse_mcp_result(self, result: Any) -> dict[str, Any]:
        if hasattr(result, "content"):
            content = result.content
            if isinstance(content, list):
                for item in content:
                    if hasattr(item, "text"):
                        try:
                            return json.loads(item.text)
                        except json.JSONDecodeError:
                            return {"text": item.text}
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        try:
                            return json.loads(item["text"])
                        except json.JSONDecodeError:
                            return {"text": item["text"]}
            if isinstance(content, str):
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {"text": content}
        if isinstance(result, dict):
            content = result.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        try:
                            return json.loads(item["text"])
                        except json.JSONDecodeError:
                            return {"text": item["text"]}
        return {"result": str(result)}
