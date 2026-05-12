from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI

from app.agent.errors import AgentOutputError
from app.agent.tools import SYSTEM_PROMPT, TOOL_DEFINITIONS
from app.mcp.client import MCPClientManager
from app.models.trip import TripInput, TripOutput

logger = logging.getLogger(__name__)


class TripAgent:
    def __init__(
        self,
        *,
        llm_client: AsyncOpenAI,
        mcp_manager: MCPClientManager,
        model: str = "gpt-4o-mini",
        max_iterations: int = 8,
    ) -> None:
        self.llm = llm_client
        self.mcp = mcp_manager
        self.model = model
        self.max_iterations = max_iterations

    async def run(self, trip_input: TripInput) -> TripOutput:
        self._region = self._detect_region(trip_input.city)
        self._route = self._get_route()
        self._weather_summary: dict[str, Any] | None = None
        self._city_coordinates: dict[str, float] | None = None
        self._tool_errors: list[str] = []
        logger.info(
            "Detected region: %s, route: primary=%s, shared=%s",
            self._region,
            self._route.primary,
            self._route.shared,
        )

        messages = self._build_initial_messages(trip_input)

        for iteration in range(self.max_iterations):
            logger.debug("Agent iteration %d", iteration)

            try:
                response = await self.llm.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=0.4,
                )
            except Exception:
                logger.exception("LLM request failed")
                return self._build_fallback_output(trip_input, "模型调用超时或失败")

            message = response.choices[0].message
            messages.append(message.model_dump(exclude_none=True))

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "finish":
                        return self._parse_finish_output(tool_call.function.arguments, trip_input)

                    result = await self._execute_tool(tool_call.function.name, tool_call.function.arguments)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

            elif message.content:
                logger.debug("LLM text output: %s", message.content[:200])

        return self._build_fallback_output(
            trip_input,
            f"Agent exceeded {self.max_iterations} iterations before finish",
        )

    def _detect_region(self, city: str) -> str:
        if self._is_chinese(city):
            return "domestic"
        return "international"

    def _get_route(self) -> Any:
        routes = self.mcp.config.routes
        route = routes.get(self._region)
        if not route:
            route = routes.get("domestic")
        if not route:
            from app.mcp.models import RouteConfig
            route = RouteConfig(primary="amap-mcp", shared=[])
        return route

    def _build_initial_messages(self, trip_input: TripInput) -> list[dict[str, Any]]:
        region_hint = "国内城市，使用高德地图" if self._region == "domestic" else "国际城市，使用Google Maps"

        user_prompt = f"""请规划以下周末行程：

城市：{trip_input.city}
日期：{trip_input.date.isoformat()}
天数：{trip_input.days}
预算：{trip_input.budget or '未指定'}
兴趣：{', '.join(trip_input.interests)}
同行：{trip_input.companions}
出发城市：{trip_input.departure_city or '未指定'}

区域判断：{region_hint}
请自主收集数据并生成行程。"""

        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

    async def _execute_tool(self, tool_name: str, arguments: str) -> str:
        try:
            params = json.loads(arguments)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON arguments"}, ensure_ascii=False)

        try:
            if tool_name == "geocode":
                server_name = self._resolve_server_for_tool("geocode")
                if not server_name:
                    return json.dumps(
                        {
                            "error": f"No available server for geocode in {self._region}",
                            "hint": (
                                "Please configure AMAP_API_KEY for domestic cities or "
                                "GOOGLE_MAPS_API_KEY for international cities."
                            ),
                        },
                        ensure_ascii=False,
                    )

                api_tool = self._resolve_mcp_tool_name(server_name, "geocode")
                result = await self.mcp.call(server_name, api_tool, params)
                coordinates = self._extract_coordinates(result)
                if coordinates:
                    self._city_coordinates = coordinates
                return json.dumps(result, ensure_ascii=False)

            if tool_name == "search_poi":
                server_name = self._resolve_server_for_tool("search_poi")
                if not server_name:
                    return json.dumps(
                        {"error": f"No available server for search_poi in {self._region}"},
                        ensure_ascii=False,
                    )

                api_tool = self._resolve_mcp_tool_name(server_name, "search_poi")
                result = await self.mcp.call(server_name, api_tool, params)
                return json.dumps(result, ensure_ascii=False)

            if tool_name == "get_weather":
                result = await self._execute_weather_tool(params)
                weather_summary = self._extract_weather_summary(result)
                if weather_summary:
                    self._weather_summary = weather_summary
                return json.dumps(result, ensure_ascii=False)

            if tool_name == "query_trains":
                if self._region != "domestic":
                    return json.dumps(
                        {"error": "Train query only available for domestic (China) cities"},
                        ensure_ascii=False,
                    )

                server_name = self._resolve_server_for_tool("query_trains")
                if not server_name:
                    return json.dumps({"error": "Train service not available"}, ensure_ascii=False)

                result = await self.mcp.call(server_name, "query_trains", params)
                return json.dumps(result, ensure_ascii=False)

            return json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)

        except Exception as exc:
            logger.warning("Tool %s failed: %s", tool_name, exc)
            error = f"{tool_name}: {exc}"
            self._tool_errors.append(error)
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    def _resolve_server_for_tool(self, tool_name: str) -> str | None:
        servers = self.mcp.config.servers
        route = self._route

        candidates = [route.primary] + route.shared

        for server_name in candidates:
            server = servers.get(server_name)
            if not server or not server.enabled:
                continue

            if self._resolve_mcp_tool_name(server_name, tool_name) in server.tools:
                return server_name

        return None

    def _resolve_mcp_tool_name(self, server_name: str, logical_tool_name: str) -> str:
        server = self.mcp.config.servers.get(server_name)
        if not server:
            return logical_tool_name

        aliases = {
            "geocode": ["geocode", "maps_geo", "maps_geocode"],
            "search_poi": [
                "search_poi",
                "search_poi_around",
                "maps_search_nearby",
                "place/nearbysearch",
            ],
            "get_weather": ["get_forecast", "get_weather"],
            "query_trains": ["query_trains"],
        }
        for candidate in aliases.get(logical_tool_name, [logical_tool_name]):
            if candidate in server.tools:
                return candidate
        return logical_tool_name

    async def _execute_weather_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        server_name = self._resolve_server_for_tool("get_weather")
        if not server_name:
            return {"error": "No weather service available"}

        forecast_tool = self._resolve_mcp_tool_name(server_name, "get_weather")
        latitude = params.get("latitude")
        longitude = params.get("longitude")

        if (latitude is None or longitude is None) and self._city_coordinates:
            latitude = self._city_coordinates["latitude"]
            longitude = self._city_coordinates["longitude"]

        if latitude is None or longitude is None:
            city = params.get("city") or params.get("query") or params.get("location")
            if not city:
                return {"error": "Weather query requires city or coordinates"}

            location_result = await self._resolve_weather_location(str(city), server_name)
            coordinates = self._extract_coordinates(location_result)
            if coordinates is None:
                return {
                    "error": "Failed to resolve weather location coordinates",
                    "location_result": location_result,
                }
            latitude = coordinates["latitude"]
            longitude = coordinates["longitude"]

        forecast_params = {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "days": max(1, min(int(params.get("days") or 3), 7)),
        }
        try:
            return await self.mcp.call(server_name, forecast_tool, forecast_params)
        except Exception as exc:
            return {
                "error": "Weather forecast unavailable",
                "detail": str(exc),
                "coordinates": {"latitude": forecast_params["latitude"], "longitude": forecast_params["longitude"]},
            }

    def _extract_coordinates(self, result: dict[str, Any]) -> dict[str, float] | None:
        latitude = result.get("latitude") or result.get("lat")
        longitude = result.get("longitude") or result.get("lng") or result.get("lon")
        if (latitude is None or longitude is None) and isinstance(result.get("location"), str):
            parts = [part.strip() for part in result["location"].split(",")]
            if len(parts) >= 2:
                longitude, latitude = parts[0], parts[1]
        if (latitude is None or longitude is None) and isinstance(result.get("geocodes"), list):
            for geocode in result["geocodes"]:
                if isinstance(geocode, dict):
                    coordinates = self._extract_coordinates(geocode)
                    if coordinates:
                        return coordinates
        if latitude is not None and longitude is not None:
            try:
                return {"latitude": float(latitude), "longitude": float(longitude)}
            except (TypeError, ValueError):
                return None

        text = result.get("text")
        if isinstance(text, str):
            match = re.search(
                r"Latitude:\s*(-?\d+(?:\.\d+)?),\s*Longitude:\s*(-?\d+(?:\.\d+)?)",
                text,
                re.IGNORECASE,
            )
            if match is None:
                match = re.search(
                    r"Coordinates:\s*(-?\d+(?:\.\d+)?)°?,\s*(-?\d+(?:\.\d+)?)°?",
                    text,
                    re.IGNORECASE,
                )
            if match:
                return {"latitude": float(match.group(1)), "longitude": float(match.group(2))}

        return None

    async def _resolve_weather_location(self, city: str, weather_server_name: str) -> dict[str, Any]:
        if self._is_chinese(city):
            geocode_server_name = self._resolve_server_for_tool("geocode")
            if geocode_server_name:
                geocode_tool = self._resolve_mcp_tool_name(geocode_server_name, "geocode")
                geocode_result = await self.mcp.call(
                    geocode_server_name,
                    geocode_tool,
                    {"address": city},
                )
                coordinates = self._extract_coordinates(geocode_result)
                if coordinates:
                    self._city_coordinates = coordinates
                    return coordinates
                return {
                    "error": f"Failed to resolve Chinese city coordinates: {city}",
                    "geocode_result": geocode_result,
                }

            return {
                "error": f"No geocode service available for Chinese city: {city}",
            }

        return await self.mcp.call(
            weather_server_name,
            "search_location",
            {"query": city, "limit": 1},
        )

    def _is_chinese(self, text: str) -> bool:
        for char in text:
            if "\u4e00" <= char <= "\u9fff":
                return True
        return False

    def _parse_finish_output(self, arguments: str, trip_input: TripInput) -> TripOutput:
        try:
            data = json.loads(arguments)
            data["input"] = trip_input.model_dump(mode="json")
            data["region"] = self._region
            if self._weather_summary:
                data["weather_summary"] = self._weather_summary
            elif self._is_missing_weather(data.get("weather_summary")):
                data.pop("weather_summary", None)
            if self._tool_errors:
                notes = data.get("notes") or []
                if isinstance(notes, str):
                    notes = [notes]
                data["notes"] = [
                    *notes,
                    *[f"MCP工具调用失败：{error}" for error in self._tool_errors[:3]],
                ]
            return TripOutput.model_validate(data)
        except Exception as exc:
            raise AgentOutputError(f"Failed to parse TripOutput: {exc}")

    def _build_fallback_output(self, trip_input: TripInput, reason: str) -> TripOutput:
        logger.warning("Falling back to deterministic trip output: %s", reason)
        daily_items = [
            {
                "start_time": "09:30",
                "end_time": "12:00",
                "activity": f"{trip_input.city}核心景点游览",
                "place": {"name": f"{trip_input.city}核心景区"},
                "notes": "外部数据不可用时生成的保守安排，建议出发前核对开放时间。",
            },
            {
                "start_time": "12:00",
                "end_time": "14:00",
                "activity": "本地特色午餐",
                "place": {"name": f"{trip_input.city}本地餐馆"},
            },
            {
                "start_time": "14:00",
                "end_time": "17:30",
                "activity": f"围绕{', '.join(trip_input.interests)}的城市探索",
                "place": {"name": f"{trip_input.city}城市街区"},
            },
            {
                "start_time": "18:00",
                "end_time": "20:00",
                "activity": "晚餐与夜间散步",
                "place": {"name": f"{trip_input.city}夜间休闲区"},
            },
        ]
        items = daily_items * trip_input.days

        return TripOutput.model_validate(
            {
                "title": f"{trip_input.city}{trip_input.days}日周末游（数据受限）",
                "input": trip_input.model_dump(mode="json"),
                "region": self._region,
                "items": items,
                "weather_summary": self._weather_summary
                or {"summary": "天气数据暂不可用，请出发前再次确认。"},
                "total_budget": trip_input.budget,
                "notes": [
                    "由于模型或外部工具响应超时，本行程使用降级模式生成。",
                    reason,
                    *[f"MCP工具调用失败：{error}" for error in self._tool_errors[:3]],
                ],
            }
        )

    def _extract_weather_summary(self, result: dict[str, Any]) -> dict[str, Any] | None:
        if not result or result.get("error"):
            return None

        live_weather = self._first_mapping(result.get("lives"))
        if live_weather:
            weather = live_weather.get("weather")
            temperature = live_weather.get("temperature")
            city = live_weather.get("city") or live_weather.get("province")
            return self._build_weather_summary(city, weather, temperature)

        forecast = self._first_mapping(result.get("forecasts"))
        cast = self._first_mapping(forecast.get("casts")) if forecast else None
        if cast:
            weather = cast.get("dayweather") or cast.get("nightweather")
            temperature = cast.get("daytemp") or cast.get("nighttemp")
            city = forecast.get("city") if forecast else None
            return self._build_weather_summary(city, weather, temperature)

        weather = result.get("weather") or result.get("condition")
        temperature = (
            result.get("temperature")
            or result.get("temperature_c")
            or result.get("temp")
            or result.get("temp_c")
        )
        if weather or temperature:
            return self._build_weather_summary(result.get("city"), weather, temperature)

        daily_summary = self._extract_daily_weather_summary(result)
        if daily_summary:
            return daily_summary

        content_text = self._extract_content_text(result)
        if content_text:
            return self._build_weather_summary_from_text(content_text)

        text = result.get("text") or result.get("summary") or result.get("forecast")
        if isinstance(text, str) and text.strip():
            return self._build_weather_summary_from_text(text)

        return None

    def _extract_daily_weather_summary(self, result: dict[str, Any]) -> dict[str, Any] | None:
        daily = self._first_mapping(result.get("daily"))
        if not daily:
            return None

        high = self._first_sequence_value(daily.get("temperature_2m_max"))
        low = self._first_sequence_value(daily.get("temperature_2m_min"))
        condition = self._first_sequence_value(daily.get("weather") or daily.get("condition"))
        parts = []
        if condition not in (None, ""):
            parts.append(str(condition))
        if high not in (None, "") and low not in (None, ""):
            parts.append(f"{high}-{low}°C")
        elif high not in (None, ""):
            parts.append(f"{high}°C")
        if not parts:
            return None
        return {"summary": "，".join(parts)}

    def _extract_content_text(self, result: dict[str, Any]) -> str | None:
        content = result.get("content")
        if not isinstance(content, list):
            return None

        texts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                texts.append(item["text"])
            elif hasattr(item, "text") and isinstance(item.text, str):
                texts.append(item.text)
        joined = "\n".join(text.strip() for text in texts if text.strip())
        return joined or None

    def _build_weather_summary_from_text(self, text: str) -> dict[str, Any] | None:
        cleaned = text.strip()
        if not cleaned:
            return None

        temperature = self._extract_markdown_field(cleaned, "Temperature")
        conditions = self._extract_markdown_field(cleaned, "Conditions")
        precipitation = self._extract_markdown_field(cleaned, "Precipitation Chance")

        parts = [part for part in (conditions, temperature) if part]
        if precipitation:
            parts.append(f"降水概率 {precipitation}")
        if parts:
            return {"summary": "，".join(parts)}

        first_content_line = next(
            (
                line.strip("#* -")
                for line in cleaned.splitlines()
                if line.strip() and not line.startswith("---")
            ),
            "",
        )
        if first_content_line:
            return {"summary": first_content_line}
        return None

    def _extract_markdown_field(self, text: str, field_name: str) -> str | None:
        pattern = rf"^\s*\*\*{re.escape(field_name)}:\*\*\s*(.+?)\s*$"
        match = re.search(pattern, text, re.MULTILINE)
        if not match:
            return None
        return match.group(1).strip()

    def _first_sequence_value(self, value: Any) -> Any:
        if isinstance(value, list) and value:
            return value[0]
        return value

    def _build_weather_summary(
        self,
        city: Any,
        weather: Any,
        temperature: Any,
    ) -> dict[str, Any] | None:
        parts = [str(value).strip() for value in (city, weather) if value not in (None, "")]
        if temperature not in (None, ""):
            parts.append(f"{temperature}°C")
        if not parts:
            return None

        summary: dict[str, Any] = {"summary": "，".join(parts)}
        try:
            summary["temperature_c"] = float(temperature)
        except (TypeError, ValueError):
            pass
        return summary

    def _first_mapping(self, value: Any) -> dict[str, Any] | None:
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value[0]
        if isinstance(value, dict):
            return value
        return None

    def _is_missing_weather(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return self._is_unavailable_weather_text(value)
        if isinstance(value, dict):
            summary = value.get("summary")
            return not summary or self._is_unavailable_weather_text(str(summary))
        return False

    def _is_unavailable_weather_text(self, text: str) -> bool:
        normalized = text.strip().lower()
        return not normalized or any(
            phrase in normalized
            for phrase in ("不可用", "暂不可用", "无法获取", "unknown", "unavailable")
        )
