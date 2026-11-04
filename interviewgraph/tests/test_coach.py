import pytest
from fastapi.testclient import TestClient

from interviewgraph.api import create_app
from interviewgraph.evaluators import DemoEvaluator
from interviewgraph.graph import build_graph, initial_state


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(database=tmp_path / "sessions.sqlite3", evaluator=DemoEvaluator())) as test_client:
        yield test_client


def start(client, topic="python"):
    response = client.post("/api/sessions", json={"topic": topic})
    assert response.status_code == 201
    return response.json()


def answer(client, session, text):
    return client.post(f"/api/sessions/{session['id']}/answers",
                       json={"answer": text, "version": session["version"]})


def test_real_graph_routes_weak_answer_to_follow_up():
    graph = build_graph(DemoEvaluator())
    state = graph.invoke(initial_state("python") | {"answer": "I am unsure"})
    assert state["trace"] == ["evaluate", "follow_up"]
    assert state["index"] == 0 and state["attempt"] == 1
    assert state["review"]["score"] < 7


def test_follow_up_is_bounded():
    graph = build_graph(DemoEvaluator())
    state = graph.invoke(initial_state("python") | {"answer": "Unsure"})
    state = graph.invoke(state | {"answer": "Still unsure"})
    assert state["trace"] == ["evaluate", "advance"]
    assert state["index"] == 1 and state["attempt"] == 0
    assert len(state["history"]) == 2


def test_good_answer_advances_without_follow_up():
    graph = build_graph(DemoEvaluator())
    state = graph.invoke(initial_state("python") | {
        "answer": "A default list is created once and shared between calls. Use None, then create a new list inside the function."})
    assert state["trace"] == ["evaluate", "advance"]
    assert state["review"]["score"] >= 7


def test_session_persists_and_is_isolated(client):
    first, second = start(client), start(client)
    changed = answer(client, first, "I am not sure yet").json()
    assert changed["version"] == 1
    assert client.get(f"/api/sessions/{first['id']}").json()["history"]
    assert client.get(f"/api/sessions/{second['id']}").json()["history"] == []


def test_duplicate_submission_rejected(client):
    session = start(client)
    assert answer(client, session, "I need a hint").status_code == 200
    assert answer(client, session, "I need a hint").status_code == 409


def test_session_finishes_and_report_downloads(client):
    session = start(client, "rag")
    for _ in range(6):
        if session["finished"]:
            break
        response = answer(client, session, "I do not know this answer")
        assert response.status_code == 200
        session = response.json()
    assert session["finished"] is True
    assert session["question"] is None
    assert len(session["history"]) == 6
    report = client.get(f"/api/sessions/{session['id']}/report")
    assert report.status_code == 200
    assert "attachment" in report.headers["content-disposition"]
    assert "RAG" in report.text and "Demo" in report.text
    assert answer(client, session, "Another answer").status_code == 409


@pytest.mark.parametrize("data", [{"topic": "unknown"}, {}, {"topic": 1}])
def test_invalid_topic_rejected(client, data):
    assert client.post("/api/sessions", json=data).status_code == 422


@pytest.mark.parametrize("text", ["", "  ", "x" * 8001])
def test_invalid_answer_rejected(client, text):
    assert answer(client, start(client), text).status_code == 422


def test_missing_session_and_status(client):
    assert client.get("/api/sessions/missing").status_code == 404
    assert client.get("/api/config").json()["mode"] == "demo"
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_provider_failure_does_not_advance_or_leak_details(tmp_path):
    class BrokenEvaluator:
        mode = "gemini"

        def evaluate(self, question, answer):
            raise RuntimeError("secret-key-do-not-leak")

    with TestClient(create_app(database=tmp_path / "failure.sqlite3", evaluator=BrokenEvaluator())) as client:
        session = start(client)
        response = answer(client, session, "Here is my answer")
        assert response.status_code == 503
        assert "secret-key" not in response.text
        unchanged = client.get(f"/api/sessions/{session['id']}").json()
        assert unchanged["version"] == 0 and unchanged["history"] == []


def test_state_survives_app_restart(tmp_path):
    database = tmp_path / "persistent.sqlite3"
    with TestClient(create_app(database=database, evaluator=DemoEvaluator())) as first:
        session = start(first)
        answer(first, session, "I am unsure")
    with TestClient(create_app(database=database, evaluator=DemoEvaluator())) as second:
        assert second.get(f"/api/sessions/{session['id']}").json()["version"] == 1
