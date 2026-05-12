from __future__ import annotations

from datetime import date

from app.db.database import get_database
from app.db.trip_repository import TripRepository
from app.models.trip import CompanionType, TripInput, TripOutput


def test_list_trips_returns_full_trip_outputs(tmp_path) -> None:
    conn = get_database(tmp_path / "weekendgo.sqlite3")
    repository = TripRepository(conn)
    trip = TripOutput.model_validate(
        {
            "title": "杭州周末游",
            "input": TripInput(
                city="杭州",
                date=date(2026, 5, 16),
                days=2,
                interests=["美食"],
                companions=CompanionType.solo,
            ).model_dump(mode="json"),
            "items": [
                {
                    "start_time": "09:00",
                    "end_time": "11:00",
                    "activity": "西湖游览",
                    "place": {"name": "西湖"},
                    "estimated_cost": 0,
                }
            ],
            "weather_summary": {"summary": "晴"},
        }
    )

    repository.create_trip(trip)
    trips = repository.list_trips()
    conn.close()

    assert len(trips) == 1
    assert isinstance(trips[0], TripOutput)
    assert trips[0].input.city == "杭州"
    assert trips[0].items[0].activity == "西湖游览"
