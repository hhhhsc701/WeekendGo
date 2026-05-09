from __future__ import annotations

from datetime import datetime
import json
import sqlite3
from typing import Any
from uuid import uuid4

from app.models.trip import TripInput, TripOutput


class TripRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_trip(self, trip: TripOutput) -> TripOutput:
        now = datetime.utcnow().isoformat()
        self.connection.execute(
            """
            INSERT INTO trips (id, input_json, output_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                trip.id,
                trip.input.model_dump_json(),
                trip.model_dump_json(),
                trip.created_at.isoformat(),
                now,
            ),
        )
        self.connection.commit()
        return trip

    def get_trip(self, trip_id: str) -> TripOutput | None:
        row = self.connection.execute(
            "SELECT output_json FROM trips WHERE id = ?",
            (trip_id,),
        ).fetchone()
        if row is None:
            return None
        return TripOutput.model_validate_json(row["output_json"])

    def list_trips(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT id, input_json, created_at, updated_at
            FROM trips
            ORDER BY created_at DESC
            """
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            trip_input = TripInput.model_validate_json(row["input_json"])
            result.append(
                {
                    "id": row["id"],
                    "city": trip_input.city,
                    "date": trip_input.date.isoformat(),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "summary": f"{trip_input.city} {trip_input.date.isoformat()}",
                }
            )
        return result

    def update_trip(self, trip_id: str, trip: TripOutput) -> TripOutput | None:
        now = datetime.utcnow().isoformat()
        cursor = self.connection.execute(
            """
            UPDATE trips
            SET input_json = ?, output_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (trip.input.model_dump_json(), trip.model_dump_json(), now, trip_id),
        )
        self.connection.commit()
        if cursor.rowcount == 0:
            return None
        return trip

    def delete_trip(self, trip_id: str) -> bool:
        cursor = self.connection.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        self.connection.commit()
        return cursor.rowcount > 0

    def create_adjustment(
        self,
        *,
        trip_id: str,
        request_text: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        record = {
            "id": str(uuid4()),
            "trip_id": trip_id,
            "request_text": request_text,
            "result": result,
            "created_at": datetime.utcnow().isoformat(),
        }
        self.connection.execute(
            """
            INSERT INTO trip_adjustments (id, trip_id, request_text, result_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                trip_id,
                request_text,
                json.dumps(result, ensure_ascii=False),
                record["created_at"],
            ),
        )
        self.connection.commit()
        return record

    def list_adjustments(self, trip_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT id, trip_id, request_text, result_json, created_at
            FROM trip_adjustments
            WHERE trip_id = ?
            ORDER BY created_at ASC
            """,
            (trip_id,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "trip_id": row["trip_id"],
                "request_text": row["request_text"],
                "result": json.loads(row["result_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
