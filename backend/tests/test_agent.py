"""Unit tests for TripAgent with mock LLM and MCP."""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.agent.trip_agent import TripAgent
from app.models.trip import CompanionType, Coordinates, Place, TripInput, TripItem, TripOutput


class FakeChatCompletion:
    """Mock chat.completions.create response."""

    def __init__(self, message: dict[str, Any]) -> None:
        self.choices = [MagicMock(message=MagicMock(**message))]


class FakeLLM:
    """Mock AsyncOpenAI client that simulates tool_calls responses.

    Accepts a list of pre-configured responses and returns them sequentially
    based on call count. Each response can contain tool_calls to simulate
    agent iterations.
    """

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.call_count = 0
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self.chat.completions.create = self._create

    async def _create(self, **kwargs: Any) -> FakeChatCompletion:
        """Return next response based on call count."""
        if self.call_count >= len(self.responses):
            return FakeChatCompletion({"content": "No more responses", "tool_calls": None})

        response = self.responses[self.call_count]
        self.call_count += 1

        message: dict[str, Any] = {"role": "assistant"}

        if "content" in response:
            message["content"] = response["content"]

        if "tool_calls" in response:
            tool_calls = []
            for tc in response["tool_calls"]:
                tool_call = MagicMock()
                tool_call.id = tc.get("id", f"call_{self.call_count}")
                tool_call.function = MagicMock()
                tool_call.function.name = tc["name"]
                tool_call.function.arguments = json.dumps(tc["arguments"], ensure_ascii=False)
                tool_calls.append(tool_call)
            message["tool_calls"] = tool_calls
        else:
            message["tool_calls"] = None

        return FakeChatCompletion(message)


