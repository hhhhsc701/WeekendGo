from __future__ import annotations

from datetime import date

import pytest

from app.models.trip import CompanionType, Coordinates, Place, TripInput
from app.services.trip_generation import TripGenerationService
from app.services.trip_generation import extract_coordinates, normalize_places, normalize_weather


class FakeMCP:
    def __init__(self, *, fail_weather: bool = False, empty_geocode: bool = False) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.fail_weather = fail_weather
        self.empty_geocode = empty_geocode

    async def call(self, region: str, tool_name: str, params: dict):
        self.calls.append((region, tool_name, params))
        if tool_name in {"geocode", "search_location"}:
            if self.empty_geocode:
                return {"geocodes": []}
            return {"lat": 31.2304 if region == "domestic" else 35.6762, "lng": 121.4737 if region == "domestic" else 139.6503}
        if tool_name in {"get_weather", "get_forecast"}:
            if self.fail_weather:
                raise RuntimeError("weather unavailable")
            return {"summary": "sunny", "temperature": 24}
        if tool_name in {"search_poi_around", "maps_search_nearby"}:
            return {
                "items": [
                    {
                        "name": "Great Museum",
                        "address": "Center",
                        "lat": 31.23,
                        "lng": 121.47,
                        "rating": 4.6,
                    },
                    {
                        "name": "Low Rated Cafe",
                        "lat": 31.2,
                        "lng": 121.4,
                        "rating": 3.2,
                    },
                ]
            }
        if tool_name in {"driving_route_planning", "maps_plan_route"}:
            return {"strategy": "optimized"}
        if tool_name == "query_trains":
            return {"trains": [{"train_no": "G1", "price": 553}]}
        raise AssertionError(tool_name)


class FakeLLM:
    async def generate_trip_json(self, context: dict, output_model):
        trip_input = TripInput.model_validate(context["input"])
        return output_model(
            title=f"{trip_input.city} weekend",
            input=trip_input,
            region=context["region"],
            weather_summary=context["weather"],
            transportation=context["transportation"],
            total_budget=trip_input.budget,
            items=[
                {
                    "start_time": "10:00",
                    "end_time": "12:00",
                    "activity": "Visit a museum",
                    "place": context["candidate_places"][0],
                    "estimated_cost": 80,
                    "transport": "walk",
                }
            ],
        )


class SparseLLM:
    async def generate_trip_json(self, context: dict, output_model):
        trip_input = TripInput.model_validate(context["input"])
        return output_model(
            title=f"{trip_input.city} sparse weekend",
            input=trip_input,
            region=context["region"],
            weather_summary="数据获取失败",
            transportation=context["transportation"],
            total_budget=trip_input.budget,
            items=[
                {
                    "start_time": "10:00",
                    "end_time": "12:00",
                    "activity": "Visit a museum",
                    "place": "Great Museum",
                },
                {
                    "start_time": "13:00",
                    "end_time": "14:00",
                    "activity": "Walk around",
                    "place": "Bund",
                },
            ],
        )


def make_input(city: str, departure_city: str | None = None) -> TripInput:
    return TripInput(
        city=city,
        date=date(2026, 5, 16),
        days=1,
        budget=500,
        interests=["culture", "food"],
        companions=CompanionType.friends,
        departure_city=departure_city,
    )


@pytest.mark.asyncio
async def test_domestic_generation_uses_amap_and_train_query() -> None:
    mcp = FakeMCP()
    service = TripGenerationService(mcp_manager=mcp, llm_client=FakeLLM())  # type: ignore[arg-type]

    trip = await service.generate(make_input("上海", "北京"))

    assert trip.region == "domestic"
    assert ("domestic", "geocode") in [(region, tool) for region, tool, _ in mcp.calls]
    assert ("domestic", "search_poi_around") in [(region, tool) for region, tool, _ in mcp.calls]
    assert ("domestic", "query_trains") in [(region, tool) for region, tool, _ in mcp.calls]


@pytest.mark.asyncio
async def test_international_generation_uses_weather_and_google_maps() -> None:
    mcp = FakeMCP()
    service = TripGenerationService(mcp_manager=mcp, llm_client=FakeLLM())  # type: ignore[arg-type]

    trip = await service.generate(make_input("Tokyo"))

    assert trip.region == "international"
    assert ("international", "search_location") in [(region, tool) for region, tool, _ in mcp.calls]
    assert ("international", "maps_search_nearby") in [(region, tool) for region, tool, _ in mcp.calls]


