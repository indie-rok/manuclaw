from __future__ import annotations

from pathlib import Path
from typing import Any

from gateway.index import handler as gateway_handler
from gateway.index import run_agent_loop as gateway_agent_loop
from gateway.index import TOOL_DEFINITIONS as GATEWAY_TOOL_DEFINITIONS
from gateway.index import TOOL_HANDLERS as GATEWAY_TOOL_HANDLERS
from memory.index import Memory
from tools.skill_loader import load_skill
from ui.app import BaseManuclawApp

ROOT = Path(__file__).resolve().parent
SKILLS_DIR = ROOT / "skills"


def build_skill_dictionary() -> dict[str, str]:
    return {path.stem: str(path) for path in sorted(SKILLS_DIR.glob("*.md"))}


SKILL_DICTIONARY = build_skill_dictionary()
TOOL_DICTIONARY = dict(GATEWAY_TOOL_HANDLERS)
TOOL_SCHEMA_LIST = list(GATEWAY_TOOL_DEFINITIONS)
MEMORY_MODULE = Memory

__all__ = [
    "ROOT",
    "SKILLS_DIR",
    "SKILL_DICTIONARY",
    "TOOL_DICTIONARY",
    "TOOL_SCHEMA_LIST",
    "MEMORY_MODULE",
    "load_skill",
    "build_skill_dictionary",
    "ManuclawAgent",
    "agent",
    "agent_loop",
    "handler",
    "ManuclawApp",
]


class ManuclawAgent:
    async def agent_loop(self, user_message: str, **kwargs: Any) -> dict[str, Any]:
        return await gateway_agent_loop(user_message, **kwargs)

    async def handler(self, websocket: Any) -> None:
        await gateway_handler(websocket)


agent = ManuclawAgent()


async def agent_loop(user_message: str, **kwargs: Any) -> dict[str, Any]:
    return await agent.agent_loop(user_message, **kwargs)


async def handler(websocket: Any) -> None:
    await agent.handler(websocket)


class ManuclawApp(BaseManuclawApp):
    def __init__(self) -> None:
        super().__init__(root=ROOT)

    def _memory_root(self) -> Path:
        return ROOT


if __name__ == "__main__":
    ManuclawApp().run()
