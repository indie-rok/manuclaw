from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import websockets

textual_root = __import__("textual", fromlist=["work"])
textual_app_module = __import__("textual.app", fromlist=["App", "ComposeResult"])
textual_containers_module = __import__(
    "textual.containers", fromlist=["VerticalScroll"]
)
textual_widgets_module = __import__("textual.widgets", fromlist=["Input", "Static"])

work = textual_root.work
App = textual_app_module.App
ComposeResult = textual_app_module.ComposeResult
VerticalScroll = textual_containers_module.VerticalScroll
Input = textual_widgets_module.Input
Static = textual_widgets_module.Static

from memory.index import Memory
from ui.constants import DEFAULT_ROOT, TUI_CSS, WS_URL
from ui.replay import history_rows_to_events


class BaseManuclawApp(App[None]):
    TITLE = "manuclaw"
    AUTO_FOCUS = "Input"
    CSS = TUI_CSS

    def __init__(self, root: Path | None = None) -> None:
        super().__init__()
        self._root = root or DEFAULT_ROOT
        self._seen: set[tuple[str, int, str, str | None]] = set()
        self._current_conversation_id: str | None = None
        self._event_handlers: dict[str, Callable[[dict[str, Any]], None]] = {
            "user_input": self._handle_user_input,
            "loop_update": self._handle_loop_update,
            "tool_start": self._handle_tool_start,
            "tool_result": self._handle_tool_result,
            "final_response": self._handle_final_response,
            "error": self._handle_error,
        }

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="chat-log")
        yield Static(f"{WS_URL} | idle", id="status")
        yield Input(placeholder="Paste a YouTube URL...")

    def _event_key(self, event: dict[str, Any]) -> tuple[str, int, str, str | None]:
        payload = event.get("payload", {})
        tool_name = payload.get("tool_name") if isinstance(payload, dict) else None
        return (
            str(event.get("conversation_id", "")),
            int(event.get("iteration", 0)),
            str(event.get("type", "")),
            tool_name,
        )

    def _mount_text(self, text: str, css_class: str) -> None:
        chat_log = self.query_one("#chat-log", VerticalScroll)
        chat_log.mount(Static(text, classes=css_class))
        chat_log.scroll_end(animate=False)

    def _update_status(self, event: dict[str, Any]) -> None:
        status = self.query_one("#status", Static)
        event_type = event.get("type")
        iteration = event.get("iteration", 0)
        status.update(f"{WS_URL} | {event_type} | loop {iteration}")

    def handle_gateway_event(self, event: dict[str, Any]) -> None:
        key = self._event_key(event)
        if key in self._seen:
            return
        self._seen.add(key)

        conversation_id = str(event.get("conversation_id", ""))
        if conversation_id:
            self._current_conversation_id = conversation_id

        event_type = str(event.get("type", ""))
        handler = self._event_handlers.get(event_type)
        if handler is not None:
            handler(event)
        self._update_status(event)

    def _handle_user_input(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", {})
        text = payload.get("text", "") if isinstance(payload, dict) else ""
        self._mount_text(f"> {text}", "user")

    def _handle_loop_update(self, event: dict[str, Any]) -> None:
        iteration = int(event.get("iteration", 0))
        self._mount_text(f"🔄 Loop #{iteration}", "loop")

    def _handle_tool_start(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        tool_name = payload.get("tool_name")
        tool_input = payload.get("input", {})
        self._mount_text(
            f"  LLM chose: {tool_name} | input: {json.dumps(tool_input)[:80]}",
            "tool",
        )

    def _handle_tool_result(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        self._mount_text(
            f"  Result: {json.dumps(payload.get('result', {}), ensure_ascii=False)[:120]}",
            "result",
        )
        stop_reason = event.get("stop_reason")
        if stop_reason:
            self._mount_text(f"  stop_reason: {stop_reason}", "result")

    def _handle_final_response(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", {})
        content = payload.get("content", "") if isinstance(payload, dict) else ""
        self._mount_text(str(content), "final")
        stop_reason = event.get("stop_reason")
        if stop_reason:
            self._mount_text(f"stop_reason: {stop_reason}", "result")

    def _handle_error(self, event: dict[str, Any]) -> None:
        payload = event.get("payload", {})
        message = (
            payload.get("message", "unknown error")
            if isinstance(payload, dict)
            else "unknown error"
        )
        self._mount_text(str(message), "error")

    def _memory_root(self) -> Path:
        return self._root

    def _rehydrate(self, conversation_id: str) -> None:
        db = Memory(str(self._memory_root() / "manuclaw.db"))
        try:
            events = history_rows_to_events(
                db.get_history(conversation_id), conversation_id
            )
            for event in events:
                self.handle_gateway_event(event)
        finally:
            db.close()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        event.input.clear()
        if message:
            self.send_message(message)

    @work(exclusive=True, exit_on_error=False)
    async def send_message(self, message: str) -> None:
        status = self.query_one("#status", Static)
        try:
            async with websockets.connect(WS_URL) as ws:
                status.update(f"{WS_URL} | connected")
                await ws.send(message)
                async for raw in ws:
                    self.handle_gateway_event(json.loads(raw))
        except Exception as exc:
            if self._current_conversation_id:
                self._rehydrate(self._current_conversation_id)
            self._mount_text(f"connection error: {exc}", "error")
            status.update(f"{WS_URL} | disconnected")
