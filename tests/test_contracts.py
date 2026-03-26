import json
import sqlite3

from gateway import index as gateway
from memory.index import Memory


def test_tools_json_has_exactly_five_tools():
    data = json.loads((gateway.PROJECT_ROOT / "tools.json").read_text(encoding="utf-8"))
    names = [item["name"] for item in data]
    assert names == [
        "youtube_detect",
        "youtube_transcript",
        "summarize",
        "write_file",
        "load_skill",
    ]


def test_memory_schema_contains_iteration_column(tmp_path):
    db_path = tmp_path / "memory.db"
    memory = Memory(str(db_path))
    memory.close()

    connection = sqlite3.connect(db_path)
    rows = connection.execute("PRAGMA table_info(memory)").fetchall()
    connection.close()
    columns = [row[1] for row in rows]
    assert "iteration" in columns


def test_event_types_are_whitelisted():
    assert gateway.ALLOWED_EVENTS == {
        "user_input",
        "loop_update",
        "tool_start",
        "tool_result",
        "final_response",
        "error",
    }


def test_event_envelope_has_required_fields():
    event = gateway._make_event(
        "loop_update",
        "conv-1",
        2,
        {"status": "running"},
        stop_reason="tool_use",
    )
    assert set(event.keys()) == {
        "type",
        "conversation_id",
        "iteration",
        "payload",
        "stop_reason",
    }
