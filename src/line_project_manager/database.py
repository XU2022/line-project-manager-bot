"""SQLite setup helpers with no LINE or business-specific dependencies."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Iterator


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self, schema_path: str | Path) -> None:
        schema = Path(schema_path).read_text(encoding="utf-8")
        with self.session() as connection:
            connection.executescript(schema)

    def initialize_default(self) -> None:
        schema = files("line_project_manager").joinpath("schema.sql").read_text(
            encoding="utf-8"
        )
        with self.session() as connection:
            connection.executescript(schema)
