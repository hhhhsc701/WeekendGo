from __future__ import annotations

from datetime import date

import pytest

from app.db.database import connect, initialize_database
from app.db.trip_repository import TripRepository
from app.models.trip import CompanionType, RefinementIntent, TripInput, TripOutput
from app.services.trip_refinement import TripRefinementService


class FakeRefinementLLM:
    async def parse_refinement_json(self, original_trip: dict, request_text: str, output_model):
        trip = TripOutput.model_validate(original_trip)
        trip.items[0].start_time = "09:00"
        return output_model(intent="time_adjustment", updated_trip=trip)


def make_trip() -> TripOutput:
    trip_input = TripInput(
        city="Shanghai",
        date=date(2026, 5, 16),
        interests=["food"],
        companions=CompanionType.couple,
    )
    return TripOutput(
        title="Shanghai weekend",
        input=trip_input,
        region="domestic",
        items=[
            {
                "start_time": "14:00",
                "end_time": "16:00",
                "activity": "Coffee",
                "place": {"name": "Cafe"},
            }
        ],
    )


def test_trip_crud_roundtrip(tmp_path) -> None:
    db_path = tmp_path / "weekendgo.sqlite3"
    initialize_database(db_path)
    with connect(db_path) as connection:
        repository = TripRepository(connection)
        trip = repository.create_trip(make_trip())

        assert repository.get_trip(trip.id) is not None
        assert len(repository.list_trips()) == 1
        trip.title = "Updated"
        assert repository.update_trip(trip.id, trip).title == "Updated"  # type: ignore[union-attr]
        assert repository.delete_trip(trip.id) is True
        assert repository.get_trip(trip.id) is None


@pytest.mark.asyncio
async def test_refinement_updates_trip_and_history(tmp_path) -> None:
    db_path = tmp_path / "weekendgo.sqlite3"
    initialize_database(db_path)
    with connect(db_path) as connection:
        repository = TripRepository(connection)
        trip = repository.create_trip(make_trip())
        service = TripRefinementService(llm_client=FakeRefinementLLM(), repository=repository)  # type: ignore[arg-type]

        result = await service.refine(trip.id, "Move it to morning")

        assert isinstance(result.intent, RefinementIntent)
        assert repository.get_trip(trip.id).items[0].start_time == "09:00"  # type: ignore[union-attr]
        assert len(repository.list_adjustments(trip.id)) == 1
