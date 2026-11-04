import sqlite3

import pytest

from interviewgraph.graph import initial_state
from interviewgraph.storage import Store


def test_database_connections_are_closed(tmp_path, monkeypatch):
    connections = []
    original_connect = sqlite3.connect

    def track_connection(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", track_connection)
    store = Store(tmp_path / "store.sqlite3")
    identifier = store.create(initial_state("python"))
    version, state = store.read(identifier)
    assert store.save(identifier, version, state)
    assert len(connections) == 4
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


def test_optimistic_save_does_not_overwrite_newer_answer(tmp_path):
    store = Store(tmp_path / "store.sqlite3")
    state = initial_state("python")
    identifier = store.create(state)
    first = state | {"prompt": "First answer was accepted"}
    second = state | {"prompt": "Stale answer must not overwrite this"}
    assert store.save(identifier, 0, first)
    assert not store.save(identifier, 0, second)
    assert store.read(identifier) == (1, first)


def test_session_identifiers_and_states_are_separate(tmp_path):
    store = Store(tmp_path / "store.sqlite3")
    one = store.create(initial_state("python"))
    two = store.create(initial_state("rag"))
    assert one != two and len(one) == 32
    assert store.read(one)[1]["topic"] == "python"
    assert store.read(two)[1]["topic"] == "rag"
    assert store.read("unknown") is None
