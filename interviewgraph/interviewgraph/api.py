"""FastAPI endpoints for one local operator; sync routes run provider calls in a thread pool."""
import logging
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .evaluators import Evaluator, configured_evaluator
from .graph import build_graph, initial_state
from .questions import LABELS, PACKS
from .storage import Store

STATIC = Path(__file__).parent / "static"
logger = logging.getLogger(__name__)


class StartRequest(BaseModel):
    topic: Literal["python", "rag", "langgraph"]


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)
    version: int = Field(ge=0, strict=True)

    @field_validator("answer")
    @classmethod
    def strip_answer(cls, value: str):
        if not value.strip():
            raise ValueError("Write an answer before submitting.")
        return value.strip()


def public_session(identifier, version, state):
    latest = {entry["question_number"]: entry["score"] for entry in state["history"]}
    average = round(sum(latest.values()) / len(latest), 1) if latest else None
    return {"id": identifier, "version": version, "topic": state["topic"], "topic_label": LABELS[state["topic"]],
            "mode": state["mode"], "question": None if state["finished"] else state["prompt"],
            "question_number": state["index"] + 1, "total_questions": len(PACKS[state["topic"]]),
            "attempt": state["attempt"], "review": state["review"], "history": state["history"],
            "trace": state["trace"], "finished": state["finished"], "average_score": average}


def create_app(database: str | Path | None = None, evaluator: Evaluator | None = None):
    load_dotenv(override=False)
    evaluator = evaluator or configured_evaluator()
    store = Store(database or os.getenv("INTERVIEW_DB", "interviews.sqlite3"))
    graph = build_graph(evaluator)
    app = FastAPI(title="InterviewGraph", version="1.0.0")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    def get_session(identifier):
        stored = store.read(identifier)
        if stored is None:
            raise HTTPException(404, "Interview not found. Start a new session.")
        return stored

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/config")
    def config():
        return {"mode": evaluator.mode, "topics": LABELS}

    @app.post("/api/sessions", status_code=201)
    def start_session(request: StartRequest):
        state = initial_state(request.topic, evaluator.mode)
        identifier = store.create(state)
        return public_session(identifier, 0, state)

    @app.get("/api/sessions/{identifier}")
    def read_session(identifier: str):
        version, state = get_session(identifier)
        return public_session(identifier, version, state)

    @app.post("/api/sessions/{identifier}/answers")
    def submit_answer(identifier: str, request: AnswerRequest):
        version, state = get_session(identifier)
        if state["finished"]:
            raise HTTPException(409, "This interview is complete. Start a new session.")
        if request.version != version:
            raise HTTPException(409, "This answer was already submitted. Reload the session.")
        if state["mode"] != evaluator.mode:
            raise HTTPException(409, "The evaluation mode changed. Start a new interview.")
        try:
            updated = graph.invoke(state | {"answer": request.answer}, {"recursion_limit": 8})
        except Exception:
            # Do not log provider messages: they can contain credentials or candidate answers.
            logger.warning("Interview evaluator failed; session was not advanced.")
            raise HTTPException(503, "Feedback is unavailable right now. Your answer has not been recorded; please retry.") from None
        if not store.save(identifier, version, updated):
            raise HTTPException(409, "Another submission completed first. Reload the session.")
        return public_session(identifier, version + 1, updated)

    @app.get("/api/sessions/{identifier}/report")
    def report(identifier: str):
        version, state = get_session(identifier)
        session = public_session(identifier, version, state)
        lines = ["INTERVIEWGRAPH PRACTICE REPORT", f"Topic: {session['topic_label']}",
                 f"Mode: {'Demo (keyword coverage, not AI grading)' if state['mode'] == 'demo' else 'Gemini AI feedback'}",
                 f"Status: {'Complete' if state['finished'] else 'In progress'}",
                 f"Average latest-attempt score: {session['average_score'] if session['average_score'] is not None else 'Not scored'}/10", ""]
        for entry in state["history"]:
            lines += [f"Question {entry['question_number']} / attempt {entry['attempt']}", entry["question"],
                      f"Your answer: {entry['answer']}", f"Score: {entry['score']}/10", entry["feedback"],
                      "Strengths: " + "; ".join(entry["strengths"]), "Improve: " + "; ".join(entry["gaps"]),
                      "Reference answer: " + entry["reference"], ""]
        return Response("\n".join(lines), media_type="text/plain",
                        headers={"Content-Disposition": 'attachment; filename="interviewgraph-report.txt"'})

    return app
