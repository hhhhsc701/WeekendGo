from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from app.api.routes import resolve_required_servers
from app.mcp.errors import MCPToolError
from app.mcp.client import MCPClientManager
from app.mcp.models import MCPConfig, MCPServerConfig, RouteConfig
from app.models.trip import CompanionType, TripInput


def build_config() -> MCPConfig:
    return MCPConfig(
        servers={
            "amap-mcp": MCPServerConfig(
                enabled=True,
                mode="local",
                command="amap",
                tools=["geocode", "search_poi_around"],
                retry_backoff_seconds=0,
            ),
            "google-maps-mcp": MCPServerConfig(
                enabled=True,
                mode="local",
                command="google",
                tools=["geocode", "maps_search_nearby"],
                retry_backoff_seconds=0,
            ),
            "weather": MCPServerConfig(
                enabled=True,
                mode="local",
                command="weather",
                tools=["search_location", "get_forecast"],
                retry_backoff_seconds=0,
            ),
            "train-12306": MCPServerConfig(
                enabled=True,
                mode="local",
                command="train",
                tools=["query_trains"],
                retry_backoff_seconds=0,
            ),
        },
        routes={
            "domestic": RouteConfig(primary="amap-mcp", shared=["weather", "train-12306"]),
            "international": RouteConfig(primary="google-maps-mcp", shared=["weather"]),
        },
    )


def build_input(city: str, departure_city: str | None = None) -> TripInput:
    return TripInput(
        city=city,
        date=date(2026, 5, 16),
        days=2,
        interests=["美食"],
        companions=CompanionType.solo,
        departure_city=departure_city,
    )


def test_domestic_trip_without_departure_skips_local_shared_servers() -> None:
    required = resolve_required_servers(build_config(), build_input("杭州"))

    assert required == {"amap-mcp", "weather"}


def test_international_trip_uses_google_and_weather_servers() -> None:
    required = resolve_required_servers(build_config(), build_input("Tokyo"))

    assert required == {"google-maps-mcp", "weather"}


async def test_initialize_only_connects_selected_servers() -> None:
    manager = MCPClientManager(build_config())
    connected: list[str] = []

    async def fake_connect(server_name: str, _: MCPServerConfig) -> None:
        connected.append(server_name)

    manager._connect_local_server = fake_connect  # type: ignore[method-assign]

    await manager.initialize({"amap-mcp"})
    await manager.close()

    assert connected == ["amap-mcp"]


async def test_disconnect_suppresses_cancelled_cleanup_error() -> None:
    class CancelledCloseStack:
        async def aclose(self) -> None:
            raise asyncio.CancelledError("Cancelled via cancel scope")

    manager = MCPClientManager(build_config())
    manager._sessions["weather"] = object()
    manager._exit_stacks["weather"] = CancelledCloseStack()  # type: ignore[assignment]

    await manager.close()

    assert manager._sessions == {}
    assert manager._exit_stacks == {}


async def test_call_reports_initialization_failure_reason() -> None:
    manager = MCPClientManager(build_config())

    async def fail_connect(_: str, __: MCPServerConfig) -> None:
        raise RuntimeError("npx package download failed")

    manager._connect_local_server = fail_connect  # type: ignore[method-assign]

    await manager.initialize({"amap-mcp"})
    with pytest.raises(MCPToolError) as exc_info:
        await manager.call("amap-mcp", "geocode", {"address": "杭州"})
    await manager.close()

    message = str(exc_info.value)
    assert "MCP server amap-mcp not connected" in message
    assert "npx package download failed" in message
    assert "`amap`" in message


async def test_initialize_retries_transient_startup_failure() -> None:
    manager = MCPClientManager(build_config())
    attempts = 0

    async def flaky_connect(server_name: str, _: MCPServerConfig) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("stdio handshake failed")
        manager._sessions[server_name] = object()

    manager._connect_local_server = flaky_connect  # type: ignore[method-assign]

    await manager.initialize({"weather"})
    await manager.close()

    assert attempts == 2


async def test_call_retries_transient_tool_failure() -> None:
    class FlakySession:
        def __init__(self) -> None:
            self.calls = 0

        async def call_tool(self, _: str, arguments: dict[str, object]) -> SimpleNamespace:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("OpenMeteo API is currently unavailable")
            return SimpleNamespace(content=[SimpleNamespace(text='{"ok": true}')])

    manager = MCPClientManager(build_config())
    session = FlakySession()
    manager._sessions["weather"] = session

    result = await manager.call("weather", "get_forecast", {"latitude": 30, "longitude": 114})
    await manager.close()

    assert result == {"ok": True}
    assert session.calls == 2


async def test_call_treats_text_tool_errors_as_failures() -> None:
    class UnknownToolSession:
        async def call_tool(self, _: str, arguments: dict[str, object]) -> SimpleNamespace:
            return SimpleNamespace(content=[SimpleNamespace(text="Unknown tool: geocode")])

    manager = MCPClientManager(build_config())
    manager._sessions["amap-mcp"] = UnknownToolSession()

    with pytest.raises(MCPToolError) as exc_info:
        await manager.call("amap-mcp", "geocode", {"address": "杭州"})
    await manager.close()

    assert "Unknown tool: geocode" in str(exc_info.value)


async def test_initialize_records_runtime_tool_list() -> None:
    class ToolsSession:
        async def list_tools(self) -> SimpleNamespace:
            return SimpleNamespace(
                tools=[
                    SimpleNamespace(name="maps_geo"),
                    SimpleNamespace(name="maps_around_search"),
                ]
            )

    manager = MCPClientManager(build_config())
    manager._sessions["amap-mcp"] = ToolsSession()

    await manager._refresh_server_tools("amap-mcp", manager.config.servers["amap-mcp"], ToolsSession())
    await manager.close()

    assert manager.config.servers["amap-mcp"].tools == ["maps_geo", "maps_around_search"]


def test_parse_mcp_result_accepts_dict_text_content() -> None:
    manager = MCPClientManager(build_config())
    result = SimpleNamespace(
        content=[
            {
                "type": "text",
                "text": "# Weather Forecast\n\n**Temperature:** High 25°C / Low 18°C\n",
            }
        ]
    )

    parsed = manager._parse_mcp_result(result)

    assert parsed == {"text": "# Weather Forecast\n\n**Temperature:** High 25°C / Low 18°C\n"}
