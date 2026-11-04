# InterviewGraph implementation plan

1. Write integration tests covering the actual compiled graph, both routing branches,
   bounded follow-ups, report download, validation, provider failure, and session isolation.
2. Implement curated question packs, typed review output, demo/Gemini evaluators,
   graph nodes, SQLite state storage, and FastAPI endpoints.
3. Add a responsive dashboard with question/answer flow, feedback, progress, visible
   graph trace, and downloadable reports. Keep provider mode explicit throughout.
4. Run tests in an isolated virtual environment with current dependencies; verify
   live HTTP/static responses and JavaScript syntax; review code independently.
5. Upload exact checked sources through the GitHub plugin, open a PR, and verify files.

Review focus: double submissions, model timeouts/invalid output, follow-up termination,
HTML injection in answers, and no API key or local session data in source control.
