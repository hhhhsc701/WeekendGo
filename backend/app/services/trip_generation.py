from __future__ import annotations

import json
import logging
from typing import Any

from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.mcp.client import MCPClientManager
from app.mcp.errors import MCPToolError
from app.mcp.region import Region, RegionRouter, fallback_chinese_city_coordinates, is_chinese_city
from app.models.trip import (
    Coordinates,
    GenerationContext,
    Place,
    TransportationInfo,
    TripInput,
    TripOutput,
    WeatherSummary,
)

logger = logging.getLogger(__name__)

INTEREST_TO_POI_TYPES = {
    "outdoor": ["park", "scenic_spot"],
    "food": ["restaurant", "cafe"],
    "photography": ["landmark", "scenic_spot"],
    "culture": ["museum", "gallery", "historical_site"],
    "shopping": ["mall", "market"],
    "family": ["park", "museum", "zoo"],
    "nightlife": ["bar", "live_music"],
    "coffee": ["cafe"],
    "art": ["gallery", "museum"],
    "nature": ["park", "scenic_spot"],
}


class TripGenerationService:
    def __init__(
        self,
        *,
        mcp_manager: MCPClientManager,
        llm_client: LLMClient,
        router: RegionRouter | None = None,
        min_rating: float = 4.0,
    ) -> None:
        self.mcp = mcp_manager
        self.llm = llm_client
        self.router = router or RegionRouter()
        self.min_rating = min_rating

    async def generate(self, trip_input: TripInput) -> TripOutput:
        region = self.router.region_for_city(trip_input.city)
        context = GenerationContext(input=trip_input, region=region)

        context.city_coordinates = await self._locate_city(trip_input.city, region)
        context.weather = await self._get_weather(trip_input, region, context.city_coordinates)
        context.candidate_places = await self._search_places(trip_input, region, context.city_coordinates)
        context.candidate_places = self.filter_places(context.candidate_places)
        context.route = await self._optimize_route(region, context.candidate_places)
        context.transportation = await self._query_transportation(trip_input, region)

        try:
            trip = await self.llm.generate_trip_json(context.model_dump(mode="json"), TripOutput)
        except LLMError:
            logger.exception("LLM trip generation failed")
            raise
        return await self._enrich_trip_output(trip, context)

    async def _locate_city(self, city: str, region: Region) -> Coordinates:
        if region == "domestic":
            result = await self.mcp.call("domestic", "geocode", {"address": city})
        else:
            result = await self.mcp.call("international", "search_location", {"query": city})
        coordinates = extract_coordinates(result)
        if coordinates is None and region == "domestic":
            fallback_coordinates = fallback_chinese_city_coordinates(city)
            if fallback_coordinates is not None:
                logger.warning("Using fallback coordinates for city %s", city)
                lat, lng = fallback_coordinates
                return Coordinates(lat=lat, lng=lng)
        if coordinates is None:
            raise MCPToolError(f"Unable to locate city: {city}")
        return coordinates

    async def _get_weather(
        self,
        trip_input: TripInput,
        region: Region,
        coordinates: Coordinates | None,
    ) -> WeatherSummary:
        try:
            if region == "domestic":
                result = await self.mcp.call(
                    "domestic",
                    "get_weather",
                    {"city": trip_input.city, "date": trip_input.date.isoformat()},
                )
            else:
                result = await self.mcp.call(
                    "international",
                    "get_forecast",
                    {
                        "lat": coordinates.lat if coordinates else None,
                        "lng": coordinates.lng if coordinates else None,
                        "date": trip_input.date.isoformat(),
                    },
                )
            return normalize_weather(result)
        except Exception as exc:  # noqa: BLE001 - weather is optional degradation data
            logger.warning("Weather lookup failed: %s", exc)
            return WeatherSummary(summary="Weather lookup failed", raw={"error": str(exc)})

    async def _search_places(
        self,
        trip_input: TripInput,
        region: Region,
        coordinates: Coordinates | None,
    ) -> list[Place]:
        places: list[Place] = []
        for poi_type in map_interests_to_poi_types(trip_input.interests):
            try:
                if region == "domestic":
                    result = await self.mcp.call(
                        "domestic",
                        "search_poi_around",
                        {
                            "keywords": poi_type,
                            "location": format_coordinates(coordinates),
                            "city": trip_input.city,
                        },
                    )
                else:
                    result = await self.mcp.call(
                        "international",
                        "maps_search_nearby",
                        {
                            "query": poi_type,
                            "lat": coordinates.lat if coordinates else None,
                            "lng": coordinates.lng if coordinates else None,
                        },
                    )
                places.extend(normalize_places(result, category=poi_type))
            except Exception as exc:  # noqa: BLE001 - single POI type failure should degrade
                logger.warning("POI lookup failed for %s: %s", poi_type, exc)
        return places

    def filter_places(self, places: list[Place]) -> list[Place]:
        seen: set[str] = set()
        filtered: list[Place] = []
        for place in sorted(places, key=lambda item: item.rating or 0, reverse=True):
            if place.rating is not None and place.rating < self.min_rating:
                continue
            key = f"{place.name}:{place.address or ''}".lower()
            if key in seen:
                continue
            seen.add(key)
            filtered.append(place)
        return filtered

    async def _optimize_route(self, region: Region, places: list[Place]) -> dict[str, Any]:
        coordinates = [place.coordinates for place in places if place.coordinates]
        if len(coordinates) < 3:
            return {"strategy": "original_order", "reason": "fewer than three places with coordinates"}

        params = {"points": [item.model_dump() for item in coordinates]}
        try:
            if region == "domestic":
                return normalize_mapping(
                    await self.mcp.call("domestic", "driving_route_planning", params)
                )
            return normalize_mapping(await self.mcp.call("international", "maps_plan_route", params))
        except Exception as exc:  # noqa: BLE001 - route failure has a defined fallback
            logger.warning("Route optimization failed: %s", exc)
            return {"strategy": "original_order", "error": str(exc)}

    async def _query_transportation(self, trip_input: TripInput, region: Region) -> TransportationInfo:
        if not trip_input.departure_city:
            return TransportationInfo(summary="No departure city provided")
        if region != "domestic" or not is_chinese_city(trip_input.departure_city):
            return TransportationInfo(summary="Train data is only available for domestic routes")

        try:
            result = await self.mcp.call(
                "domestic",
                "query_trains",
                {
                    "from": trip_input.departure_city,
                    "to": trip_input.city,
                    "date": trip_input.date.isoformat(),
                },
            )
            payload = normalize_mapping(result)
            trains = extract_list(payload)
            return TransportationInfo(summary=f"{len(trains)} trains found", trains=trains, raw=payload)
        except Exception as exc:  # noqa: BLE001 - train data is optional planning context
            logger.warning("Train lookup failed: %s", exc)
            return TransportationInfo(summary="Train lookup failed", raw={"error": str(exc)})

    async def _enrich_trip_output(
        self,
        trip: TripOutput,
        context: GenerationContext,
    ) -> TripOutput:
        if should_prefer_context_weather(trip.weather_summary, context.weather):
            trip.weather_summary = context.weather

        for item in trip.items:
            if item.place.coordinates is not None:
                continue

            matched_place = match_candidate_place(item.place, context.candidate_places)
            if matched_place and matched_place.coordinates:
                item.place.coordinates = matched_place.coordinates
                if item.place.address is None:
                    item.place.address = matched_place.address
                if item.place.rating is None:
                    item.place.rating = matched_place.rating
                continue

            coordinates = await self._locate_place(item.place, trip.input.city, trip.region)
            if coordinates is not None:
                item.place.coordinates = coordinates

        return trip

    async def _locate_place(
        self,
        place: Place,
        city: str,
        region: Region,
    ) -> Coordinates | None:
        query = place.address or place.name
        if not query or query.lower() == "unknown place":
            return None
        if "/" in query or "->" in query:
            return None
        if region == "domestic":
            query = query if city in query else f"{city}{query}"
            params = {"address": query}
            route = "domestic"
            tool = "geocode"
        else:
            params = {"address": query}
            route = "international"
            tool = "geocode"

        try:
            return extract_coordinates(await self.mcp.call(route, tool, params))
        except Exception as exc:  # noqa: BLE001 - place geocoding is best-effort enrichment
            logger.debug("Place geocoding failed for %s: %s", query, exc)
            return None


