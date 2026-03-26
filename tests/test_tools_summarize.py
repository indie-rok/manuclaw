import asyncio

from tools import summarize as summarize_mod


def test_summarize_missing_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = asyncio.run(summarize_mod.summarize("hello"))
    assert result["ok"] is False
    assert "OPENROUTER_KEY" in result["error"]


def test_summarize_success(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "- one\n- two"}}]}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers=None, json=None):
            assert isinstance(json, dict)
            assert "messages" in json
            return FakeResponse()

    monkeypatch.setenv("OPENROUTER_KEY", "test")
    monkeypatch.setattr(
        summarize_mod.httpx, "AsyncClient", lambda timeout: FakeClient()
    )
    result = asyncio.run(summarize_mod.summarize("some transcript"))
    assert result["ok"] is True
    assert "summary" in result["data"]
