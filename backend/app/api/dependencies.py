from __future__ import annotations

from collections.abc import Iterator
import sqlite3

from fastapi import Depends

from app.core.settings import Settings, get_settings
from app.db.database import connect, initialize_database
from app.db.trip_repository import TripRepository


def get_db_connection(settings: Settings = Depends(get_settings)) -> Iterator[sqlite3.Connection]:
    initialize_database(settings.database_path)
    connection = connect(settings.database_path)
    try:
        yield connection
    finally:
        connection.close()


def get_trip_repository(
    connection: sqlite3.Connection = Depends(get_db_connection),
) -> TripRepository:
    return TripRepository(connection)