def map_interests_to_poi_types(interests: list[str]) -> list[str]:
    mapped: list[str] = []
    for interest in interests:
        key = interest.strip().lower()
        mapped.extend(INTEREST_TO_POI_TYPES.get(key, [key]))
    return list(dict.fromkeys(mapped))


def format_coordinates(coordinates: Coordinates | None) -> str | None:
    if coordinates is None:
        return None
    return f"{coordinates.lng},{coordinates.lat}"


def normalize_mapping(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, dict):
        if "content" in value:
            extracted = extract_content_payload(value["content"])
            if extracted is not None:
                return normalize_mapping(extracted)
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"text": value}
        return normalize_mapping(parsed)
    if hasattr(value, "content"):
        content = getattr(value, "content")
        extracted = extract_content_payload(content)
        if extracted is not None:
            return normalize_mapping(extracted)
        return {"content": content}
    return {"value": value}


def extract_list(value: Any) -> list[dict[str, Any]]:
    payload = normalize_mapping(value)
    for key in ("items", "pois", "results", "data", "trains", "geocodes", "return"):
        items = payload.get(key)
        if isinstance(items, list):
            return [normalize_mapping(item) for item in items]
    if isinstance(value, list):
        return [normalize_mapping(item) for item in value]
    return []


def extract_content_payload(content: Any) -> Any | None:
    if isinstance(content, list):
        payloads = []
        for item in content:
            if hasattr(item, "text"):
                payloads.append(getattr(item, "text"))
            elif isinstance(item, dict) and "text" in item:
                payloads.append(item["text"])
        if len(payloads) == 1:
            return payloads[0]
        if payloads:
            return {"items": payloads}
    return None


