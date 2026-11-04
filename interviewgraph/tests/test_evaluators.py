from interviewgraph.evaluators import GeminiEvaluator, Review


def test_gemini_fallback_key_is_forwarded(monkeypatch):
    import langchain_google_genai

    captured = {}

    class FakeChatModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def with_structured_output(self, schema):
            assert schema is Review
            return self

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test-only")
    monkeypatch.setattr(langchain_google_genai, "ChatGoogleGenerativeAI", FakeChatModel)
    GeminiEvaluator()
    assert captured["google_api_key"] == "fake-key-for-test-only"