class FakeMCP:
    """Mock MCPClientManager that simulates tool results.

    Accepts pre-configured tool results and returns them based on
    (server_name, tool_name) lookup. Can simulate errors when configured.
    """

    def __init__(
        self,
        tool_results: dict[str, dict[str, Any]] | None = None,
        errors: dict[str, str] | None = None,
    ) -> None:
        from app.mcp.models import MCPConfig, MCPServerConfig, RouteConfig

        self.tool_results = tool_results or {}
        self.errors = errors or {}
        self.call_count = 0
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

        self.config = MCPConfig(
            servers={
                "amap-mcp": MCPServerConfig(
                    enabled=True,
                    mode="local",
                    tools=["geocode", "search_poi_around"],
                ),
                "google-maps-mcp": MCPServerConfig(
                    enabled=True,
                    mode="local",
                    tools=["geocode", "maps_search_nearby"],
                ),
                "weather": MCPServerConfig(
                    enabled=True,
                    mode="local",
                    tools=["search_location", "get_forecast"],
                ),
                "train-12306": MCPServerConfig(
                    enabled=True,
                    mode="local",
                    tools=["query_trains"],
                ),
            },
            routes={
                "domestic": RouteConfig(primary="amap-mcp", shared=["weather", "train-12306"]),
                "international": RouteConfig(primary="google-maps-mcp", shared=["weather"]),
            },
        )

    async def initialize(self) -> None:
        """Async no-op for initialization."""
        pass

    async def close(self) -> None:
        """Async no-op for cleanup."""
        pass

    async def call(self, server_name: str, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Return pre-configured result or simulate error."""
        key = f"{server_name}:{tool_name}"
        self.call_count += 1
        self.calls.append((server_name, tool_name, params))

        if key in self.errors:
            raise RuntimeError(self.errors[key])

        if key in self.tool_results:
            return self.tool_results[key]

        return {"error": f"No mock result for {key}"}


SAMPLE_TRIP_OUTPUT: dict[str, Any] = {
    "title": "北京周末一日游",
    "input": {
        "city": "北京",
        "date": "2025-05-15",
        "days": 1,
        "budget": 500.0,
        "interests": ["历史", "美食"],
        "companions": "solo",
    },
    "items": [
        {
            "start_time": "09:00",
            "end_time": "12:00",
            "activity": "故宫游览",
            "place": {
                "name": "故宫博物院",
                "address": "北京市东城区景山前街4号",
                "coordinates": {"lat": 39.9163, "lng": 116.3972},
                "rating": 4.8,
                "category": "景点",
            },
            "estimated_cost": 60.0,
        },
        {
            "start_time": "12:00",
            "end_time": "14:00",
            "activity": "午餐",
            "place": {"name": "老北京炸酱面"},
            "estimated_cost": 50.0,
        },
    ],
    "weather_summary": {"summary": "晴，温度18-25°C", "temperature_c": 22.0},
    "total_budget": 110.0,
    "notes": ["建议提前预约故宫门票"],
}


GEOCODE_RESULT: dict[str, Any] = {
    "location": "116.3972,39.9163",
    "address": "北京市",
}

SEARCH_POI_RESULT: dict[str, Any] = {
    "pois": [
        {
            "name": "故宫博物院",
            "address": "北京市东城区景山前街4号",
            "location": "116.3972,39.9163",
            "rating": 4.8,
            "type": "景点",
        },
        {
            "name": "天安门广场",
            "address": "北京市东城区东长安街",
            "location": "116.3975,39.9054",
            "rating": 4.7,
            "type": "景点",
        },
    ],
}

WEATHER_RESULT: dict[str, Any] = {
    "city": "北京",
    "weather": "晴",
    "temperature": "18-25",
}

WEATHER_TEXT_RESULT: dict[str, Any] = {
    "content": [
        {
            "type": "text",
            "text": (
                "# Weather Forecast (Daily)\n\n"
                "## Tuesday, May 12\n"
                "**Temperature:** High 25°C / Low 18°C\n"
                "**Conditions:** Clear sky\n"
                "**Precipitation Chance:** 10%\n"
            ),
        }
    ]
}

LOCATION_RESULT: dict[str, Any] = {
    "text": "*Latitude: 39.9042, Longitude: 116.4074*",
}

TRAIN_RESULT: dict[str, Any] = {
    "trains": [
        {
            "train_number": "G1234",
            "from_station": "北京南",
            "to_station": "上海虹桥",
            "depart_time": "08:00",
            "arrive_time": "12:30",
            "duration": "4小时30分",
            "price": "553",
        }
    ]
}


@pytest.fixture
def trip_input() -> TripInput:
    """Sample TripInput for testing."""
    return TripInput(
        city="北京",
        date=date(2025, 5, 15),
        days=1,
        budget=500.0,
        interests=["历史", "美食"],
        companions=CompanionType.solo,
        departure_city=None,
    )


@pytest.fixture
def fake_mcp() -> FakeMCP:
    """FakeMCP with pre-configured tool results."""
    return FakeMCP(
        tool_results={
            "amap-mcp:geocode": GEOCODE_RESULT,
            "amap-mcp:search_poi_around": SEARCH_POI_RESULT,
            "weather:search_location": LOCATION_RESULT,
            "weather:get_forecast": WEATHER_RESULT,
            "train-12306:query_trains": TRAIN_RESULT,
        }
    )


class TestTripAgentCompleteFlow:
    """Test TripAgent complete flow: geocode→search_poi→finish."""

    @pytest.mark.asyncio
    async def test_agent_complete_flow(self, trip_input: TripInput, fake_mcp: FakeMCP) -> None:
        """Simulate geocode→search_poi→finish sequence."""
        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "geocode", "arguments": {"address": "北京"}}]},
                {"tool_calls": [{"name": "search_poi", "arguments": {"query": "景点", "location": "116.3972,39.9163"}}]},
                {"tool_calls": [{"name": "finish", "arguments": SAMPLE_TRIP_OUTPUT}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert result.title == "北京周末一日游"
        assert len(result.items) == 2
        assert result.items[0].activity == "故宫游览"
        assert result.items[0].place.name == "故宫博物院"
        assert fake_llm.call_count == 3
        assert fake_mcp.call_count == 2

    @pytest.mark.asyncio
    async def test_agent_with_weather_and_poi(self, trip_input: TripInput, fake_mcp: FakeMCP) -> None:
        """Test agent collecting weather and POI before finish."""
        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "geocode", "arguments": {"address": "北京"}}]},
                {"tool_calls": [{"name": "get_weather", "arguments": {"city": "北京"}}]},
                {"tool_calls": [{"name": "search_poi", "arguments": {"query": "景点"}}]},
                {"tool_calls": [{"name": "finish", "arguments": SAMPLE_TRIP_OUTPUT}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert fake_llm.call_count == 4
        assert fake_mcp.call_count == 3

    @pytest.mark.asyncio
    async def test_weather_tool_result_fills_missing_finish_weather(
        self, trip_input: TripInput, fake_mcp: FakeMCP
    ) -> None:
        """Weather tool result fills weather_summary when finish omits useful weather."""
        output_without_weather = dict(SAMPLE_TRIP_OUTPUT)
        output_without_weather["weather_summary"] = {"summary": "天气数据不可用"}
        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "get_weather", "arguments": {"city": "北京"}}]},
                {"tool_calls": [{"name": "finish", "arguments": output_without_weather}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert result.weather_summary.summary == "北京，晴，18-25°C"

    @pytest.mark.asyncio
    async def test_weather_reuses_geocode_coordinates(
        self, trip_input: TripInput, fake_mcp: FakeMCP
    ) -> None:
        """Weather forecast uses cached geocode coordinates instead of search_location."""
        output_without_weather = dict(SAMPLE_TRIP_OUTPUT)
        output_without_weather["weather_summary"] = {"summary": "天气数据不可用"}
        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "geocode", "arguments": {"address": "北京"}}]},
                {"tool_calls": [{"name": "get_weather", "arguments": {"city": "北京"}}]},
                {"tool_calls": [{"name": "finish", "arguments": output_without_weather}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert ("weather", "search_location") not in [
            (server_name, tool_name) for server_name, tool_name, _ in fake_mcp.calls
        ]
        assert (
            "weather",
            "get_forecast",
            {"latitude": 39.9163, "longitude": 116.3972, "days": 3},
        ) in fake_mcp.calls

    @pytest.mark.asyncio
    async def test_chinese_weather_does_not_fallback_to_weather_location_search(
        self, trip_input: TripInput
    ) -> None:
        """Chinese city weather resolution never calls weather.search_location."""
        fake_mcp = FakeMCP(
            tool_results={
                "amap-mcp:geocode": {"error": "No geocode result"},
                "weather:search_location": LOCATION_RESULT,
                "weather:get_forecast": WEATHER_RESULT,
            }
        )
        output_without_weather = dict(SAMPLE_TRIP_OUTPUT)
        output_without_weather["weather_summary"] = {"summary": "天气数据不可用"}
        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "get_weather", "arguments": {"city": "北京"}}]},
                {"tool_calls": [{"name": "finish", "arguments": output_without_weather}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert ("weather", "search_location") not in [
            (server_name, tool_name) for server_name, tool_name, _ in fake_mcp.calls
        ]
        assert ("weather", "get_forecast") not in [
            (server_name, tool_name) for server_name, tool_name, _ in fake_mcp.calls
        ]

    @pytest.mark.asyncio
    async def test_weather_forecast_failure_continues_to_finish(
        self, trip_input: TripInput, fake_mcp: FakeMCP
    ) -> None:
        """Forecast failures are returned as tool errors instead of aborting generation."""
        fake_mcp.errors["weather:get_forecast"] = "OpenMeteo API is currently unavailable"
        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "geocode", "arguments": {"address": "北京"}}]},
                {"tool_calls": [{"name": "get_weather", "arguments": {"city": "北京"}}]},
                {"tool_calls": [{"name": "finish", "arguments": SAMPLE_TRIP_OUTPUT}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert fake_llm.call_count == 3

    @pytest.mark.asyncio
    async def test_weather_mcp_text_content_fills_missing_finish_weather(
        self, trip_input: TripInput
    ) -> None:
        """Weather MCP text content is converted into a displayable weather summary."""
        fake_mcp = FakeMCP(
            tool_results={
                "amap-mcp:geocode": GEOCODE_RESULT,
                "weather:get_forecast": WEATHER_TEXT_RESULT,
            }
        )
        output_without_weather = dict(SAMPLE_TRIP_OUTPUT)
        output_without_weather["weather_summary"] = {"summary": "天气数据不可用"}
        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "geocode", "arguments": {"address": "北京"}}]},
                {"tool_calls": [{"name": "get_weather", "arguments": {"city": "北京"}}]},
                {"tool_calls": [{"name": "finish", "arguments": output_without_weather}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert result.weather_summary.summary == "Clear sky，High 25°C / Low 18°C，降水概率 10%"

    @pytest.mark.asyncio
    async def test_finish_enriches_missing_coordinates_and_item_costs(
        self, trip_input: TripInput, fake_mcp: FakeMCP
    ) -> None:
        """POI results backfill map coordinates and missing per-step budgets."""
        output_without_coordinates_or_costs = {
            "title": "北京周末游",
            "items": [
                {
                    "start_time": "09:00",
                    "end_time": "11:00",
                    "activity": "故宫游览",
                    "place": {"name": "故宫博物院"},
                },
                {
                    "start_time": "12:00",
                    "end_time": "13:00",
                    "activity": "午餐",
                    "place": {"name": "本地餐厅"},
                },
            ],
        }
        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "search_poi", "arguments": {"query": "景点"}}]},
                {"tool_calls": [{"name": "finish", "arguments": output_without_coordinates_or_costs}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert result.items[0].place.coordinates is not None
        assert result.items[0].place.coordinates.lng == 116.3972
        assert result.items[0].place.coordinates.lat == 39.9163
        assert result.items[0].estimated_cost == 60.0
        assert result.items[1].estimated_cost == 80.0
        assert result.total_budget == 140.0

    @pytest.mark.asyncio
    async def test_train_result_enriches_transport_detail(
        self, trip_input: TripInput, fake_mcp: FakeMCP
    ) -> None:
        """Selected train numbers show concrete time and fare in itinerary items."""
        output_with_train_reference = {
            "title": "北京到上海周末游",
            "items": [
                {
                    "start_time": "08:00",
                    "end_time": "12:30",
                    "activity": "乘坐高铁前往上海",
                    "place": {"name": "上海虹桥站"},
                    "transport": "G1234 高铁",
                }
            ],
        }
        fake_llm = FakeLLM(
            responses=[
                {
                    "tool_calls": [
                        {
                            "name": "query_trains",
                            "arguments": {"from": "北京", "to": "上海", "date": "2025-05-15"},
                        }
                    ]
                },
                {"tool_calls": [{"name": "finish", "arguments": output_with_train_reference}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        detail = result.items[0].transport_detail
        assert detail is not None
        assert detail.mode == "train"
        assert detail.code == "G1234"
        assert detail.departure == "北京南"
        assert detail.arrival == "上海虹桥"
        assert detail.departure_time == "08:00"
        assert detail.arrival_time == "12:30"
        assert detail.cost == 553.0
        assert result.items[0].estimated_cost == 553.0

    @pytest.mark.asyncio
    async def test_departure_city_coordinates_are_preserved_for_map(
        self, trip_input: TripInput, fake_mcp: FakeMCP
    ) -> None:
        """Departure city geocode is included in input and transport detail map points."""
        trip_input = trip_input.model_copy(update={"departure_city": "北京"})
        output_with_train_reference = {
            "title": "北京到上海周末游",
            "items": [
                {
                    "start_time": "08:00",
                    "end_time": "12:30",
                    "activity": "乘坐高铁前往上海",
                    "place": {"name": "上海虹桥站"},
                    "transport": "G1234 高铁",
                }
            ],
        }
        fake_llm = FakeLLM(
            responses=[
                {
                    "tool_calls": [
                        {
                            "name": "query_trains",
                            "arguments": {"from": "北京", "to": "上海", "date": "2025-05-15"},
                        }
                    ]
                },
                {"tool_calls": [{"name": "finish", "arguments": output_with_train_reference}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert result.input.departure_coordinates is not None
        assert result.input.departure_coordinates.lng == 116.3972
        assert result.input.departure_coordinates.lat == 39.9163
        assert result.items[0].transport_detail is not None
        assert result.items[0].transport_detail.departure_coordinates is not None
        assert result.items[0].transport_detail.departure_coordinates.lng == 116.3972
        assert result.items[0].transport_detail.departure_coordinates.lat == 39.9163

    @pytest.mark.asyncio
    async def test_departure_city_coordinates_use_fallback_when_geocode_fails(
        self, trip_input: TripInput, fake_mcp: FakeMCP
    ) -> None:
        """Known departure cities still get a map point when MCP geocode fails."""
        trip_input = trip_input.model_copy(update={"departure_city": "上海"})
        fake_mcp.errors["amap-mcp:geocode"] = "geocode unavailable"
        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "finish", "arguments": SAMPLE_TRIP_OUTPUT}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert result.input.departure_coordinates is not None
        assert result.input.departure_coordinates.lng == 121.4737
        assert result.input.departure_coordinates.lat == 31.2304


class TestTripAgentFallback:
    """Test TripAgent fallback scenarios."""

    @pytest.mark.asyncio
    async def test_agent_fallback_max_iterations(
        self, trip_input: TripInput, fake_mcp: FakeMCP
    ) -> None:
        """Agent returns degraded output after max_iterations without finish call."""
        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "geocode", "arguments": {"address": "北京"}}]},
                {"tool_calls": [{"name": "search_poi", "arguments": {"query": "景点"}}]},
                {"tool_calls": [{"name": "get_weather", "arguments": {"city": "北京"}}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=2)

        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert result.title == "北京1日周末游（数据受限）"
        assert "Agent exceeded 2 iterations" in result.notes[-1]

    @pytest.mark.asyncio
    async def test_agent_fallback_no_finish(self, trip_input: TripInput, fake_mcp: FakeMCP) -> None:
        """Agent loops without ever calling finish."""
        loop_response = {"tool_calls": [{"name": "geocode", "arguments": {"address": "北京"}}]}
        fake_llm = FakeLLM(responses=[loop_response] * 10)

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=5)

        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert fake_llm.call_count == 5


class TestTripAgentToolFailure:
    """Test TripAgent handling of MCP tool failures."""

    @pytest.mark.asyncio
    async def test_tool_failure_degradation(self, trip_input: TripInput) -> None:
        """MCP tool returns error, agent handles gracefully and continues."""
        fake_mcp = FakeMCP(
            tool_results={"amap-mcp:search_poi_around": SEARCH_POI_RESULT},
            errors={"amap-mcp:geocode": "API key invalid"},
        )

        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "geocode", "arguments": {"address": "北京"}}]},
                {"tool_calls": [{"name": "search_poi", "arguments": {"query": "景点"}}]},
                {"tool_calls": [{"name": "finish", "arguments": SAMPLE_TRIP_OUTPUT}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert fake_llm.call_count == 3
        assert any("MCP工具调用失败：geocode: API key invalid" in note for note in result.notes)

    @pytest.mark.asyncio
    async def test_all_tools_fail(self, trip_input: TripInput) -> None:
        """All MCP tools fail, agent still finishes with degraded data."""
        fake_mcp = FakeMCP(
            errors={
                "amap-mcp:geocode": "Service unavailable",
                "amap-mcp:search_poi_around": "Service unavailable",
                "weather:get_forecast": "Service unavailable",
            },
        )

        minimal_output = {
            "title": "北京周末游（数据受限）",
            "input": {
                "city": "北京",
                "date": "2025-05-15",
                "days": 1,
                "interests": ["历史"],
                "companions": "solo",
            },
            "items": [
                {
                    "start_time": "09:00",
                    "end_time": "18:00",
                    "activity": "自由探索",
                    "place": {"name": "北京"},
                }
            ],
            "notes": ["由于API服务不可用，行程基于有限数据生成"],
        }

        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "geocode", "arguments": {"address": "北京"}}]},
                {"tool_calls": [{"name": "search_poi", "arguments": {"query": "景点"}}]},
                {"tool_calls": [{"name": "finish", "arguments": minimal_output}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert result.title == "北京周末游（数据受限）"


class TestTripAgentEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_invalid_json_arguments(self, trip_input: TripInput, fake_mcp: FakeMCP) -> None:
        """Agent handles invalid JSON in tool arguments."""
        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "geocode", "arguments": {"address": "北京"}}]},
                {"tool_calls": [{"name": "finish", "arguments": SAMPLE_TRIP_OUTPUT}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)

    @pytest.mark.asyncio
    async def test_unknown_tool(self, trip_input: TripInput, fake_mcp: FakeMCP) -> None:
        """Agent handles unknown tool name gracefully."""
        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "unknown_tool", "arguments": {"foo": "bar"}}]},
                {"tool_calls": [{"name": "geocode", "arguments": {"address": "北京"}}]},
                {"tool_calls": [{"name": "finish", "arguments": SAMPLE_TRIP_OUTPUT}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert fake_llm.call_count == 3

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_per_iteration(self, trip_input: TripInput, fake_mcp: FakeMCP) -> None:
        """Agent handles multiple tool_calls in single response."""
        fake_llm = FakeLLM(
            responses=[
                {
                    "tool_calls": [
                        {"name": "geocode", "arguments": {"address": "北京"}},
                        {"name": "get_weather", "arguments": {"city": "北京"}},
                    ]
                },
                {"tool_calls": [{"name": "finish", "arguments": SAMPLE_TRIP_OUTPUT}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert fake_mcp.call_count == 2

    @pytest.mark.asyncio
    async def test_finish_without_input_uses_original_trip_input(
        self, trip_input: TripInput, fake_mcp: FakeMCP
    ) -> None:
        """Agent fills input from the original request when finish omits it."""
        output_without_input = dict(SAMPLE_TRIP_OUTPUT)
        output_without_input.pop("input")
        fake_llm = FakeLLM(
            responses=[
                {"tool_calls": [{"name": "finish", "arguments": output_without_input}]},
            ]
        )

        agent = TripAgent(llm_client=fake_llm, mcp_manager=fake_mcp, max_iterations=10)
        result = await agent.run(trip_input)

        assert isinstance(result, TripOutput)
        assert result.input == trip_input


class TestTripOutputCoercion:
    """Test TripOutput model_validator coercion."""

    def test_string_notes_coercion(self) -> None:
        """String notes converted to list."""
        data = {
            "title": "Test Trip",
            "input": {
                "city": "北京",
                "date": "2025-05-15",
                "days": 1,
                "interests": ["历史"],
                "companions": "solo",
            },
            "notes": "Single note",
            "items": [],
        }
        result = TripOutput.model_validate(data)
        assert result.notes == ["Single note"]

    def test_total_cost_alias(self) -> None:
        """total_cost mapped to total_budget."""
        data = {
            "title": "Test Trip",
            "input": {
                "city": "北京",
                "date": "2025-05-15",
                "days": 1,
                "interests": ["历史"],
                "companions": "solo",
            },
            "total_cost": 500.0,
            "items": [],
        }
        result = TripOutput.model_validate(data)
        assert result.total_budget == 500.0

    def test_missing_input_defaults(self) -> None:
        """Missing input gets empty dict, then defaults."""
        data = {
            "title": "Test Trip",
            "items": [],
        }
        with pytest.raises(Exception):
            TripOutput.model_validate(data)


class TestPlaceCoercion:
    """Test Place model_validator coercion."""

    def test_string_place_coercion(self) -> None:
        """String place name converted to Place object."""
        data = "故宫博物院"
        result = Place.model_validate(data)
        assert result.name == "故宫博物院"

    def test_dict_place_preserved(self) -> None:
        """Dict place data preserved."""
        data = {
            "name": "故宫博物院",
            "address": "北京市东城区",
            "coordinates": {"lat": 39.9, "lng": 116.4},
        }
        result = Place.model_validate(data)
        assert result.name == "故宫博物院"
        assert result.coordinates is not None
        assert result.coordinates.lat == 39.9

    def test_coordinate_string_coercion(self) -> None:
        """AMap lng,lat coordinate strings are converted to Coordinates."""
        result = Coordinates.model_validate("114.4258,30.6076")

        assert result.lng == 114.4258
        assert result.lat == 30.6076

    def test_place_location_string_coerces_to_coordinates(self) -> None:
        """Place.location from POI data is reused as coordinates when needed."""
        result = Place.model_validate({"name": "东湖", "location": "114.4258,30.6076"})

        assert result.coordinates is not None
        assert result.coordinates.lng == 114.4258
        assert result.coordinates.lat == 30.6076

    def test_trip_output_accepts_coordinate_strings(self) -> None:
        """LLM finish output can include coordinates as AMap lng,lat strings."""
        data = {
            "title": "武汉周末游",
            "input": {
                "city": "武汉",
                "date": "2026-05-16",
                "days": 1,
                "interests": ["美食"],
                "companions": "solo",
            },
            "items": [
                {
                    "start_time": "09:00",
                    "end_time": "11:00",
                    "activity": "东湖游览",
                    "place": {
                        "name": "东湖",
                        "coordinates": "114.4258,30.6076",
                    },
                }
            ],
        }

        result = TripOutput.model_validate(data)

        assert result.items[0].place.coordinates is not None
        assert result.items[0].place.coordinates.lng == 114.4258
        assert result.items[0].place.coordinates.lat == 30.6076

    def test_trip_item_accepts_train_detail_aliases(self) -> None:
        """Train/flight aliases are normalized into transport_detail."""
        data = {
            "start_time": "08:00",
            "end_time": "12:30",
            "activity": "乘坐高铁",
            "place": "上海虹桥站",
            "train": {
                "train_number": "G1234",
                "from_station": "北京南",
                "to_station": "上海虹桥",
                "depart_time": "08:00",
                "arrive_time": "12:30",
                "price": "553",
            },
        }

        result = TripItem.model_validate(data)

        assert result.transport_detail is not None
        assert result.transport_detail.code == "G1234"
        assert result.transport_detail.departure == "北京南"
        assert result.transport_detail.arrival == "上海虹桥"
        assert result.transport_detail.cost == 553.0
