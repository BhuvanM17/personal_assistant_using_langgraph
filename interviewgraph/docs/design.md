# InterviewGraph

A small interview coach that demonstrates real LangGraph state, conditional routing,
LangChain structured output, and a human answering between graph runs.

## Choices
FastAPI serves a plain HTML/CSS/JavaScript interface. SQLite stores each interview's
serialized graph state. A question bank keeps the project understandable; Gemini
evaluates answers against explicit reference points rather than inventing questions.
A visibly labeled demo evaluator checks keyword coverage without claiming AI judgment.

The graph evaluates an answer, then either asks one targeted follow-up (score below 7),
advances to the next question, or finishes. At most one follow-up per question prevents
unbounded loops. The browser shows the executed node trace, feedback, and past answers.
Sessions are isolated by random IDs and survive restarts. A version number prevents
double submissions from advancing a session twice.

Scope: Python, RAG, and LangGraph question packs; 3 questions per session; scores,
feedback, retry/follow-up, report download, and optional Gemini mode. The local server
binds to loopback. No public hosting, user accounts, voice, or payment integration.
Student answers are untrusted data in the model prompt. API keys remain server-side.

Delivery: a self-contained `interviewgraph/` folder in the user's existing public
LangGraph repository, on a separate branch. The GitHub connector cannot create repos.
Project and implementation choices are delegated by the user's request.
