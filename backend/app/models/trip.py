from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class CompanionType(StrEnum):
    solo = "solo"
    couple = "couple"
    family = "family"
    friends = "friends"


class Coordinates(BaseModel):
    lat: float
    lng: float

    @model_validator(mode="before")
    @classmethod
    def coerce_coordinates(cls, value: Any) -> Any:
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            if len(parts) >= 2:
                return {"lng": parts[0], "lat": parts[1]}
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return {"lng": value[0], "lat": value[1]}
        if isinstance(value, dict):
            coordinates = dict(value)
            if "lat" not in coordinates and "latitude" in coordinates:
                coordinates["lat"] = coordinates["latitude"]
            if "lng" not in coordinates:
                if "longitude" in coordinates:
                    coordinates["lng"] = coordinates["longitude"]
                elif "lon" in coordinates:
                    coordinates["lng"] = coordinates["lon"]
            return coordinates
        return value


class Place(BaseModel):
    name: str
    address: str | None = None
    coordinates: Coordinates | None = None
    rating: float | None = None
    category: str | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_place(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"name": value}
        if isinstance(value, dict):
            place = dict(value)
            coordinates = place.get("coordinates")
            if coordinates is None and isinstance(place.get("location"), str):
                place["coordinates"] = place["location"]
            return place
        return value


class WeatherSummary(BaseModel):
    summary: str = "天气数据不可用"
    temperature_c: float | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_weather(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"summary": value}
        return value


class TransportDetail(BaseModel):
    mode: str | None = None
    code: str | None = None
    departure: str | None = None
    arrival: str | None = None
    departure_coordinates: Coordinates | None = None
    arrival_coordinates: Coordinates | None = None
    departure_time: str | None = None
    arrival_time: str | None = None
    duration: str | None = None
    cost: float | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_transport_detail(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"code": value}
        if not isinstance(value, dict):
            return value

        detail = dict(value)
        detail.setdefault("code", detail.get("train_number") or detail.get("flight_number") or detail.get("number"))
        detail.setdefault("departure", detail.get("from") or detail.get("from_station") or detail.get("departure_station"))
        detail.setdefault("arrival", detail.get("to") or detail.get("to_station") or detail.get("arrival_station"))
        detail.setdefault(
            "departure_coordinates",
            detail.get("from_coordinates")
            or detail.get("departure_location")
            or detail.get("from_location"),
        )
        detail.setdefault(
            "arrival_coordinates",
            detail.get("to_coordinates")
            or detail.get("arrival_location")
            or detail.get("to_location"),
        )
        detail.setdefault("departure_time", detail.get("depart_time") or detail.get("start_time"))
        detail.setdefault("arrival_time", detail.get("arrive_time") or detail.get("end_time"))
        detail.setdefault("cost", detail.get("price") or detail.get("fare"))
        return detail


class TripItem(BaseModel):
    start_time: str
    end_time: str
    activity: str
    place: Place
    estimated_cost: float | None = None
    transport: str | None = None
    transport_detail: TransportDetail | None = None
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_llm_item(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        item = dict(value)

        time_value = item.get("time") or item.get("time_range")
        if time_value and ("start_time" not in item or "end_time" not in item):
            normalized = str(time_value).replace("—", "-").replace("–", "-")
            if "-" in normalized:
                parts = normalized.split("-", 1)
                item.setdefault("start_time", parts[0].strip())
                item.setdefault("end_time", parts[1].strip() if len(parts) > 1 else parts[0].strip())

        item.setdefault("start_time", item.get("start") or "09:00")
        item.setdefault("end_time", item.get("end") or item["start_time"])
        item.setdefault("activity", item.get("description") or item.get("title") or "活动")

        if "place" not in item:
            item["place"] = item.get("location") or item.get("venue") or "地点"
        if "transport_detail" not in item:
            item["transport_detail"] = item.get("train") or item.get("flight") or item.get("traffic")

        return item


class TripInput(BaseModel):
    city: str = Field(min_length=1)
    date: date
    days: int = Field(default=1, ge=1, le=14)
    budget: float | None = Field(default=None, ge=0)
    interests: list[str] = Field(min_length=1)
    companions: CompanionType
    departure_city: str | None = None
    departure_coordinates: Coordinates | None = None
    notes: str | None = None


class TripOutput(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    input: TripInput
    region: str = "domestic"
    items: list[TripItem] = Field(default_factory=list)
    weather_summary: WeatherSummary = Field(default_factory=WeatherSummary)
    total_budget: float | None = None
    notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="before")
    @classmethod
    def coerce_llm_output(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        output = dict(value)

        if isinstance(output.get("notes"), str):
            output["notes"] = [output["notes"]]
        if "total_budget" not in output:
            output["total_budget"] = output.get("total_cost") or output.get("budget")
        if "input" not in output:
            output["input"] = {}
        if "region" not in output:
            output["region"] = "domestic"

        return output