@pytest.mark.asyncio
async def test_weather_failure_degrades() -> None:
    mcp = FakeMCP(fail_weather=True)
    service = TripGenerationService(mcp_manager=mcp, llm_client=FakeLLM())  # type: ignore[arg-type]

    trip = await service.generate(make_input("Shanghai"))

    assert "failed" in trip.weather_summary.summary.lower()


@pytest.mark.asyncio
async def test_english_chinese_city_alias_uses_domestic_route() -> None:
    mcp = FakeMCP()
    service = TripGenerationService(mcp_manager=mcp, llm_client=FakeLLM())  # type: ignore[arg-type]

    trip = await service.generate(make_input("Shanghai"))

    assert trip.region == "domestic"
    assert ("domestic", "geocode") in [(region, tool) for region, tool, _ in mcp.calls]
    assert ("international", "search_location") not in [
        (region, tool) for region, tool, _ in mcp.calls
    ]


@pytest.mark.asyncio
async def test_domestic_city_uses_coordinate_fallback_when_geocode_is_empty() -> None:
    mcp = FakeMCP(empty_geocode=True)
    service = TripGenerationService(mcp_manager=mcp, llm_client=FakeLLM())  # type: ignore[arg-type]

    trip = await service.generate(make_input("上海"))

    assert trip.region == "domestic"
    assert trip.items[0].place.name == "Great Museum"


@pytest.mark.asyncio
async def test_generation_enriches_weather_and_missing_place_coordinates() -> None:
    mcp = FakeMCP()
    service = TripGenerationService(mcp_manager=mcp, llm_client=SparseLLM())  # type: ignore[arg-type]

    trip = await service.generate(make_input("上海"))

    assert trip.weather_summary.summary == "sunny"
    assert trip.items[0].place.coordinates == Coordinates(lat=31.23, lng=121.47)
    assert trip.items[1].place.coordinates == Coordinates(lat=31.2304, lng=121.4737)


def test_poi_filter_removes_low_rated_places() -> None:
    service = TripGenerationService(mcp_manager=FakeMCP(), llm_client=FakeLLM())  # type: ignore[arg-type]
    places = [
        Place(name="Good", rating=4.4, coordinates=Coordinates(lat=1, lng=2)),
        Place(name="Bad", rating=3.5, coordinates=Coordinates(lat=1, lng=3)),
    ]

    assert [place.name for place in service.filter_places(places)] == ["Good"]


def test_extract_coordinates_from_mcp_text_content_geocode_payload() -> None:
    payload = {
        "content": [
            {
                "type": "text",
                "text": '{"return":[{"formatted_address":"上海市","location":"121.473667,31.230525"}]}',
            }
        ]
    }

    coordinates = extract_coordinates(payload)

    assert coordinates == Coordinates(lat=31.230525, lng=121.473667)


def test_normalize_places_from_mcp_text_content_poi_payload() -> None:
    payload = {
        "content": [
            {
                "type": "text",
                "text": '{"pois":[{"name":"上海博物馆","location":"121.4702,31.2288","biz_ext":{"rating":"4.7"}}]}',
            }
        ]
    }

    places = normalize_places(payload, category="museum")

    assert places[0].name == "上海博物馆"
    assert places[0].coordinates == Coordinates(lat=31.2288, lng=121.4702)


def test_normalize_weather_from_amap_live_payload() -> None:
    weather = normalize_weather(
        {
            "status": "1",
            "lives": [
                {
                    "province": "上海",
                    "city": "上海市",
                    "weather": "阴",
                    "temperature": "18",
                    "humidity": "62",
                    "winddirection": "东",
                }
            ],
        }
    )

    assert weather.summary == "上海市: 阴，18°C，湿度 62%，东风"
    assert weather.temperature_c == 18


def test_normalize_weather_from_amap_forecast_payload() -> None:
    weather = normalize_weather(
        {
            "city": "上海市",
            "forecasts": [
                {
                    "date": "2026-05-16",
                    "dayweather": "小雨",
                    "nightweather": "阴",
                    "daytemp": "24",
                    "nighttemp": "19",
                    "daywind": "东",
                }
            ],
        }
    )

    assert weather.summary == "小雨，24°C，东风"
    assert weather.temperature_c == 24
