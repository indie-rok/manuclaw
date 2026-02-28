"""manuclaw — TUI conversation interface with WebSocket client."""

import websockets
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Input, Static
from textual import work

WS_URL = "ws://localhost:8765"


class ManuclawApp(App):
    """A Textual TUI chat app that talks to a WebSocket gateway."""

    TITLE = "manuclaw"
    AUTO_FOCUS = "Input"
    CSS = """
    #chat-log {
        height: 1fr;
        padding: 1 2;
    }

    .user-message {
        text-align: right;
        background: $primary-darken-2;
        color: $text;
        margin: 1 0 0 8;
        padding: 1 2;
    }

    .phase-gateway {
        color: #888888;
        margin: 0 0 0 0;
        padding: 0 2;
    }

    .phase-planner {
        color: #5cabff;
        margin: 0 0 0 0;
        padding: 0 2;
    }

    .phase-executor {
        color: #f5c242;
        margin: 0 0 0 0;
        padding: 0 2;
    }

    .phase-memory {
        color: #c678dd;
        margin: 0 0 0 0;
        padding: 0 2;
    }

    .phase-result {
        background: $success-darken-2;
        color: $text;
        margin: 1 4 0 0;
        padding: 1 2;
    }

    .phase-error {
        background: $error-darken-2;
        color: $text;
        margin: 0 4;
        padding: 0 2;
    }

    .error-message {
        text-align: center;
        background: $error-darken-2;
        color: $text;
        margin: 1 4;
        padding: 1 2;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: #888888;
        padding: 0 2;
    }

    Input {
        dock: bottom;
    }
    """

    PHASE_MAP = {
        "GATEWAY": "phase-gateway",
        "PLANNER": "phase-planner",
        "EXECUTOR": "phase-executor",
        "MEMORY": "phase-memory",
        "RESULT": "phase-result",
        "ERROR": "phase-error",
    }

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="chat-log")
        yield Static("ws://localhost:8765 | Idle", id="status-bar")
        yield Input(placeholder="Type a message...")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        if not message:
            return
        event.input.clear()
        chat_log = self.query_one("#chat-log")
        chat_log.mount(Static(f"You: {message}", classes="user-message"))
        chat_log.scroll_end(animate=False)
        chat_log.loading = True
        self.send_message(message)

    @work(exclusive=True, exit_on_error=False)
    async def send_message(self, message: str) -> None:
        chat_log = self.query_one("#chat-log")
        status = self.query_one("#status-bar")
        try:
            status.update("ws://localhost:8765 | Connecting...")
            async with websockets.connect(WS_URL) as ws:
                await ws.send(message)
                chat_log.loading = False
                async for line in ws:
                    if line == "END":
                        status.update("ws://localhost:8765 | Done")
                        break
                    # Parse phase prefix
                    phase_cls = "phase-gateway"
                    text = line
                    if ":" in line:
                        prefix, _, rest = line.partition(":")
                        if prefix in self.PHASE_MAP:
                            phase_cls = self.PHASE_MAP[prefix]
                            text = rest
                            phase_label = prefix.lower()
                            status.update(f"ws://localhost:8765 | {phase_label} | kimi-k2.5")
                    chat_log.mount(Static(text, classes=phase_cls))
                    chat_log.scroll_end(animate=False)
        except Exception:
            chat_log.loading = False
            chat_log.mount(
                Static(
                    f"Cannot connect to gateway at {WS_URL}",
                    classes="error-message",
                )
            )
            chat_log.scroll_end(animate=False)


if __name__ == "__main__":
    ManuclawApp().run()
