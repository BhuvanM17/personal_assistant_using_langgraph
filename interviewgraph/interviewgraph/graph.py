"""A real compiled StateGraph; the human responds between graph invocations."""
from datetime import datetime, timezone
from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph

from .evaluators import Evaluator, Review
from .questions import PACKS


class CoachState(TypedDict):
    topic: str
    index: int
    attempt: int
    prompt: str
    answer: str
    review: dict | None
    history: list[dict]
    trace: list[str]
    finished: bool
    mode: str


def initial_state(topic: str, mode: str = "demo") -> CoachState:
    return {"topic": topic, "index": 0, "attempt": 0, "prompt": PACKS[topic][0].prompt,
            "answer": "", "review": None, "history": [], "trace": [], "finished": False, "mode": mode}


def build_graph(evaluator: Evaluator):
    def evaluate(state: CoachState):
        question = PACKS[state["topic"]][state["index"]]
        review = Review.model_validate(evaluator.evaluate(question, state["answer"]))
        entry = {"question_number": state["index"] + 1, "attempt": state["attempt"] + 1,
                 "question": state["prompt"], "answer": state["answer"], **review.model_dump(),
                 "reference": question.reference, "mode": evaluator.mode,
                 "timestamp": datetime.now(timezone.utc).isoformat()}
        return {"review": review.model_dump(), "history": [*state["history"], entry],
                "trace": ["evaluate"], "answer": ""}

    def route(state: CoachState):
        if state["review"]["score"] < 7 and state["attempt"] == 0:
            return "follow_up"
        return "finish" if state["index"] + 1 == len(PACKS[state["topic"]]) else "advance"

    def follow_up(state: CoachState):
        gaps = state["review"]["gaps"]
        focus = "; ".join(gaps[:2]) if gaps else "give a clearer explanation and one concrete example"
        return {"attempt": 1, "prompt": PACKS[state["topic"]][state["index"]].prompt +
                "\n\nFollow-up: try the full answer again, focusing on: " + focus,
                "trace": [*state["trace"], "follow_up"]}

    def advance(state: CoachState):
        next_index = state["index"] + 1
        return {"index": next_index, "attempt": 0, "prompt": PACKS[state["topic"]][next_index].prompt,
                "trace": [*state["trace"], "advance"]}

    def finish(state: CoachState):
        return {"finished": True, "prompt": "", "trace": [*state["trace"], "finish"]}

    builder = StateGraph(CoachState)
    for name, node in [("evaluate", evaluate), ("follow_up", follow_up), ("advance", advance), ("finish", finish)]:
        builder.add_node(name, node)
    builder.add_edge(START, "evaluate")
    builder.add_conditional_edges("evaluate", route,
                                  {"follow_up": "follow_up", "advance": "advance", "finish": "finish"})
    for name in ["follow_up", "advance", "finish"]:
        builder.add_edge(name, END)
    return builder.compile()
