from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from app.mcp.region import Region


class CompanionType(StrEnum):
    solo = "solo"
    couple = "couple"
    family = "family"
    friends = "friends"


class TripInput(BaseModel):
    city: str = Field(min_length=1)
    date: date
    days: int = Field(default=1, ge=1, le=14)
    budget: float | None = Field(default=None, ge=0)
    interests: list[str] = Field(min_length=1)
    companions: CompanionType
    departure_city: str | None = None
    notes: str | None = None

    @field_validator("city", "departure_city")
    @classmethod
    def strip_city(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @field_validator("interests")
    @classmethod
    def strip_interests(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("At least one interest is required")
        return cleaned


class Coordinates(BaseModel):
    lat: float
    lng: float


class Place(BaseModel):
    name: str
    address: str | None = None
    coordinates: Coordinates | None = None
    rating: float | None = None
    distance_meters: float | None = None
    category: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class WeatherSummary(BaseModel):
    summary: str = "Weather data unavailable"
    temperature_c: float | None = None
    rain_probability: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class TransportationInfo(BaseModel):
    summary: str = "No cross-city transportation data"
    trains: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class TripItem(BaseModel):
    start_time: str
    end_time: str
    activity: str
    place: Place
    estimated_cost: float | None = None
    transport: str | None = None
    notes: str | None = None


class TripOutput(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    input: TripInput
    region: Region
    items: list[TripItem] = Field(default_factory=list)
    total_budget: float | None = None
    weather_summary: WeatherSummary = Field(default_factory=WeatherSummary)
    transportation: TransportationInfo = Field(default_factory=TransportationInfo)
    notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GenerationContext(BaseModel):
    input: TripInput
    region: Region
    city_coordinates: Coordinates | None = None
    weather: WeatherSummary = Field(default_factory=WeatherSummary)
    candidate_places: list[Place] = Field(default_factory=list)
    route: dict[str, Any] = Field(default_factory=dict)
    transportation: TransportationInfo = Field(default_factory=TransportationInfo)
    notes: list[str] = Field(default_factory=list)


class RefinementIntent(BaseModel):
    intent: str
    needs_clarification: bool = False
    clarification_question: str | None = None
    updated_trip: TripOutput | None = None
    conflicts: list[str] = Field(default_factory=list)