def extract_coordinates(value: Any) -> Coordinates | None:
    payload = normalize_mapping(value)
    candidates = [payload, *extract_list(payload)]
    for item in candidates:
        lat = item.get("lat") or item.get("latitude")
        lng = item.get("lng") or item.get("lon") or item.get("longitude")
        location = item.get("location")
        if (lat is None or lng is None) and isinstance(location, str) and "," in location:
            first, second = location.split(",", 1)
            lng, lat = first, second
        try:
            if lat is not None and lng is not None:
                return Coordinates(lat=float(lat), lng=float(lng))
        except (TypeError, ValueError):
            continue
    return None


def normalize_places(value: Any, *, category: str | None = None) -> list[Place]:
    places: list[Place] = []
    for item in extract_list(value):
        name = item.get("name") or item.get("title") or item.get("formatted_address")
        if not name:
            continue
        rating = item.get("rating") or item.get("score")
        if rating is None and isinstance(item.get("biz_ext"), dict):
            rating = item["biz_ext"].get("rating")
        distance = item.get("distance") or item.get("distance_meters")
        places.append(
            Place(
                name=str(name),
                address=item.get("address") or item.get("formatted_address") or item.get("vicinity"),
                coordinates=extract_coordinates(item),
                rating=safe_float(rating),
                distance_meters=safe_float(distance),
                category=category,
                raw=item,
            )
        )
    return places


def normalize_weather(value: Any) -> WeatherSummary:
    payload = normalize_mapping(value)
    weather_item = extract_weather_item(payload)
    source = weather_item or payload
    temperature = source.get("temperature") or source.get("temperature_c") or source.get("temp")
    rain_probability = source.get("rain_probability") or source.get("precipitation_probability")
    summary = (
        source.get("summary")
        or source.get("weather")
        or source.get("condition")
        or source.get("text")
        or "Weather data available"
    )
    if weather_item is not None:
        city = weather_item.get("city") or weather_item.get("province")
        wind = weather_item.get("winddirection")
        humidity = weather_item.get("humidity")
        parts = [str(summary)]
        if temperature not in (None, ""):
            parts.append(f"{temperature}°C")
        if humidity not in (None, ""):
            parts.append(f"湿度 {humidity}%")
        if wind:
            parts.append(f"{wind}风")
        summary = f"{city}: {'，'.join(parts)}" if city else "，".join(parts)
    return WeatherSummary(
        summary=str(summary),
        temperature_c=safe_float(temperature),
        rain_probability=safe_float(rain_probability),
        raw=payload,
    )


def extract_weather_item(payload: dict[str, Any]) -> dict[str, Any] | None:
    lives = payload.get("lives")
    if isinstance(lives, list) and lives and isinstance(lives[0], dict):
        return normalize_mapping(lives[0])

    forecasts = payload.get("forecasts")
    if isinstance(forecasts, list) and forecasts and isinstance(forecasts[0], dict):
        forecast = normalize_mapping(forecasts[0])
        casts = forecast.get("casts")
        if isinstance(casts, list) and casts and isinstance(casts[0], dict):
            cast = normalize_mapping(casts[0])
            return {
                **cast,
                "city": forecast.get("city"),
                "province": forecast.get("province"),
                "weather": cast.get("dayweather") or cast.get("nightweather"),
                "temperature": cast.get("daytemp") or cast.get("nighttemp"),
            }
        if forecast.get("dayweather") or forecast.get("nightweather"):
            return {
                **forecast,
                "weather": forecast.get("dayweather") or forecast.get("nightweather"),
                "temperature": forecast.get("daytemp") or forecast.get("nighttemp"),
                "winddirection": forecast.get("daywind") or forecast.get("nightwind"),
            }
    return None


def should_prefer_context_weather(llm_weather: WeatherSummary, context_weather: WeatherSummary) -> bool:
    if context_weather.raw.get("error"):
        return False
    summary = llm_weather.summary.strip().lower()
    if not summary:
        return True
    unavailable_tokens = (
        "unavailable",
        "lookup failed",
        "工具调用失败",
        "数据获取失败",
        "暂无天气",
        "天气接口调用失败",
    )
    return any(token in summary for token in unavailable_tokens)


def match_candidate_place(place: Place, candidates: list[Place]) -> Place | None:
    place_key = normalize_place_key(place.name)
    if not place_key:
        return None
    for candidate in candidates:
        candidate_key = normalize_place_key(candidate.name)
        if not candidate_key:
            continue
        if place_key in candidate_key or candidate_key in place_key:
            return candidate
    return None


def normalize_place_key(value: str | None) -> str:
    if not value:
        return ""
    return (
        value.lower()
        .replace("(", "")
        .replace(")", "")
        .replace("（", "")
        .replace("）", "")
        .replace(" ", "")
    )


def safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
