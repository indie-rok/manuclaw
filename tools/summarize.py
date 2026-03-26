from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

TOOL_NAME = "summarize"
DEFAULT_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = (
    os.getenv("OPENROUTER_MODEL") or os.getenv("LLM_MODEL") or "moonshotai/kimi-k2.5"
)


def _resolve_chat_completions_url() -> str:
    configured = (
        os.getenv("OPENROUTER_BASE_URL")
        or os.getenv("LLM_BASE_URL")
        or DEFAULT_OPENROUTER_URL
    ).rstrip("/")
    if configured.endswith("/chat/completions"):
        return configured
    return f"{configured}/chat/completions"


OPENROUTER_URL = _resolve_chat_completions_url()


def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "tool_name": TOOL_NAME, "data": data, "error": None}


def _err(message: str) -> dict[str, Any]:
    return {"ok": False, "tool_name": TOOL_NAME, "data": None, "error": message}


async def summarize(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        return _err("text is required")

    api_key = os.getenv("OPENROUTER_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return _err("OPENROUTER_KEY is missing")

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You summarize transcripts clearly for beginners. "
                    "Return 3-5 concise bullet points."
                ),
            },
            {"role": "user", "content": text[:12000]},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            status_code = getattr(response, "status_code", 200)
            if status_code >= 400:
                return _err(
                    f"summarization request failed ({status_code}) at {OPENROUTER_URL}: {response.text[:2000]}"
                )
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            return _ok({"summary": content})
    except Exception as exc:
        return _err(f"summarization failed: {exc}")
