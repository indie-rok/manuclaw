import asyncio
import json

from gateway import index as gateway


class FakeWebSocket:
    def __init__(self, incoming):
        self._incoming = incoming
        self.sent = []

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._incoming:
            raise StopAsyncIteration
        return self._incoming.pop(0)

    async def send(self, data):
        self.sent.append(data)


def test_websocket_event_order(monkeypatch):
    async def fake_llm(history, tools):
        if len(history) == 1:
            return {
                "role": "assistant",
                "content": "",
                "stop_reason": "tool_use",
                "tool_calls": [
                    {
                        "id": "a1",
                        "name": "youtube_detect",
                        "input": {"text": "https://youtu.be/dQw4w9WgXcQ"},
                    }
                ],
            }
        return {
            "role": "assistant",
            "content": "all set",
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

    ws = FakeWebSocket(["summarize this"])
    asyncio.run(gateway.handler(ws))

    events = [json.loads(raw) for raw in ws.sent]
    assert events[0]["type"] == "user_input"

    loop_index = next(
        i for i, event in enumerate(events) if event["type"] == "loop_update"
    )
    tool_start_index = next(
        i for i, event in enumerate(events) if event["type"] == "tool_start"
    )
    tool_result_index = next(
        i for i, event in enumerate(events) if event["type"] == "tool_result"
    )
    final_index = next(
        i for i, event in enumerate(events) if event["type"] == "final_response"
    )

    assert loop_index < tool_start_index < tool_result_index < final_index
