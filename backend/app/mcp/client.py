from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from contextlib import AsyncExitStack, suppress
from time import perf_counter
from typing import Any

from app.mcp.errors import MCPError, MCPTimeoutError, MCPToolError
from app.mcp.models import MCPConfig, MCPServerConfig

logger = logging.getLogger(__name__)


class MCPClientManager:
    def __init__(self, config: MCPConfig, job_id: str | None = None) -> None:
        self.config = config
        self.job_id = job_id or "local"
        self._exit_stacks: dict[str, AsyncExitStack] = {}
        self._sessions: dict[str, Any] = {}
        self._init_errors: dict[str, str] = {}
        self._server_tools: dict[str, list[str]] = {}

    async def initialize(self, server_names: Iterable[str] | None = None) -> None:
        selected_servers = set(server_names) if server_names is not None else None

        for server_name, server_config in self.config.servers.items():
            if selected_servers is not None and server_name not in selected_servers:
                continue
            if not server_config.enabled:
                logger.info("trip_generation[%s] MCP server skipped server=%s disabled", self.job_id, server_name)
                continue
            await self._initialize_server_with_retries(server_name, server_config)

    async def close(self) -> None:
        logger.info("trip_generation[%s] MCP manager close started", self.job_id)
        for server_name in list(self._exit_stacks):
            await self._disconnect_server(server_name)
        self._sessions.clear()
        self._init_errors.clear()
        self._server_tools.clear()
        logger.info("trip_generation[%s] MCP manager close finished", self.job_id)

    def available_tools(self, server_name: str) -> list[str]:
        server = self.config.servers.get(server_name)
        configured_tools = server.tools if server else []
        return self._server_tools.get(server_name) or configured_tools

    async def call(self, server_name: str, tool: str, params: dict[str, Any]) -> dict[str, Any]:
        server = self.config.servers.get(server_name)
        if not server:
            raise MCPToolError(f"Server {server_name} not found")

        last_error: Exception | None = None
        attempts = max(1, server.retry_attempts)
        for attempt in range(1, attempts + 1):
            try:
                logger.info(
                    "trip_generation[%s] MCP tool call attempt %d/%d server=%s tool=%s params=%s",
                    self.job_id,
                    attempt,
                    attempts,
                    server_name,
                    tool,
                    self._json_preview(params),
                )
                if self._sessions.get(server_name) is None:
                    await self._initialize_server_with_retries(server_name, server)
                return await self._call_local(server_name, server, tool, params)
            except MCPTimeoutError as exc:
                last_error = exc
                logger.warning(
                    "MCP tool %s:%s timed out on attempt %d/%d",
                    server_name,
                    tool,
                    attempt,
                    attempts,
                )
                await self._disconnect_server(server_name)
            except MCPToolError as exc:
                last_error = exc
                if not self._is_retryable_tool_error(exc):
                    raise
                logger.warning(
                    "MCP tool %s:%s failed on attempt %d/%d: %s",
                    server_name,
                    tool,
                    attempt,
                    attempts,
                    exc,
                )

            if attempt < attempts:
                await asyncio.sleep(server.retry_backoff_seconds * attempt)

        if last_error:
            raise last_error
        raise MCPToolError(f"MCP tool call failed: {server_name}:{tool}")

    async def _initialize_server_with_retries(
        self,
        server_name: str,
        server_config: MCPServerConfig,
    ) -> None:
        last_error: Exception | None = None
        attempts = max(1, server_config.retry_attempts)

        for attempt in range(1, attempts + 1):
            try:
                started_at = perf_counter()
                logger.info(
                    "trip_generation[%s] MCP server init attempt %d/%d server=%s command=%s",
                    self.job_id,
                    attempt,
                    attempts,
                    server_name,
                    self._command_preview(server_config),
                )
                await self._disconnect_server(server_name)
                await asyncio.wait_for(
                    self._connect_local_server(server_name, server_config),
                    timeout=self._initialize_timeout(server_config),
                )
                self._init_errors.pop(server_name, None)
                logger.info(
                    "trip_generation[%s] MCP server init succeeded server=%s elapsed=%.2fs",
                    self.job_id,
                    server_name,
                    perf_counter() - started_at,
                )
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "MCP server %s failed to initialize on attempt %d/%d: %s",
                    server_name,
                    attempt,
                    attempts,
                    exc,
                )
                await self._disconnect_server(server_name)
                if attempt < attempts:
                    await asyncio.sleep(server_config.retry_backoff_seconds * attempt)

        if last_error:
            logger.error("MCP server %s failed to initialize after %d attempts", server_name, attempts)
            self._sessions[server_name] = None
            self._init_errors[server_name] = self._format_init_error(server_config, last_error)

    def _initialize_timeout(self, server: MCPServerConfig) -> float:
        if server.initialize_timeout_seconds is not None:
            return server.initialize_timeout_seconds
        return min(server.timeout_seconds, 12.0)

    async def _disconnect_server(self, server_name: str) -> None:
        self._sessions.pop(server_name, None)
        stack = self._exit_stacks.pop(server_name, None)
        if stack is not None:
            logger.info("trip_generation[%s] MCP server disconnecting server=%s", self.job_id, server_name)
            with suppress(Exception, asyncio.CancelledError):
                await stack.aclose()
            logger.info("trip_generation[%s] MCP server disconnected server=%s", self.job_id, server_name)

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
            started_at = perf_counter()
            result = await asyncio.wait_for(
                session.call_tool(tool, arguments=params),
                timeout=server.timeout_seconds,
            )
            parsed = self._parse_mcp_result(result)
            self._raise_for_mcp_result_error(server_name, tool, parsed)
            logger.info(
                "trip_generation[%s] MCP tool call succeeded server=%s tool=%s elapsed=%.2fs result=%s",
                self.job_id,
                server_name,
                tool,
                perf_counter() - started_at,
                self._json_preview(parsed),
            )
            return parsed
        except asyncio.TimeoutError:
            logger.warning(
                "trip_generation[%s] MCP tool call timed out server=%s tool=%s timeout=%.0fs",
                self.job_id,
                server_name,
                tool,
                server.timeout_seconds,
            )
            raise MCPTimeoutError(f"MCP tool {tool} timed out")
        except Exception as exc:
            logger.warning(
                "trip_generation[%s] MCP tool call failed server=%s tool=%s error=%s",
                self.job_id,
                server_name,
                tool,
                exc,
            )
            raise MCPToolError(f"MCP tool call failed: {exc}")

    async def _connect_local_server(self, server_name: str, server: MCPServerConfig) -> None:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            raise MCPError("Python package 'mcp' is not installed")

        if not server.command:
            raise MCPError(f"Server {server_name} missing command")

        stack = AsyncExitStack()
        parameters = StdioServerParameters(
            command=server.command,
            args=server.args,
            env=server.env,
        )
        try:
            read_stream, write_stream = await stack.enter_async_context(stdio_client(parameters))
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
            self._exit_stacks[server_name] = stack
            self._sessions[server_name] = session
            await self._refresh_server_tools(server_name, server, session)
            logger.info("MCP server %s initialized", server_name)
        except BaseException:
            with suppress(Exception, asyncio.CancelledError):
                await stack.aclose()
            raise

    async def _refresh_server_tools(self, server_name: str, server: MCPServerConfig, session: Any) -> None:
        try:
            result = await session.list_tools()
        except Exception as exc:
            logger.warning(
                "trip_generation[%s] MCP list_tools failed server=%s error=%s",
                self.job_id,
                server_name,
                exc,
            )
            self._server_tools[server_name] = list(server.tools)
            return

        tools = getattr(result, "tools", None)
        names = [
            tool.name
            for tool in tools or []
            if isinstance(getattr(tool, "name", None), str)
        ]
        if names:
            self._server_tools[server_name] = names
            server.tools = names
        else:
            self._server_tools[server_name] = list(server.tools)
        logger.info(
            "trip_generation[%s] MCP server tools server=%s tools=%s",
            self.job_id,
            server_name,
            ", ".join(self._server_tools[server_name]) or "-",
        )

    def _format_init_error(self, server: MCPServerConfig, exc: Exception) -> str:
        command = " ".join([server.command or "", *server.args]).strip()
        if not command:
            command = "<missing command>"
        error = str(exc).strip() or exc.__class__.__name__
        return (
            f"failed to start command `{command}` within "
            f"{self._initialize_timeout(server):.0f}s; error={error}. "
            "Check that Node.js/npm can run npx, network access is available for first-time "
            "package download, and required environment variables are configured."
        )

    def _is_retryable_tool_error(self, exc: MCPToolError) -> bool:
        message = str(exc).lower()
        if message.startswith("server ") and "not found" in message:
            return False
        if message.startswith("mcp server ") and "not connected" in message:
            return False
        non_retryable_fragments = (
            "unknown tool",
            "tool not found",
            "not found",
            "mcp error -32602",
            "invalid arguments",
            "validation",
        )
        return not any(fragment in message for fragment in non_retryable_fragments)

    def _raise_for_mcp_result_error(self, server_name: str, tool: str, parsed: Any) -> None:
        if not isinstance(parsed, dict):
            return

        error_text = parsed.get("error") or parsed.get("detail")
        text = parsed.get("text")
        if error_text:
            raise MCPToolError(f"{server_name}:{tool} returned error: {error_text}")
        if not isinstance(text, str):
            return

        normalized = text.strip().lower()
        error_fragments = (
            "unknown tool",
            "tool not found",
            "mcp error",
            "error:",
            "failed:",
            "not found.",
        )
        if any(fragment in normalized for fragment in error_fragments):
            raise MCPToolError(f"{server_name}:{tool} returned error text: {text.strip()}")

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

    def _command_preview(self, server: MCPServerConfig) -> str:
        return " ".join([server.command or "", *server.args]).strip() or "<missing command>"

    def _json_preview(self, value: Any, max_length: int = 500) -> str:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            text = str(value)
        compact = " ".join(text.split())
        if len(compact) <= max_length:
            return compact
        return f"{compact[:max_length]}..."
