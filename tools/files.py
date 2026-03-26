from __future__ import annotations

from pathlib import Path
from typing import Any

TOOL_NAME = "write_file"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"


def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "tool_name": TOOL_NAME, "data": data, "error": None}


def _err(message: str) -> dict[str, Any]:
    return {"ok": False, "tool_name": TOOL_NAME, "data": None, "error": message}


def write_file(filename: str, content: str) -> dict[str, Any]:
    if not filename or not filename.strip():
        return _err("filename is required")

    if Path(filename).is_absolute() or ".." in Path(filename).parts:
        return _err("invalid filename: absolute and traversal paths are not allowed")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    return _ok({"path": str(output_path), "saved": True})
