from __future__ import annotations

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
            ),
            "google-maps-mcp": MCPServerConfig(
                enabled=True,
                mode="local",
                command="google",
                tools=["geocode", "maps_search_nearby"],
            ),
            "weather": MCPServerConfig(
                enabled=True,
                mode="local",
                command="weather",
                tools=["search_location", "get_forecast"],
            ),
            "train-12306": MCPServerConfig(
                enabled=True,
                mode="local",
                command="train",
                tools=["query_trains"],
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
