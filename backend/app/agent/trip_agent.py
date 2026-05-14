from __future__ import annotations

import json
import logging
import re
from time import perf_counter
from typing import Any

from openai import AsyncOpenAI

from app.agent.city_coordinates import CITY_COORDINATES, get_city_coordinates
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
        self._requested_city = self._normalize_destination_city(trip_input.city)
        self._destination_city = self._requested_city
        self._random_destination = self._destination_city is None
        self._region = self._detect_region(self._destination_city or trip_input.departure_city)
        self._route = self._get_route()
        self._weather_summary: dict[str, Any] | None = None
        self._city_coordinates: dict[str, float] | None = None
        self._departure_coordinates: dict[str, float] | None = None
        self._poi_places: list[dict[str, Any]] = []
        self._transport_options: list[dict[str, Any]] = []
        self._tool_errors: list[str] = []
        self._failed_tool_results: dict[str, str] = {}
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

    def _detect_region(self, city: str | None) -> str:
        if not city:
            return "domestic"
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
        destination = self._destination_city or (
            "未指定（随机目的地模式：请根据出发城市、日期、天数、预算、兴趣、同行和备注，"
            "自主选择一个适合周末旅行的具体目的地城市）"
        )
        random_destination_instruction = ""
        if self._random_destination:
            random_destination_instruction = (
                "\n随机目的地要求：先选择一个明确的目的地城市，并在第一次调用geocode、get_weather、"
                "search_poi、query_trains以及最终finish.city中都使用该城市。"
                "若未指定出发城市，优先选择中国国内周末游热门城市；若指定出发城市，优先选择交通便利、"
                "符合天数和预算的周边或直达城市。"
            )

        user_prompt = f"""请规划以下周末行程：

城市：{destination}
日期：{trip_input.date.isoformat()}
天数：{trip_input.days}
预算：{trip_input.budget or '未指定'}
兴趣：{', '.join(trip_input.interests)}
同行：{trip_input.companions}
出发城市：{trip_input.departure_city or '未指定'}

区域判断：{region_hint}
请自主收集数据并生成行程。{random_destination_instruction}"""

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
        failure_cache_key = self._tool_failure_cache_key(tool_name, params)
        if failure_cache_key in self._failed_tool_results:
            logger.info(
                "trip_generation[%s] tool call skipped after previous failure tool=%s params=%s",
                self.job_id,
                tool_name,
                self._json_preview(params),
            )
            return self._failed_tool_results[failure_cache_key]
        try:
            if tool_name == "geocode":
                self._capture_destination_city(params.get("address") or params.get("city") or params.get("query"))
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
                params = self._prepare_mcp_params(server_name, api_tool, params)
                self._log_mcp_call(tool_name, server_name, api_tool)
                result = await self.mcp.call(server_name, api_tool, params)
                coordinates = self._extract_coordinates(result)
                if coordinates:
                    self._city_coordinates = coordinates
                else:
                    fallback_coordinates = get_city_coordinates(str(params.get("address") or ""))
                    if fallback_coordinates:
                        self._city_coordinates = {
                            "latitude": fallback_coordinates["lat"],
                            "longitude": fallback_coordinates["lng"],
                        }
                        result = {
                            **result,
                            "fallback_coordinates": self._coordinates_to_place_dict(self._city_coordinates),
                        }
                return self._finish_tool_result(tool_name, result, started_at)

            if tool_name == "search_poi":
                self._capture_destination_city(params.get("city"))
                server_name = self._resolve_server_for_tool("search_poi")
                if not server_name:
                    return self._finish_tool_result(
                        tool_name,
                        {"error": f"No available server for search_poi in {self._region}"},
                        started_at,
                    )

                api_tool = self._resolve_search_poi_tool(server_name, params)
                params = self._prepare_mcp_params(server_name, api_tool, params)
                self._log_mcp_call(tool_name, server_name, api_tool)
                result = await self.mcp.call(server_name, api_tool, params)
                result = await self._enrich_poi_search_result(server_name, result)
                self._poi_places.extend(self._extract_poi_places(result))
                return self._finish_tool_result(tool_name, result, started_at)

            if tool_name == "get_weather":
                self._capture_destination_city(params.get("city") or params.get("query") or params.get("location"))
                result = await self._execute_weather_tool(params)
                weather_summary = self._extract_weather_summary(result)
                if weather_summary:
                    self._weather_summary = weather_summary
                return self._finish_tool_result(tool_name, result, started_at)

            if tool_name == "query_trains":
                self._capture_destination_city(params.get("to") or params.get("toStation"))
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

                api_tool = self._resolve_mcp_tool_name(server_name, "query_trains")
                train_params = self._prepare_mcp_params(server_name, api_tool, params)
                self._log_mcp_call(tool_name, server_name, api_tool)
                result = await self.mcp.call(server_name, api_tool, train_params)
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
            result = json.dumps({"error": str(exc)}, ensure_ascii=False)
            self._failed_tool_results[failure_cache_key] = result
            return result

    def _tool_failure_cache_key(self, tool_name: str, params: dict[str, Any]) -> str:
        return f"{tool_name}:{json.dumps(params, ensure_ascii=False, sort_keys=True, default=str)}"

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
        route = self._route

        candidates = [route.primary] + route.shared

        for server_name in candidates:
            server = self.mcp.config.servers.get(server_name)
            if not server or not server.enabled:
                continue

            if self._resolve_mcp_tool_name(server_name, tool_name) in self._available_tools(server_name):
                return server_name

        return None

    def _available_tools(self, server_name: str) -> list[str]:
        if hasattr(self.mcp, "available_tools"):
            return self.mcp.available_tools(server_name)
        server = self.mcp.config.servers.get(server_name)
        return server.tools if server else []

    def _resolve_mcp_tool_name(self, server_name: str, logical_tool_name: str) -> str:
        available_tools = self._available_tools(server_name)

        aliases = {
            "geocode": ["maps_geo", "geocode", "maps_geocode"],
            "search_poi": [
                "maps_around_search",
                "maps_text_search",
                "maps_search_nearby",
                "search_poi_around",
                "search_poi",
                "place/nearbysearch",
            ],
            "get_weather": ["get_forecast", "get_weather"],
            "query_trains": ["get-tickets", "query_trains"],
        }
        for candidate in aliases.get(logical_tool_name, [logical_tool_name]):
            if candidate in available_tools:
                return candidate
        return logical_tool_name

    def _resolve_search_poi_tool(self, server_name: str, params: dict[str, Any]) -> str:
        available_tools = self._available_tools(server_name)
        if server_name == "amap-mcp":
            if (params.get("location") or self._city_coordinates) and "maps_around_search" in available_tools:
                return "maps_around_search"
            if "maps_text_search" in available_tools:
                return "maps_text_search"
        return self._resolve_mcp_tool_name(server_name, "search_poi")

    def _prepare_mcp_params(
        self,
        server_name: str,
        api_tool: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if server_name == "amap-mcp" and api_tool == "maps_geo":
            prepared = {"address": params.get("address") or params.get("city") or params.get("query")}
            if params.get("city"):
                prepared["city"] = params["city"]
            return {key: value for key, value in prepared.items() if value not in (None, "")}

        if server_name == "amap-mcp" and api_tool in {"maps_around_search", "maps_text_search"}:
            query = params.get("query") or params.get("keywords") or params.get("keyword")
            prepared: dict[str, Any] = {}
            if api_tool == "maps_around_search":
                location = params.get("location")
                if not location and self._city_coordinates:
                    location = (
                        f"{self._city_coordinates['longitude']},"
                        f"{self._city_coordinates['latitude']}"
                    )
                prepared["location"] = location
                prepared["radius"] = str(params.get("radius") or 3000)
                if query:
                    prepared["keywords"] = query
            else:
                if query:
                    prepared["keywords"] = query
                city = params.get("city")
                if city:
                    prepared["city"] = city
            return {key: value for key, value in prepared.items() if value not in (None, "")}

        if server_name == "train-12306" and api_tool == "get-tickets":
            return {
                "date": params.get("date"),
                "fromStation": params.get("from") or params.get("fromStation"),
                "toStation": params.get("to") or params.get("toStation"),
                "trainFilterFlags": params.get("trainFilterFlags") or "",
                "sortFlag": params.get("sortFlag") or "startTime",
                "limitedNum": int(params.get("limitedNum") or 5),
                "format": "json",
            }

        return params

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

            fallback_coordinates = get_city_coordinates(str(city))
            if fallback_coordinates:
                latitude = fallback_coordinates["lat"]
                longitude = fallback_coordinates["lng"]
                self._city_coordinates = {
                    "latitude": fallback_coordinates["lat"],
                    "longitude": fallback_coordinates["lng"],
                }
            else:
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
        if (latitude is None or longitude is None) and isinstance(result.get("return"), list):
            for item in result["return"]:
                if isinstance(item, dict):
                    coordinates = self._extract_coordinates(item)
                    if coordinates:
                        return coordinates
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

    async def _enrich_poi_search_result(self, server_name: str, result: Any) -> Any:
        if server_name != "amap-mcp" or not isinstance(result, dict):
            return result
        if "maps_search_detail" not in self._available_tools(server_name):
            return result

        pois = result.get("pois")
        if not isinstance(pois, list):
            return result

        enriched_pois: list[Any] = []
        for poi in pois[:8]:
            if not isinstance(poi, dict) or poi.get("location") or not poi.get("id"):
                enriched_pois.append(poi)
                continue
            try:
                detail = await self.mcp.call(server_name, "maps_search_detail", {"id": poi["id"]})
                if isinstance(detail, dict):
                    enriched_pois.append({**poi, **detail})
                else:
                    enriched_pois.append(poi)
            except Exception as exc:
                logger.info(
                    "trip_generation[%s] POI detail enrichment skipped id=%s error=%s",
                    self.job_id,
                    poi.get("id"),
                    exc,
                )
                enriched_pois.append(poi)
        result["pois"] = [*enriched_pois, *pois[8:]]
        return result

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

    def _is_chinese(self, text: str | None) -> bool:
        if not text:
            return False
        for char in text:
            if "\u4e00" <= char <= "\u9fff":
                return True
        return False

    def _normalize_destination_city(self, city: Any) -> str | None:
        if not isinstance(city, str):
            return None
        normalized = city.strip()
        if re.fullmatch(r"-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?", normalized):
            return None
        return normalized or None

    def _capture_destination_city(self, city: Any) -> None:
        normalized = self._normalize_destination_city(city)
        if not normalized:
            return
        self._destination_city = normalized
        if self._is_chinese(normalized):
            self._region = "domestic"
        elif not self._is_chinese(normalized):
            self._region = "international"

    def _capture_destination_city_from_finish(self, data: dict[str, Any]) -> None:
        candidates = [
            data.get("city"),
            data.get("destination_city"),
            data.get("destination"),
        ]
        input_data = data.get("input")
        if isinstance(input_data, dict):
            candidates.append(input_data.get("city"))
        for candidate in candidates:
            before = self._destination_city
            self._capture_destination_city(candidate)
            if self._destination_city != before:
                return

        if not self._destination_city and isinstance(data.get("title"), str):
            self._capture_destination_city(self._infer_city_from_text(data["title"]))

    def _infer_city_from_text(self, text: str) -> str | None:
        normalized = text.strip()
        for city in CITY_COORDINATES:
            if city in normalized:
                return city
        return None

    def _resolved_destination_city(self, trip_input: TripInput) -> str:
        return (
            self._destination_city
            or self._normalize_destination_city(trip_input.city)
            or self._infer_city_from_text(trip_input.notes or "")
            or self._fallback_destination_city(trip_input)
        )

    def _fallback_destination_city(self, trip_input: TripInput) -> str:
        interest_text = " ".join(trip_input.interests)
        if any(keyword in interest_text for keyword in ("自然", "风光", "摄影", "海", "度假")):
            return "厦门"
        if any(keyword in interest_text for keyword in ("历史", "博物馆", "古迹")):
            return "南京"
        if any(keyword in interest_text for keyword in ("美食", "夜生活", "Citywalk", "citywalk")):
            return "成都"
        if trip_input.departure_city:
            departure = trip_input.departure_city.strip()
            if departure in {"上海", "杭州", "苏州", "南京"}:
                return "杭州" if departure != "杭州" else "苏州"
            if departure in {"北京", "天津"}:
                return "天津" if departure != "天津" else "北京"
        return "杭州"

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
        data["city"] = self._resolved_destination_city(trip_input)
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
            self._capture_destination_city_from_finish(data)
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

        self._ensure_hotel_item(items, trip_input)
        self._sync_total_budget(data, items)

    def _sync_total_budget(self, data: dict[str, Any], items: list[Any]) -> None:
        total = sum(
            float(item["estimated_cost"])
            for item in items
            if isinstance(item, dict) and item.get("estimated_cost") not in (None, "")
        )
        if total <= 0:
            return

        existing = data.get("total_budget")
        try:
            existing_total = float(existing) if existing not in (None, "") else None
        except (TypeError, ValueError):
            existing_total = None
        if existing_total is None or existing_total < total:
            data["total_budget"] = round(total, 2)

    def _ensure_hotel_item(self, items: list[Any], trip_input: TripInput) -> None:
        if self._has_hotel_item(items):
            return

        hotel_place = self._select_hotel_place(trip_input)
        hotel_cost = self._estimate_hotel_cost(trip_input)
        hotel_date = trip_input.date
        items.append(
            {
                "start_time": f"{hotel_date.isoformat()} 20:30",
                "end_time": f"{hotel_date.isoformat()} 21:00",
                "activity": "酒店入住/休息",
                "place": hotel_place,
                "estimated_cost": hotel_cost,
                "transport": "前往酒店",
                "notes": "模型未返回酒店安排，系统已补充住宿节点；请出发前核对房型、余量和价格。",
            }
        )

    def _has_hotel_item(self, items: list[Any]) -> bool:
        for item in items:
            if not isinstance(item, dict):
                continue
            text = " ".join(
                str(value)
                for value in (
                    item.get("activity"),
                    item.get("transport"),
                    item.get("notes"),
                    self._place_name(item.get("place")),
                    self._place_category(item.get("place")),
                )
                if value
            )
            if self._is_hotel_text(text):
                return True
        return False

    def _select_hotel_place(self, trip_input: TripInput) -> dict[str, Any]:
        destination_city = self._resolved_destination_city(trip_input)
        for poi in self._poi_places:
            text = " ".join(
                str(value)
                for value in (poi.get("name"), poi.get("category"), poi.get("address"))
                if value
            )
            if self._is_hotel_text(text):
                return {
                    "name": str(poi.get("name") or f"{destination_city}推荐酒店"),
                    "address": poi.get("address"),
                    "coordinates": poi.get("coordinates"),
                    "rating": poi.get("rating"),
                    "category": "酒店",
                }

        coordinates = self._city_coordinates
        if not coordinates:
            fallback = get_city_coordinates(destination_city)
            if fallback:
                coordinates = {"latitude": fallback["lat"], "longitude": fallback["lng"]}

        place: dict[str, Any] = {
            "name": f"{destination_city}推荐酒店",
            "address": f"{destination_city}核心商圈附近",
            "category": "酒店",
        }
        if coordinates:
            place["coordinates"] = {
                "lat": coordinates["latitude"],
                "lng": coordinates["longitude"],
            }
        return place

    def _estimate_hotel_cost(self, trip_input: TripInput) -> float:
        if trip_input.budget:
            return round(min(max(trip_input.budget * 0.3 / max(trip_input.days, 1), 150), 800), 2)
        if trip_input.companions.value == "family":
            return 450.0
        if trip_input.companions.value in ("couple", "friends"):
            return 350.0
        return 250.0

    def _is_hotel_text(self, value: str) -> bool:
        normalized = value.lower()
        return any(
            keyword in normalized
            for keyword in (
                "酒店",
                "宾馆",
                "住宿",
                "入住",
                "退房",
                "民宿",
                "客栈",
                "hotel",
                "hostel",
                "inn",
                "resort",
            )
        )

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
                    "category": candidate.get("type") or candidate.get("category") or candidate.get("typecode"),
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

    def _place_category(self, place: Any) -> str | None:
        if isinstance(place, dict):
            category = place.get("category")
            return str(category) if category else None
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
        result: Any,
        mode: str,
    ) -> list[dict[str, Any]]:
        candidates: list[Any] = []
        if isinstance(result, list):
            candidates.extend(result)
        elif isinstance(result, dict):
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
            or normalized.get("start_train_code")
            or normalized.get("station_train_code")
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
            or normalized.get("from_station_name")
            or normalized.get("departure_station")
            or normalized.get("departure_airport")
            or normalized.get("出发站"),
        )
        normalized.setdefault(
            "arrival",
            normalized.get("to")
            or normalized.get("to_station")
            or normalized.get("to_station_name")
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
            or normalized.get("startTime")
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
        normalized.setdefault("duration", normalized.get("lishi") or normalized.get("历时"))
        normalized.setdefault(
            "cost",
            normalized.get("price")
            or normalized.get("fare")
            or normalized.get("费用")
            or self._extract_ticket_price(normalized.get("prices")),
        )
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

    def _extract_ticket_price(self, prices: Any) -> float | None:
        if not isinstance(prices, list):
            return None
        for price in prices:
            if not isinstance(price, dict):
                continue
            value = price.get("price") or price.get("amount") or price.get("value")
            if value in (None, ""):
                continue
            if isinstance(value, (int, float)):
                return float(value)
            match = re.search(r"\d+(?:\.\d+)?", str(value))
            if match:
                return float(match.group(0))
        return None

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
        destination_city = self._resolved_destination_city(trip_input)
        daily_items = [
            {
                "start_time": "09:30",
                "end_time": "12:00",
                "activity": f"{destination_city}核心景点游览",
                "place": {"name": f"{destination_city}核心景区"},
                "notes": "外部数据不可用时生成的保守安排，建议出发前核对开放时间。",
            },
            {
                "start_time": "12:00",
                "end_time": "14:00",
                "activity": "本地特色午餐",
                "place": {"name": f"{destination_city}本地餐馆"},
            },
            {
                "start_time": "14:00",
                "end_time": "17:30",
                "activity": f"围绕{', '.join(trip_input.interests)}的城市探索",
                "place": {"name": f"{destination_city}城市街区"},
            },
            {
                "start_time": "18:00",
                "end_time": "20:00",
                "activity": "晚餐与夜间散步",
                "place": {"name": f"{destination_city}夜间休闲区"},
            },
        ]
        items = daily_items * trip_input.days

        return TripOutput.model_validate(
            {
                "title": f"{destination_city}{trip_input.days}日周末游（数据受限）",
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
