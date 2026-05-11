from __future__ import annotations

from contextlib import AsyncExitStack
import asyncio
import logging
from typing import Any

from app.mcp.config_loader import MCPConfig, MCPServerConfig
from app.mcp.errors import MCPToolError, MCPToolTimeoutError, wrap_tool_error
from app.mcp.region import Region, RegionRouter

logger = logging.getLogger(__name__)

TOOL_ALIASES = {
    "geocode": "maps_geo",
    "search_poi": "maps_text_search",
    "search_poi_around": "maps_around_search",
    "driving_route_planning": "maps_direction_driving",
    "walking_route_planning": "maps_direction_walking",
    "public_transit_route_planning": "maps_direction_transit_integrated",
    "get_weather": "maps_weather",
    "search_poi_detail": "maps_search_detail",
}


class MCPClientManager:
    def __init__(self, config: MCPConfig, router: RegionRouter | None = None) -> None:
        self.config = config
        self.router = router or RegionRouter()
        self._exit_stack = AsyncExitStack()
        self._sessions: dict[str, Any] = {}
        self._tool_registry: dict[str, set[str]] = {}

    @property
    def available_servers(self) -> list[str]:
        return sorted(self._sessions)

    @property
    def tool_registry(self) -> dict[str, set[str]]:
        return self._tool_registry

    async def initialize(self) -> None:
        for server_name, server_config in self.config.servers.items():
            if not server_config.enabled:
                continue
            try:
                await self._connect_server(server_name, server_config)
            except Exception as exc:  # noqa: BLE001 - one failed server must not stop all routes
                logger.exception("MCP server %s failed to initialize", server_name)
                self._tool_registry[server_name] = set()
                wrapped = wrap_tool_error(exc, server=server_name)
                logger.warning("MCP server unavailable: %s", wrapped.to_dict())

    async def close(self) -> None:
        await self._exit_stack.aclose()
        self._sessions.clear()
        self._tool_registry.clear()

    async def _connect_server(self, server_name: str, server_config: MCPServerConfig) -> None:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:
            raise MCPToolError("Python package 'mcp' is not installed") from exc

        parameters = StdioServerParameters(
            command=server_config.command,
            args=server_config.args,
            env=server_config.env,
        )
        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(parameters)
        )
        session = await self._exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        self._sessions[server_name] = session

        listed_tools = await session.list_tools()
        discovered = {tool.name for tool in listed_tools.tools}
        configured = set(server_config.tools)
        self._tool_registry[server_name] = discovered or configured
        logger.info("MCP server %s initialized with tools: %s", server_name, sorted(discovered))

    async def call(self, region: Region, tool_name: str, params: dict[str, Any]) -> Any:
        server_name = self._select_server(region, tool_name)
        session = self._sessions.get(server_name)
        if session is None:
            raise MCPToolError(f"MCP server {server_name} is not connected")
        actual_tool_name = self._resolve_tool_name(server_name, tool_name)

        try:
            return await asyncio.wait_for(
                session.call_tool(actual_tool_name, params),
                timeout=self.config.timeout_seconds,
            )
        except TimeoutError as exc:
            wrapped = MCPToolTimeoutError(
                f"MCP tool {tool_name} timed out after {self.config.timeout_seconds:.0f}s"
            )
            logger.warning("MCP timeout: %s", wrap_tool_error(wrapped, server=server_name, tool=tool_name).to_dict())
            raise wrapped from exc
        except Exception as exc:
            wrapped = wrap_tool_error(exc, server=server_name, tool=tool_name)
            logger.exception("MCP tool call failed: %s", wrapped.to_dict())
            raise MCPToolError(wrapped.message) from exc

    def _select_server(self, region: Region, tool_name: str) -> str:
        candidates = self.router.server_candidates(
            region,
            tool_name,
            self.config.routes,
            self.config.servers,
        )
        connected_candidates = [name for name in candidates if name in self._sessions]
        if connected_candidates:
            return connected_candidates[0]
        if candidates:
            raise MCPToolError(f"No connected MCP server available for tool {tool_name}")
        raise MCPToolError(f"MCP tool {tool_name} is not configured for region {region}")

    def _resolve_tool_name(self, server_name: str, tool_name: str) -> str:
        discovered = self._tool_registry.get(server_name, set())
        if tool_name in discovered:
            return tool_name
        alias = TOOL_ALIASES.get(tool_name)
        if alias and alias in discovered:
            return alias
        return tool_name
