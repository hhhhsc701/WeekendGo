from __future__ import annotations

import json
import logging
import re
from time import perf_counter
from typing import Any

from openai import AsyncOpenAI

from app.agent.city_coordinates import get_city_coordinates
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
        job_id: str | None = None,
    ) -> None:
        self.llm = llm_client
        self.mcp = mcp_manager
        self.model = model
        self.max_iterations = max_iterations
        self.job_id = job_id or "local"

    async def run(self, trip_input: TripInput) -> TripOutput:
        self._region = self._detect_region(trip_input.city)
        self._route = self._get_route()
        self._weather_summary: dict[str, Any] | None = None
        self._city_coordinates: dict[str, float] | None = None
        self._departure_coordinates: dict[str, float] | None = None
        self._poi_places: list[dict[str, Any]] = []
        self._transport_options: list[dict[str, Any]] = []
        self._tool_errors: list[str] = []
        logger.info(
            "trip_generation[%s] detected region=%s route_primary=%s route_shared=%s",
            self.job_id,
            self._region,
            self._route.primary,
            self._route.shared,
        )

        await self._prepare_departure_coordinates(trip_input)
        messages = self._build_initial_messages(trip_input)

        for iteration in range(self.max_iterations):
            model_call_number = iteration + 1
            started_at = perf_counter()
            logger.info(
                "trip_generation[%s] model call %d/%d started model=%s messages=%d",
                self.job_id,
                model_call_number,
                self.max_iterations,
                self.model,
                len(messages),
            )

            try:
                response = await self.llm.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=0.4,
                )
            except Exception:
                logger.exception(
                    "trip_generation[%s] model call %d failed elapsed=%.2fs",
                    self.job_id,
                    model_call_number,
                    perf_counter() - started_at,
                )
                return self._build_fallback_output(trip_input, "模型调用超时或失败")

            message = response.choices[0].message
            finish_reason = getattr(response.choices[0], "finish_reason", None)
            tool_call_count = len(message.tool_calls or [])
            usage = getattr(response, "usage", None)
            usage_text = self._format_usage(usage)
            logger.info(
                "trip_generation[%s] model call %d finished elapsed=%.2fs finish_reason=%s tool_calls=%d%s",
                self.job_id,
                model_call_number,
                perf_counter() - started_at,
                finish_reason or "-",
                tool_call_count,
                usage_text,
            )
            messages.append(message.model_dump(exclude_none=True))

            if message.tool_calls:
                logger.info(
                    "trip_generation[%s] model requested tools: %s",
                    self.job_id,
                    ", ".join(tool_call.function.name for tool_call in message.tool_calls),
                )
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "finish":
                        logger.info("trip_generation[%s] finish tool received; parsing itinerary", self.job_id)
                        return self._parse_finish_output(tool_call.function.arguments, trip_input)

                    result = await self._execute_tool(tool_call.function.name, tool_call.function.arguments)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

            elif message.content:
                logger.info(
                    "trip_generation[%s] model returned text content preview=%s",
                    self.job_id,
                    self._preview(message.content),
                )

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
        started_at = perf_counter()
        try:
            params = json.loads(arguments)
        except json.JSONDecodeError:
            logger.warning(
                "trip_generation[%s] tool call skipped tool=%s invalid JSON arguments=%s",
                self.job_id,
                tool_name,
                self._preview(arguments),
            )
            return json.dumps({"error": "Invalid JSON arguments"}, ensure_ascii=False)

        logger.info(
            "trip_generation[%s] tool call started tool=%s params=%s",
            self.job_id,
            tool_name,
            self._json_preview(params),
        )
        try:
            if tool_name == "geocode":
                server_name = self._resolve_server_for_tool("geocode")
                if not server_name:
                    return self._finish_tool_result(
                        tool_name,
                        {
                            "error": f"No available server for geocode in {self._region}",
                            "hint": (
                                "Please configure AMAP_API_KEY for domestic cities or "
                                "GOOGLE_MAPS_API_KEY for international cities."
                            ),
                        },
                        started_at,
                    )

                api_tool = self._resolve_mcp_tool_name(server_name, "geocode")
                self._log_mcp_call(tool_name, server_name, api_tool)
                result = await self.mcp.call(server_name, api_tool, params)
                coordinates = self._extract_coordinates(result)
                if coordinates:
                    self._city_coordinates = coordinates
                return self._finish_tool_result(tool_name, result, started_at)

            if tool_name == "search_poi":
                server_name = self._resolve_server_for_tool("search_poi")
                if not server_name:
                    return self._finish_tool_result(
                        tool_name,
                        {"error": f"No available server for search_poi in {self._region}"},
                        started_at,
                    )

                api_tool = self._resolve_mcp_tool_name(server_name, "search_poi")
                self._log_mcp_call(tool_name, server_name, api_tool)
                result = await self.mcp.call(server_name, api_tool, params)
                self._poi_places.extend(self._extract_poi_places(result))
                return self._finish_tool_result(tool_name, result, started_at)

            if tool_name == "get_weather":
                result = await self._execute_weather_tool(params)
                weather_summary = self._extract_weather_summary(result)
                if weather_summary:
                    self._weather_summary = weather_summary
                return self._finish_tool_result(tool_name, result, started_at)

            if tool_name == "query_trains":
                if self._region != "domestic":
                    return self._finish_tool_result(
                        tool_name,
                        {"error": "Train query only available for domestic (China) cities"},
                        started_at,
                    )

                server_name = self._resolve_server_for_tool("query_trains")
                if not server_name:
                    return self._finish_tool_result(
                        tool_name,
                        {"error": "Train service not available"},
                        started_at,
                    )

                self._log_mcp_call(tool_name, server_name, "query_trains")
                result = await self.mcp.call(server_name, "query_trains", params)
                self._transport_options.extend(self._extract_transport_options(result, "train"))
                return self._finish_tool_result(tool_name, result, started_at)

            return self._finish_tool_result(
                tool_name,
                {"error": f"Unknown tool: {tool_name}"},
                started_at,
            )

        except Exception as exc:
            logger.warning(
                "trip_generation[%s] tool call failed tool=%s elapsed=%.2fs error=%s",
                self.job_id,
                tool_name,
                perf_counter() - started_at,
                exc,
            )
            error = f"{tool_name}: {exc}"
            self._tool_errors.append(error)
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    def _finish_tool_result(self, tool_name: str, result: dict[str, Any], started_at: float) -> str:
        logger.info(
            "trip_generation[%s] tool call finished tool=%s elapsed=%.2fs result=%s",
            self.job_id,
            tool_name,
            perf_counter() - started_at,
            self._json_preview(result),
        )
        return json.dumps(result, ensure_ascii=False)

    def _log_mcp_call(self, tool_name: str, server_name: str, api_tool: str) -> None:
        logger.info(
            "trip_generation[%s] MCP call mapped logical_tool=%s server=%s api_tool=%s",
            self.job_id,
            tool_name,
            server_name,
            api_tool,
        )

    def _json_preview(self, value: Any, max_length: int = 500) -> str:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            text = str(value)
        return self._preview(text, max_length=max_length)

    def _preview(self, value: str, max_length: int = 500) -> str:
        compact = re.sub(r"\s+", " ", value).strip()
        if len(compact) <= max_length:
            return compact
        return f"{compact[:max_length]}..."

    def _format_usage(self, usage: Any) -> str:
        if usage is None:
            return ""
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)
        parts = []
        if prompt_tokens is not None:
            parts.append(f"prompt_tokens={prompt_tokens}")
        if completion_tokens is not None:
            parts.append(f"completion_tokens={completion_tokens}")
        if total_tokens is not None:
            parts.append(f"total_tokens={total_tokens}")
        return f" {' '.join(parts)}" if parts else ""

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

            logger.info(
                "trip_generation[%s] resolving weather location city=%s via server=%s",
                self.job_id,
                city,
                server_name,
            )
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
            self._log_mcp_call("get_weather", server_name, forecast_tool)
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

    async def _prepare_departure_coordinates(self, trip_input: TripInput) -> None:
        if not trip_input.departure_city:
            return

        fallback_coordinates = get_city_coordinates(trip_input.departure_city)
        server_name = self._resolve_server_for_tool("geocode")
        if not server_name:
            if fallback_coordinates:
                self._departure_coordinates = fallback_coordinates
                logger.info(
                    "trip_generation[%s] departure city coordinates used fallback city=%s lat=%s lng=%s",
                    self.job_id,
                    trip_input.departure_city,
                    fallback_coordinates["lat"],
                    fallback_coordinates["lng"],
                )
                return
            logger.info(
                "trip_generation[%s] departure geocode skipped; no geocode server",
                self.job_id,
            )
            return

        api_tool = self._resolve_mcp_tool_name(server_name, "geocode")
        try:
            logger.info(
                "trip_generation[%s] resolving departure city coordinates city=%s server=%s tool=%s",
                self.job_id,
                trip_input.departure_city,
                server_name,
                api_tool,
            )
            result = await self.mcp.call(
                server_name,
                api_tool,
                {"address": trip_input.departure_city},
            )
            coordinates = self._extract_coordinates(result)
            if coordinates:
                self._departure_coordinates = coordinates
                logger.info(
                    "trip_generation[%s] departure city coordinates resolved lat=%s lng=%s",
                    self.job_id,
                    coordinates["latitude"],
                    coordinates["longitude"],
                )
            else:
                logger.info(
                    "trip_generation[%s] departure city coordinates unavailable result=%s",
                    self.job_id,
                    self._json_preview(result),
                )
                if fallback_coordinates:
                    self._departure_coordinates = fallback_coordinates
                    logger.info(
                        "trip_generation[%s] departure city coordinates used fallback city=%s lat=%s lng=%s",
                        self.job_id,
                        trip_input.departure_city,
                        fallback_coordinates["lat"],
                        fallback_coordinates["lng"],
                    )
        except Exception as exc:
            logger.warning(
                "trip_generation[%s] departure city geocode failed city=%s error=%s",
                self.job_id,
                trip_input.departure_city,
                exc,
            )
            self._tool_errors.append(f"departure geocode: {exc}")
            if fallback_coordinates:
                self._departure_coordinates = fallback_coordinates
                logger.info(
                    "trip_generation[%s] departure city coordinates used fallback after geocode failure city=%s lat=%s lng=%s",
                    self.job_id,
                    trip_input.departure_city,
                    fallback_coordinates["lat"],
                    fallback_coordinates["lng"],
                )

    def _trip_input_dump(self, trip_input: TripInput) -> dict[str, Any]:
        data = trip_input.model_dump(mode="json")
        if self._departure_coordinates and not data.get("departure_coordinates"):
            data["departure_coordinates"] = self._coordinates_to_place_dict(self._departure_coordinates)
        return data

    def _coordinates_to_place_dict(self, coordinates: dict[str, float]) -> dict[str, float]:
        return {
            "lat": coordinates["latitude"] if "latitude" in coordinates else coordinates["lat"],
            "lng": coordinates["longitude"] if "longitude" in coordinates else coordinates["lng"],
        }

    def _parse_finish_output(self, arguments: str, trip_input: TripInput) -> TripOutput:
        try:
            logger.info("trip_generation[%s] parsing model finish output", self.job_id)
            data = json.loads(arguments)
            data["input"] = self._trip_input_dump(trip_input)
            data["region"] = self._region
            self._enrich_finish_data(data, trip_input)
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
            trip = TripOutput.model_validate(data)
            logger.info(
                "trip_generation[%s] itinerary parsed title=%s items=%d weather=%s",
                self.job_id,
                trip.title,
                len(trip.items),
                trip.weather_summary.summary,
            )
            return trip
        except Exception as exc:
            logger.warning("trip_generation[%s] failed to parse finish output: %s", self.job_id, exc)
            raise AgentOutputError(f"Failed to parse TripOutput: {exc}")

    def _enrich_finish_data(self, data: dict[str, Any], trip_input: TripInput) -> None:
        items = data.get("items")
        if not isinstance(items, list):
            return

        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            self._enrich_item_place(item, index)
            self._enrich_item_transport(item)
            if item.get("estimated_cost") in (None, ""):
                item["estimated_cost"] = self._estimate_item_cost(item, trip_input)

        if data.get("total_budget") in (None, ""):
            total = sum(
                float(item["estimated_cost"])
                for item in items
                if isinstance(item, dict) and item.get("estimated_cost") not in (None, "")
            )
            if total > 0:
                data["total_budget"] = round(total, 2)

    def _enrich_item_place(self, item: dict[str, Any], index: int) -> None:
        place = item.get("place")
        if isinstance(place, str):
            place = {"name": place}
            item["place"] = place
        if not isinstance(place, dict):
            return
        if place.get("coordinates"):
            return

        poi = self._find_matching_poi(str(place.get("name") or ""))
        if poi is None and index < len(self._poi_places):
            poi = self._poi_places[index]
        if poi is None:
            return

        place.setdefault("name", poi.get("name"))
        place.setdefault("address", poi.get("address"))
        place.setdefault("rating", poi.get("rating"))
        place.setdefault("category", poi.get("category"))
        place["coordinates"] = poi.get("coordinates")

    def _extract_poi_places(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[Any] = []
        for key in ("pois", "places", "results"):
            value = result.get(key)
            if isinstance(value, list):
                candidates.extend(value)

        places: list[dict[str, Any]] = []
        seen: set[str] = set()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            name = candidate.get("name") or candidate.get("title")
            coordinates = self._extract_coordinates(candidate)
            if not name or not coordinates:
                continue

            normalized_name = self._normalize_match_text(str(name))
            if normalized_name in seen:
                continue
            seen.add(normalized_name)
            places.append(
                {
                    "name": str(name),
                    "address": candidate.get("address") or candidate.get("formatted_address"),
                    "coordinates": {
                        "lat": coordinates["latitude"],
                        "lng": coordinates["longitude"],
                    },
                    "rating": candidate.get("rating"),
                    "category": candidate.get("type") or candidate.get("category"),
                }
            )
        return places

    def _find_matching_poi(self, place_name: str) -> dict[str, Any] | None:
        normalized_place = self._normalize_match_text(place_name)
        if not normalized_place:
            return None

        for poi in self._poi_places:
            normalized_poi = self._normalize_match_text(str(poi.get("name") or ""))
            if normalized_place == normalized_poi:
                return poi
        for poi in self._poi_places:
            normalized_poi = self._normalize_match_text(str(poi.get("name") or ""))
            if normalized_place in normalized_poi or normalized_poi in normalized_place:
                return poi
        return None

    def _normalize_match_text(self, value: str) -> str:
        return re.sub(r"\s+", "", value).lower()

    def _estimate_item_cost(self, item: dict[str, Any], trip_input: TripInput) -> float:
        text = " ".join(
            str(value)
            for value in (
                item.get("activity"),
                item.get("transport"),
                self._place_name(item.get("place")),
            )
            if value
        ).lower()

        if any(keyword in text for keyword in ("早餐", "breakfast")):
            return 30.0
        if any(keyword in text for keyword in ("午餐", "晚餐", "餐厅", "美食", "dinner", "lunch", "restaurant")):
            return 80.0
        if any(keyword in text for keyword in ("打车", "出租", "网约车", "taxi")):
            return 40.0
        if any(keyword in text for keyword in ("地铁", "公交", "交通", "metro", "bus")):
            return 10.0
        if any(keyword in text for keyword in ("散步", "漫步", "citywalk", "自由", "公园")):
            return 0.0
        if any(keyword in text for keyword in ("门票", "景区", "博物馆", "展览", "游览", "museum", "ticket")):
            return 60.0
        if trip_input.budget:
            return round(min(max(trip_input.budget / max(trip_input.days * 4, 1), 30), 150), 2)
        return 50.0

    def _place_name(self, place: Any) -> str | None:
        if isinstance(place, dict):
            name = place.get("name")
            return str(name) if name else None
        if isinstance(place, str):
            return place
        return None

    def _enrich_item_transport(self, item: dict[str, Any]) -> None:
        detail = item.get("transport_detail")
        if isinstance(detail, dict):
            normalized = self._normalize_transport_detail(detail)
            self._enrich_transport_coordinates(normalized, item)
            item["transport_detail"] = normalized
            if item.get("estimated_cost") in (None, "") and normalized.get("cost") not in (None, ""):
                item["estimated_cost"] = normalized["cost"]
            return

        transport_text = item.get("transport")
        if not isinstance(transport_text, str) or not transport_text.strip():
            return

        inferred = self._infer_transport_detail(transport_text)
        if inferred:
            self._enrich_transport_coordinates(inferred, item)
            item["transport_detail"] = inferred
            if item.get("estimated_cost") in (None, "") and inferred.get("cost") not in (None, ""):
                item["estimated_cost"] = inferred["cost"]

    def _enrich_transport_coordinates(self, detail: dict[str, Any], item: dict[str, Any]) -> None:
        if self._departure_coordinates and not detail.get("departure_coordinates"):
            detail["departure_coordinates"] = self._coordinates_to_place_dict(self._departure_coordinates)

        if detail.get("arrival_coordinates"):
            return

        place = item.get("place")
        if isinstance(place, dict) and isinstance(place.get("coordinates"), dict):
            detail["arrival_coordinates"] = place["coordinates"]

    def _extract_transport_options(
        self,
        result: dict[str, Any],
        mode: str,
    ) -> list[dict[str, Any]]:
        candidates: list[Any] = []
        for key in ("trains", "train", "results", "items", "data", "list"):
            value = result.get(key)
            if isinstance(value, list):
                candidates.extend(value)
        if not candidates and isinstance(result.get("result"), list):
            candidates.extend(result["result"])

        options: list[dict[str, Any]] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            detail = self._normalize_transport_detail({**candidate, "mode": mode})
            if detail.get("code"):
                options.append(detail)
        return options

    def _normalize_transport_detail(self, detail: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(detail)
        normalized.setdefault(
            "code",
            normalized.get("train_number")
            or normalized.get("train_no")
            or normalized.get("flight_number")
            or normalized.get("flight_no")
            or normalized.get("number")
            or normalized.get("车次")
            or normalized.get("航班号"),
        )
        normalized.setdefault(
            "departure",
            normalized.get("from")
            or normalized.get("from_station")
            or normalized.get("departure_station")
            or normalized.get("departure_airport")
            or normalized.get("出发站"),
        )
        normalized.setdefault(
            "arrival",
            normalized.get("to")
            or normalized.get("to_station")
            or normalized.get("arrival_station")
            or normalized.get("arrival_airport")
            or normalized.get("到达站"),
        )
        normalized.setdefault(
            "departure_coordinates",
            normalized.get("from_coordinates")
            or normalized.get("departure_location")
            or normalized.get("from_location")
            or normalized.get("出发坐标"),
        )
        normalized.setdefault(
            "arrival_coordinates",
            normalized.get("to_coordinates")
            or normalized.get("arrival_location")
            or normalized.get("to_location")
            or normalized.get("到达坐标"),
        )
        normalized.setdefault(
            "departure_time",
            normalized.get("depart_time")
            or normalized.get("start_time")
            or normalized.get("departureTime")
            or normalized.get("出发时间"),
        )
        normalized.setdefault(
            "arrival_time",
            normalized.get("arrive_time")
            or normalized.get("end_time")
            or normalized.get("arrivalTime")
            or normalized.get("到达时间"),
        )
        normalized.setdefault("cost", normalized.get("price") or normalized.get("fare") or normalized.get("费用"))
        cost = normalized.get("cost")
        if isinstance(cost, str):
            match = re.search(r"\d+(?:\.\d+)?", cost)
            normalized["cost"] = float(match.group(0)) if match else None
        return {
            key: normalized.get(key)
            for key in (
                "mode",
                "code",
                "departure",
                "arrival",
                "departure_coordinates",
                "arrival_coordinates",
                "departure_time",
                "arrival_time",
                "duration",
                "cost",
            )
            if normalized.get(key) not in (None, "")
        }

    def _infer_transport_detail(self, transport_text: str) -> dict[str, Any] | None:
        code_match = re.search(r"\b([GDCZTK]\d{1,4}|[A-Z]{2}\d{3,4})\b", transport_text, re.IGNORECASE)
        if not code_match:
            return None

        code = code_match.group(1).upper()
        mode = "flight" if re.match(r"^[A-Z]{2}\d{3,4}$", code) and not code.startswith(("G", "D", "C", "Z", "T", "K")) else "train"
        detail = self._find_transport_option(code) or {"mode": mode, "code": code}
        return self._normalize_transport_detail(detail)

    def _find_transport_option(self, code: str) -> dict[str, Any] | None:
        normalized_code = code.upper()
        for option in self._transport_options:
            option_code = str(option.get("code") or "").upper()
            if option_code == normalized_code:
                return option
        return None

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
                "input": self._trip_input_dump(trip_input),
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
