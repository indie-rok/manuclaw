import asyncio

from gateway import index as gateway
from memory.index import Memory


def test_agent_loop_single_tool_then_final(monkeypatch, tmp_path):
    calls = {"count": 0}

    async def fake_llm(history, tools):
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "role": "assistant",
                "content": "",
                "stop_reason": "tool_use",
                "tool_calls": [
                    {
                        "id": "t1",
                        "name": "youtube_detect",
                        "input": {"text": "https://youtu.be/dQw4w9WgXcQ"},
                    }
                ],
            }
        return {
            "role": "assistant",
            "content": "done",
            "stop_reason": "end_turn",
            "tool_calls": [],
        }

    monkeypatch.setattr(gateway, "call_llm", fake_llm)
    monkeypatch.setattr(
        gateway,
        "TOOL_HANDLERS",
        {
            "youtube_detect": lambda text: {
                "ok": True,
                "tool_name": "youtube_detect",
                "data": {"video_id": "dQw4w9WgXcQ"},
                "error": None,
            }
        },
    )

    events = []
    db = Memory(str(tmp_path / "db.sqlite3"))
    result = asyncio.run(
        gateway.run_agent_loop(
            "find id", on_event=events.append, memory=db, conversation_id="conv-a"
        )
    )
    db.close()

    assert result["stop_reason"] == "end_turn"
    assert calls["count"] == 2
    event_types = [event["type"] for event in events]
    assert "user_input" in event_types
    assert "loop_update" in event_types
    assert "tool_start" in event_types
    assert "tool_result" in event_types
    assert "final_response" in event_types


def test_agent_loop_unknown_tool(monkeypatch, tmp_path):
    async def fake_llm(history, tools):
        if len(history) == 1:
            return {
                "role": "assistant",
                "content": "",
                "stop_reason": "tool_use",
                "tool_calls": [{"id": "x1", "name": "does_not_exist", "input": {}}],
            }
        return {
            "role": "assistant",
            "content": "failed gracefully",
            "stop_reason": "end_turn",
            "tool_calls": [],
        }

    monkeypatch.setattr(gateway, "call_llm", fake_llm)
    monkeypatch.setattr(gateway, "TOOL_HANDLERS", {})

    events = []
    db = Memory(str(tmp_path / "db.sqlite3"))
    asyncio.run(
        gateway.run_agent_loop(
            "hello", on_event=events.append, memory=db, conversation_id="conv-b"
        )
    )
    db.close()

    tool_results = [event for event in events if event["type"] == "tool_result"]
    assert tool_results
    assert tool_results[0]["payload"]["result"]["ok"] is False
    assert "unknown tool" in tool_results[0]["payload"]["result"]["error"]
