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

    .agent-message {
        text-align: left;
        background: $success-darken-2;
        color: $text;
        margin: 1 8 0 0;
        padding: 1 2;
    }

    .error-message {
        text-align: center;
        background: $error-darken-2;
        color: $text;
        margin: 1 4;
        padding: 1 2;
    }

    Input {
        dock: bottom;
    }
    """

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="chat-log")
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
        try:
            async with websockets.connect(WS_URL) as ws:
                await ws.send(message)
                response = await ws.recv()
            chat_log.loading = False
            chat_log.mount(Static(f"manuclaw: {response}", classes="agent-message"))
            chat_log.scroll_end(animate=False)
        except Exception:
            chat_log.loading = False
            chat_log.mount(
                Static(
                    f"[Error] Cannot connect to gateway at {WS_URL}",
                    classes="error-message",
                )
            )
            chat_log.scroll_end(animate=False)


if __name__ == "__main__":
    ManuclawApp().run()
