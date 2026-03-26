from __future__ import annotations

from pathlib import Path
from typing import Any

TOOL_NAME = "load_skill"
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "tool_name": TOOL_NAME, "data": data, "error": None}


def _err(message: str) -> dict[str, Any]:
    return {"ok": False, "tool_name": TOOL_NAME, "data": None, "error": message}


def load_skill(name: str) -> dict[str, Any]:
    cleaned = (name or "").strip()
    if not cleaned:
        return _err("name is required")
    if "/" in cleaned or "\\" in cleaned or cleaned.endswith(".md"):
        return _err("skill name must be a bare name without path or extension")

    path = SKILLS_DIR / f"{cleaned}.md"
    if not path.exists():
        return _err(f"skill '{cleaned}' not found")

    return _ok({"name": cleaned, "content": path.read_text(encoding="utf-8")})
