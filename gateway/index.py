from __future__ import annotations

import asyncio
import inspect
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

import httpx
import websockets
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from memory.index import Memory
from tools.files import write_file
from tools.skill_loader import load_skill
from tools.summarize import summarize
from tools.youtube import youtube_detect, youtube_transcript

load_dotenv()

TOOLS_PATH = PROJECT_ROOT / "tools.json"

DEFAULT_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = (
    os.getenv("OPENROUTER_MODEL") or os.getenv("LLM_MODEL") or "moonshotai/kimi-k2.5"
)
MAX_ITERATIONS = 10


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

EVENT_USER_INPUT = "user_input"
EVENT_LOOP_UPDATE = "loop_update"
EVENT_TOOL_START = "tool_start"
EVENT_TOOL_RESULT = "tool_result"
EVENT_FINAL_RESPONSE = "final_response"
EVENT_ERROR = "error"

ALLOWED_EVENTS = {
    EVENT_USER_INPUT,
    EVENT_LOOP_UPDATE,
    EVENT_TOOL_START,
    EVENT_TOOL_RESULT,
    EVENT_FINAL_RESPONSE,
    EVENT_ERROR,
}

SYSTEM_PROMPT = (
    "You are a helpful assistant that processes YouTube videos. "
    "Use tools to detect a video id, fetch transcript, summarize it, and save the summary to output/. "
    "Use load_skill when YouTube-specific guidance is needed."
)

TOOL_HANDLERS: dict[str, Callable[..., Any]] = {
    "youtube_detect": youtube_detect,
    "youtube_transcript": youtube_transcript,
    "summarize": summarize,
    "write_file": write_file,
    "load_skill": load_skill,
}


def load_tool_definitions() -> list[dict[str, Any]]:
    return json.loads(TOOLS_PATH.read_text(encoding="utf-8"))


TOOL_DEFINITIONS = load_tool_definitions()


def _make_event(
    event_type: str,
    conversation_id: str,
    iteration: int,
    payload: dict[str, Any],
    stop_reason: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "type": event_type,
        "conversation_id": conversation_id,
        "iteration": iteration,
        "payload": payload,
    }
    if stop_reason is not None:
        event["stop_reason"] = stop_reason
    return event


async def _emit(
    callback: Callable[[dict[str, Any]], Any] | None,
    event: dict[str, Any],
) -> None:
    if callback is None:
        return
    outcome = callback(event)
    if inspect.isawaitable(outcome):
        await outcome


def _tool_result_message(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False)


async def call_llm(
    conversation_history: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> dict[str, Any]:
    api_key = os.getenv("OPENROUTER_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_KEY is missing")

    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for message in conversation_history:
        role = message["role"]
        if role == "user":
            messages.append({"role": "user", "content": message["content"]})
        elif role == "assistant":
            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": message.get("content") or "",
            }
            if message.get("tool_calls"):
                assistant_message["tool_calls"] = message["tool_calls"]
            messages.append(assistant_message)
        elif role == "tool_result":
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": message["tool_use_id"],
                    "content": message["content"],
                }
            )

    api_tools = [
        {
            "type": "function",
            "function": {
                "name": item["name"],
                "description": item.get("description", ""),
                "parameters": item["input_schema"],
            },
        }
        for item in tools
    ]

    request_payload = {
        "model": MODEL,
        "messages": messages,
        "tools": api_tools,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request_payload,
        )
        if response.status_code >= 400:
            error_body = response.text[:2000]
            raise RuntimeError(
                f"LLM request failed ({response.status_code}) at {OPENROUTER_URL}: {error_body}"
            )
        body = response.json()

    choice = body["choices"][0]
    message = choice["message"]
    raw_tool_calls = message.get("tool_calls", [])
    parsed_tool_calls: list[dict[str, Any]] = []
    for tool_call in raw_tool_calls:
        arguments = tool_call["function"]["arguments"]
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        parsed_tool_calls.append(
            {
                "id": tool_call["id"],
                "name": tool_call["function"]["name"],
                "input": arguments,
            }
        )

    stop_reason = "tool_use" if parsed_tool_calls else "end_turn"
    return {
        "role": "assistant",
        "content": message.get("content", ""),
        "stop_reason": stop_reason,
        "tool_calls": parsed_tool_calls,
    }


