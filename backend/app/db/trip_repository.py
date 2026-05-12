from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from app.models.trip import TripOutput


class TripRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create_trip(self, trip: TripOutput) -> TripOutput:
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """
            INSERT INTO trips (id, title, input_json, output_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                trip.id,
                trip.title,
                json.dumps(trip.input.model_dump(mode="json")),
                json.dumps(trip.model_dump(mode="json")),
                now,
                now,
            ),
        )
        self.conn.commit()
        return trip

    def get_trip(self, trip_id: str) -> TripOutput | None:
        row = self.conn.execute("SELECT output_json FROM trips WHERE id = ?", (trip_id,)).fetchone()
        if row is None:
            return None
        return TripOutput.model_validate(json.loads(row["output_json"]))

    def list_trips(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT id, title, created_at FROM trips ORDER BY created_at DESC"
        ).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def delete_trip(self, trip_id: str) -> bool:
        cursor = self.conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        self.conn.commit()
        return cursor.rowcount > 0