from collections.abc import Iterator
from pathlib import Path
import sqlite3

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(database_path: Path | str) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: Path | str) -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(database_path) as connection:
        connection.executescript(schema)


def get_connection(database_path: Path | str) -> Iterator[sqlite3.Connection]:
    connection = connect(database_path)
    try:
        yield connection
    finally:
        connection.close()
