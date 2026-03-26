from manuclaw import ManuclawApp


class FakeStatus:
    def __init__(self):
        self.value = ""

    def update(self, value):
        self.value = value


def test_handle_gateway_event_renders_lines(monkeypatch):
    app = ManuclawApp()
    mounted = []
    status = FakeStatus()

    monkeypatch.setattr(
        app, "_mount_text", lambda text, css: mounted.append((text, css))
    )
    monkeypatch.setattr(app, "query_one", lambda selector, *_args, **_kwargs: status)

    app.handle_gateway_event(
        {
            "type": "loop_update",
            "conversation_id": "conv-1",
            "iteration": 2,
            "payload": {"status": "running"},
            "stop_reason": "tool_use",
        }
    )
    app.handle_gateway_event(
        {
            "type": "tool_start",
            "conversation_id": "conv-1",
            "iteration": 2,
            "payload": {"tool_name": "youtube_detect", "input": {"text": "x"}},
            "stop_reason": "tool_use",
        }
    )
    app.handle_gateway_event(
        {
            "type": "tool_result",
            "conversation_id": "conv-1",
            "iteration": 2,
            "payload": {"tool_name": "youtube_detect", "result": {"ok": True}},
            "stop_reason": "tool_use",
        }
    )
    app.handle_gateway_event(
        {
            "type": "final_response",
            "conversation_id": "conv-1",
            "iteration": 3,
            "payload": {"content": "done"},
            "stop_reason": "end_turn",
        }
    )

    assert any("Loop #2" in text for text, _ in mounted)
    assert any("LLM chose" in text for text, _ in mounted)
    assert any("Result:" in text for text, _ in mounted)
    assert any("done" in text for text, _ in mounted)
    assert "final_response" in status.value
