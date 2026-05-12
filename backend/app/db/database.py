import sqlite3
from pathlib import Path


def get_database(db_path: str | Path = "data/weekendgo.sqlite3") -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _init_tables(conn)
    return conn


def initialize_database(db_path: str | Path = "data/weekendgo.sqlite3") -> None:
    """Initialize database with tables. Used by init_db script."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    _init_tables(conn)
    conn.close()


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            input_json TEXT NOT NULL,
            output_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
    """)
    conn.commit()