from __future__ import annotations

from pathlib import Path

WS_URL = "ws://localhost:8765"
DEFAULT_ROOT = Path(__file__).resolve().parent.parent

TUI_CSS = """
#chat-log { height: 1fr; padding: 1 2; }
#status { dock: bottom; height: 1; color: #888888; padding: 0 2; }
Input { dock: bottom; }
.user { text-align: right; margin: 1 0 0 8; background: $primary-darken-2; padding: 1 2; }
.loop { color: #5cabff; margin: 1 0 0 0; }
.tool { color: #f5c242; margin: 0 0 0 2; }
.result { color: #aaaaaa; margin: 0 0 0 2; }
.final { background: $success-darken-2; margin: 1 4 0 0; padding: 1 2; }
.error { background: $error-darken-2; margin: 1 4; padding: 1 2; }
"""
