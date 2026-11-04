"""Curated practice questions and explicit concepts used by both evaluators."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    prompt: str
    reference: str
    concepts: tuple[tuple[str, ...], ...]


PACKS = {
    "python": [
        Question(
            "What goes wrong with def add_user(name, users=[]), and how would you fix it?",
            "Python evaluates the default list once when the function is defined. The same mutable list is shared across calls. Use users=None and create a new list inside the function when users is None.",
            (("once", "definition", "defined"), ("shared", "same list", "reuse"), ("none",), ("new list", "inside", "users = []"))),
        Question(
            "A FastAPI endpoint calls a slow external API. How would you keep other requests responsive?",
            "Use an async HTTP client and await network I/O. Do not call blocking clients directly in async routes. Set timeouts, limit concurrency, and use a thread pool for blocking work or a worker queue for long jobs.",
            (("async", "await"), ("blocking", "thread"), ("timeout",), ("limit", "semaphore", "queue", "concurrency"))),
        Question(
            "How would you handle timeouts and rate limits from an LLM API in a Python backend?",
            "Set a request timeout, catch specific provider exceptions, retry only transient failures with bounded exponential backoff and jitter, and respect Retry-After when provided. Return a clear retryable error after the limit, without leaking credentials.",
            (("timeout",), ("exception", "catch", "try"), ("backoff", "jitter"), ("bounded", "limit", "retry-after", "retry after"))),
    ],
    "rag": [
        Question(
            "Walk me through a RAG pipeline from documents to a grounded answer.",
            "Split documents into chunks, embed and index the chunks, retrieve relevant passages for the query, and pass those passages as context to the LLM. Cite source passages and decline unsupported answers.",
            (("chunk", "split"), ("embed", "vector"), ("retriev", "similarity"), ("context", "ground", "source"))),
        Question(
            "Your RAG assistant retrieves irrelevant passages. What would you investigate first?",
            "Inspect the actual retrieved chunks and their source metadata on a representative query set. Check chunk size and overlap, embedding model consistency, top-k and metadata filters. Try hybrid search or reranking, and compare retrieval metrics before and after changes.",
            (("chunk", "overlap"), ("embed",), ("top-k", "top k", "filter", "rerank", "hybrid"), ("metric", "evaluat", "recall", "precision"))),
        Question(
            "How would you prevent a RAG assistant from exposing another employee's private documents?",
            "Authenticate the user on the server and enforce document permissions during retrieval with metadata filters. Never rely on a prompt for authorization. Also isolate conversation memory per user and test cross-user access attempts.",
            (("auth", "permission"), ("filter", "metadata"), ("server", "retriev"), ("memory", "isolat", "cross-user"))),
    ],
    "langgraph": [
        Question(
            "What are state, nodes, and edges in LangGraph? Give a small example.",
            "State is the typed data shared through a workflow. Nodes read state and return updates. Edges determine the next node. For example, classify a question, then use a conditional edge to route it to retrieval or a normal response.",
            (("state", "shared"), ("node", "function"), ("edge", "route"), ("conditional", "classif", "example"))),
        Question(
            "When would you use a conditional edge, and how do you prevent an endless agent loop?",
            "Use a conditional edge when the next step depends on state, such as a score or tool result. Route to END when done, cap retries or iterations, and configure a recursion limit as a final safeguard.",
            (("state", "score", "result"), ("conditional", "route", "branch"), ("end", "stop", "terminat"), ("limit", "cap", "max"))),
        Question(
            "How would you preserve separate conversations for multiple LangGraph users across restarts?",
            "Use a persistent checkpointer with an appropriate durable backend and a separate thread ID for each conversation. Associate each thread with the authenticated user, enforce ownership on the server, and avoid shared global memory. Alternatively persist a validated application state between graph runs.",
            (("persist", "checkpoint", "database"), ("thread", "session"), ("user", "ownership", "auth"), ("isolat", "separate", "restart"))),
    ],
}

LABELS = {"python": "Python Backend", "rag": "RAG", "langgraph": "LangGraph"}
