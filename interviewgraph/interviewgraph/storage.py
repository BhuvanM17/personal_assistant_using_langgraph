"""Durable JSON state with optimistic version checks; no pickle/checkpoint deserialization."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as connection, connection:
            connection.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, version INTEGER NOT NULL, state TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def create(self, state: dict):
        identifier = uuid4().hex
        with closing(self.connect()) as connection, connection:
            connection.execute("INSERT INTO sessions VALUES (?, 0, ?)", (identifier, json.dumps(state)))
        return identifier

    def read(self, identifier: str):
        with closing(self.connect()) as connection, connection:
            row = connection.execute("SELECT version, state FROM sessions WHERE id = ?", (identifier,)).fetchone()
        return None if row is None else (row[0], json.loads(row[1]))

    def save(self, identifier: str, expected_version: int, state: dict):
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute("UPDATE sessions SET version = version + 1, state = ? WHERE id = ? AND version = ?",
                                        (json.dumps(state), identifier, expected_version))
        return cursor.rowcount == 1
