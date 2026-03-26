from __future__ import annotations

import json
from typing import Any, Iterable


def history_rows_to_events(
    rows: Iterable[dict[str, object | None]], conversation_id: str
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        role = str(row["role"])
        iteration_value = row["iteration"]
        iteration = int(str(iteration_value)) if iteration_value is not None else 0
        tool_name = row.get("tool_name")
        content = str(row["content"])

        if role == "user":
            events.append(
                {
                    "type": "user_input",
                    "conversation_id": conversation_id,
                    "iteration": iteration,
                    "payload": {"text": content},
                }
            )
            continue

        if role == "tool_result":
            try:
                parsed_content: object = json.loads(content)
            except Exception:
                parsed_content = {"raw": content}
            events.append(
                {
                    "type": "tool_result",
                    "conversation_id": conversation_id,
                    "iteration": iteration,
                    "payload": {
                        "tool_name": str(tool_name) if tool_name is not None else None,
                        "result": parsed_content,
                    },
                    "stop_reason": "tool_use",
                }
            )
            continue

        if role == "assistant":
            events.append(
                {
                    "type": "final_response",
                    "conversation_id": conversation_id,
                    "iteration": iteration,
                    "payload": {"content": content},
                    "stop_reason": "end_turn",
                }
            )

    return events
