from datetime import date

from app.models.trip import CompanionType, TripInput, TripOutput


def test_trip_output_accepts_common_llm_field_variants() -> None:
    trip_input = TripInput(
        city="上海",
        date=date(2026, 5, 16),
        interests=["food"],
        companions=CompanionType.friends,
    )

    output = TripOutput.model_validate(
        {
            "title": "上海周末",
            "input": trip_input.model_dump(mode="json"),
            "region": "domestic",
            "weather_summary": "天气适宜",
            "transportation": "地铁",
            "total_cost": 300,
            "notes": "建议提前预约",
            "items": [
                {
                    "time": "09:30-11:30",
                    "location": "上海博物馆",
                    "description": "看展",
                    "cost": 0,
                    "transportation": "地铁",
                }
            ],
        }
    )

    assert output.items[0].start_time == "09:30"
    assert output.items[0].end_time == "11:30"
    assert output.items[0].place.name == "上海博物馆"
    assert output.weather_summary.summary == "天气适宜"
    assert output.transportation.summary == "地铁"
    assert output.notes == ["建议提前预约"]
