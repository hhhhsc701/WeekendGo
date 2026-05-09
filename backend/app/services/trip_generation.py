from __future__ import annotations

import logging
from typing import Any

from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.mcp.client import MCPClientManager
from app.mcp.errors import MCPToolError
from app.mcp.region import Region, RegionRouter, is_chinese_city
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
            return await self.llm.generate_trip_json(context.model_dump(mode="json"), TripOutput)
        except LLMError:
            logger.exception("LLM trip generation failed")
            raise

    async def _locate_city(self, city: str, region: Region) -> Coordinates:
        if region == "domestic":
            result = await self.mcp.call("domestic", "geocode", {"address": city})
        else:
            result = await self.mcp.call("international", "search_location", {"query": city})
        coordinates = extract_coordinates(result)
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
        return value
    if hasattr(value, "content"):
        return {"content": getattr(value, "content")}
    return {"value": value}


def extract_list(value: Any) -> list[dict[str, Any]]:
    payload = normalize_mapping(value)
    for key in ("items", "pois", "results", "data", "trains"):
        items = payload.get(key)
        if isinstance(items, list):
            return [normalize_mapping(item) for item in items]
    if isinstance(value, list):
        return [normalize_mapping(item) for item in value]
    return []


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
    temperature = payload.get("temperature") or payload.get("temperature_c") or payload.get("temp")
    rain_probability = payload.get("rain_probability") or payload.get("precipitation_probability")
    summary = (
        payload.get("summary")
        or payload.get("weather")
        or payload.get("condition")
        or payload.get("text")
        or "Weather data available"
    )
    return WeatherSummary(
        summary=str(summary),
        temperature_c=safe_float(temperature),
        rain_probability=safe_float(rain_probability),
        raw=payload,
    )


def safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