async def run_agent_loop(
    user_message: str,
    on_event: Callable[[dict[str, Any]], Any] | None = None,
    memory: Memory | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    current_conversation_id = conversation_id or str(uuid.uuid4())
    local_memory = memory or Memory()

    await _emit(
        on_event,
        _make_event(
            EVENT_USER_INPUT,
            current_conversation_id,
            0,
            {"text": user_message},
        ),
    )
    local_memory.save(current_conversation_id, "user", user_message, iteration=0)

    conversation_history: list[dict[str, Any]] = [
        {"role": "user", "content": user_message}
    ]

    for iteration in range(1, MAX_ITERATIONS + 1):
        final_result = await _run_single_agent_iteration(
            iteration=iteration,
            conversation_history=conversation_history,
            conversation_id=current_conversation_id,
            memory=local_memory,
            on_event=on_event,
        )
        if final_result is not None:
            return final_result

    message = f"max iterations reached ({MAX_ITERATIONS})"
    local_memory.save(
        current_conversation_id, "assistant", message, iteration=MAX_ITERATIONS + 1
    )
    await _emit(
        on_event,
        _make_event(
            EVENT_ERROR,
            current_conversation_id,
            MAX_ITERATIONS + 1,
            {"message": message},
            stop_reason="error",
        ),
    )
    return {
        "conversation_id": current_conversation_id,
        "role": "assistant",
        "content": "",
        "stop_reason": "error",
        "tool_calls": [],
    }


async def _run_single_agent_iteration(
    iteration: int,
    conversation_history: list[dict[str, Any]],
    conversation_id: str,
    memory: Memory,
    on_event: Callable[[dict[str, Any]], Any] | None,
) -> dict[str, Any] | None:
    await _emit(
        on_event,
        _make_event(
            EVENT_LOOP_UPDATE,
            conversation_id,
            iteration,
            {"status": "running"},
            stop_reason="tool_use",
        ),
    )

    llm_answer = await call_llm(conversation_history, TOOL_DEFINITIONS)
    conversation_history.append(
        {
            "role": "assistant",
            "content": llm_answer.get("content", ""),
            "tool_calls": [
                {
                    "id": tool_call["id"],
                    "type": "function",
                    "function": {
                        "name": tool_call["name"],
                        "arguments": json.dumps(tool_call["input"], ensure_ascii=False),
                    },
                }
                for tool_call in llm_answer.get("tool_calls", [])
            ],
        }
    )

    if llm_answer["stop_reason"] != "tool_use":
        content = llm_answer.get("content") or ""
        memory.save(conversation_id, "assistant", content, iteration=iteration)
        await _emit(
            on_event,
            _make_event(
                EVENT_FINAL_RESPONSE,
                conversation_id,
                iteration,
                {"content": content},
                stop_reason=llm_answer["stop_reason"],
            ),
        )
        return {"conversation_id": conversation_id, **llm_answer}

    for tool_call in llm_answer["tool_calls"]:
        tool_name = tool_call["name"]
        tool_input = tool_call.get("input", {})
        await _emit(
            on_event,
            _make_event(
                EVENT_TOOL_START,
                conversation_id,
                iteration,
                {"tool_name": tool_name, "input": tool_input},
                stop_reason="tool_use",
            ),
        )

        handler = TOOL_HANDLERS.get(tool_name)
        if handler is None:
            result = {
                "ok": False,
                "tool_name": tool_name,
                "data": None,
                "error": f"unknown tool '{tool_name}'",
            }
        else:
            raw = handler(**tool_input)
            result = await raw if inspect.isawaitable(raw) else raw

        result_text = _tool_result_message(result)
        memory.save(
            conversation_id,
            "tool_result",
            result_text,
            iteration=iteration,
            tool_name=tool_name,
        )
        conversation_history.append(
            {
                "role": "tool_result",
                "tool_use_id": tool_call["id"],
                "content": result_text,
            }
        )

        await _emit(
            on_event,
            _make_event(
                EVENT_TOOL_RESULT,
                conversation_id,
                iteration,
                {"tool_name": tool_name, "result": result},
                stop_reason="tool_use",
            ),
        )

    return None


async def _send_gateway_event(websocket: Any, event: dict[str, Any]) -> None:
    await websocket.send(json.dumps(event, ensure_ascii=False))


async def _process_client_message(websocket: Any, message: str, db: Memory) -> None:
    conversation_id = str(uuid.uuid4())

    async def send_event_to_client(event: dict[str, Any]) -> None:
        await _send_gateway_event(websocket, event)

    try:
        await run_agent_loop(
            message,
            on_event=send_event_to_client,
            memory=db,
            conversation_id=conversation_id,
        )
    except Exception as exc:
        error_event = _make_event(
            EVENT_ERROR,
            conversation_id,
            0,
            {"message": str(exc)},
            stop_reason="error",
        )
        await _send_gateway_event(websocket, error_event)


async def handler(websocket: Any) -> None:
    db = Memory()
    try:
        async for incoming in websocket:
            await _process_client_message(websocket, incoming, db)
    finally:
        db.close()


async def main() -> None:
    async with websockets.serve(handler, "localhost", 8765):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
