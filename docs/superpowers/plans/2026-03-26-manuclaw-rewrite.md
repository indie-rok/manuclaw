# Manuclaw Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite manuclaw from a hardcoded pipeline into a real agent loop — while loop, dispatch map, tool calling, skills, and a gateway — applied to a YouTube summarizer use case.

**Architecture:** TUI connects to Gateway via WebSocket. Gateway runs a `while stop_reason == "tool_use"` agent loop. The LLM decides which tool to call at each step via a dispatch map. One skill (`youtube.md`) loaded on demand. Memory stored in SQLite.

**Tech Stack:** Python 3.11+, Textual (TUI), websockets, OpenRouter API (Kimi K2.5), youtube-transcript-api, SQLite

**Spec:** `docs/superpowers/specs/2026-03-26-manuclaw-rewrite-design.md`

---

## File Structure

```
manuclaw.py                      # TUI (Textual framework, full rewrite)
gateway/
  __init__.py                    # keep existing empty init
  index.py                       # WebSocket server + agent loop (full rewrite)
tools/
  __init__.py                    # empty init
  youtube.py                     # youtube_detect + youtube_transcript
  summarize.py                   # transcript_summarizer (LLM call)
  files.py                       # write_file tool
  skill_loader.py                # load_skill tool
skills/
  youtube.md                     # YouTube edge cases, language fallbacks
memory/
  __init__.py                    # keep existing empty init
  index.py                       # SQLite memory (full rewrite, new schema)
tools.json                       # Tool definitions (JSON schemas for the LLM)
requirements.txt                 # Updated dependencies
output/                          # Created at runtime by write_file tool
```

### Deletions
- `subtask-generator/` — entire directory (LLM decides in the loop now)
- `tooling-detection/` — replaced by simpler `tools.json`
- `ai-loop-orch/` — split into `tools/` directory

---

## Task 1: Clean up old code and update project scaffolding

**Files:**
- Delete: `subtask-generator/index.py`, `subtask-generator/` directory
- Delete: `tooling-detection/tooling.json`, `tooling-detection/` directory
- Delete: `ai-loop-orch/index.py`, `ai-loop-orch/__init__.py`, `ai-loop-orch/` directory
- Create: `tools/__init__.py`
- Create: `skills/youtube.md`
- Create: `tools.json`
- Modify: `requirements.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Delete old directories**

```bash
rm -rf subtask-generator/ tooling-detection/ ai-loop-orch/
```

- [ ] **Step 2: Create `tools/__init__.py`**

Create an empty init file:

```python
# tools/__init__.py
```

- [ ] **Step 3: Create `skills/youtube.md`**

```markdown
# YouTube Skill

## Handling edge cases
- Shortened URLs (youtu.be/ID) are valid — extract the ID from the path
- Playlist URLs contain both list= and v= params — use v= for the video ID
- YouTube Shorts URLs (/shorts/ID) — the ID is in the path
- Some videos have auto-generated transcripts (prefixed with "a.") — try those as fallback

## Language fallbacks
Try languages in this order: en, en-US, a.en (auto-generated), fr, fr-FR, a.fr
If all fail, report which languages are available.

## Transcript tips
- Transcripts can be very long (10k+ words). Always summarize before presenting.
- Auto-generated transcripts have no punctuation — the summarizer handles this fine.
```

- [ ] **Step 4: Create `tools.json`**

```json
[
    {
        "name": "youtube_detect",
        "description": "Extract a YouTube video ID from a URL or text input.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": { "type": "string", "description": "Text containing a YouTube URL or video ID" }
            },
            "required": ["text"]
        }
    },
    {
        "name": "youtube_transcript",
        "description": "Fetch the transcript of a YouTube video by its video ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "video_id": { "type": "string", "description": "The YouTube video ID" }
            },
            "required": ["video_id"]
        }
    },
    {
        "name": "summarize",
        "description": "Summarize text using an LLM. Good for long transcripts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": { "type": "string", "description": "The text to summarize" }
            },
            "required": ["text"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file in the output/ folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": { "type": "string", "description": "Name of the file to create" },
                "content": { "type": "string", "description": "Content to write" }
            },
            "required": ["filename", "content"]
        }
    },
    {
        "name": "load_skill",
        "description": "Load specialized knowledge from a skill file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": { "type": "string", "description": "Skill name to load (e.g. 'youtube')" }
            },
            "required": ["name"]
        }
    }
]
```

- [ ] **Step 5: Update `requirements.txt`**

```
textual>=1.0.0
websockets>=12.0
httpx>=0.27.0
python-dotenv>=1.0.0
youtube-transcript-api>=0.6.0
```

(No changes needed — current deps are correct.)

- [ ] **Step 6: Update `.gitignore`**

Add `output/` to `.gitignore` so saved summaries aren't committed:

```
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
env/
*.egg-info/
dist/
build/
.DS_Store
*.pyc
.sisyphus
.env
manuclaw.db
output/
```

- [ ] **Step 7: Commit scaffolding**

```bash
git add -A
git commit -m "chore: remove old pipeline dirs, add tool/skill scaffolding"
```

---

## Task 2: Implement `tools/youtube.py` — youtube_detect and youtube_transcript

**Files:**
- Create: `tools/youtube.py`
- Create: `tests/test_youtube.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_youtube.py`:

```python
"""Tests for tools/youtube.py — youtube_detect and youtube_transcript."""

from tools.youtube import youtube_detect, youtube_transcript


# --- youtube_detect tests ---

def test_detect_standard_url():
    result = youtube_detect(text="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert result == "dQw4w9WgXcQ"


def test_detect_shortened_url():
    result = youtube_detect(text="https://youtu.be/dQw4w9WgXcQ")
    assert result == "dQw4w9WgXcQ"


def test_detect_shorts_url():
    result = youtube_detect(text="https://www.youtube.com/shorts/dQw4w9WgXcQ")
    assert result == "dQw4w9WgXcQ"


def test_detect_bare_id():
    result = youtube_detect(text="dQw4w9WgXcQ")
    assert result == "dQw4w9WgXcQ"


def test_detect_playlist_url():
    result = youtube_detect(text="https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf")
    assert result == "dQw4w9WgXcQ"


def test_detect_no_match():
    result = youtube_detect(text="this is just some random text")
    assert result is None


def test_detect_embedded_in_sentence():
    result = youtube_detect(text="Check out this video: https://youtu.be/abc123DEF45 it's great")
    assert result == "abc123DEF45"


# --- youtube_transcript tests ---

def test_transcript_returns_string(monkeypatch):
    """Mock the YouTubeTranscriptApi to avoid network calls."""
    class FakeSegment:
        def __init__(self, text):
            self.text = text

    class FakeApi:
        def fetch(self, video_id, languages):
            return [FakeSegment("Hello"), FakeSegment("world")]

    monkeypatch.setattr("tools.youtube.YouTubeTranscriptApi", FakeApi)
    result = youtube_transcript(video_id="abc123DEF45")
    assert result == "Hello world"


def test_transcript_error_returns_error_string(monkeypatch):
    """When the API raises, return an error string."""
    class FakeApi:
        def fetch(self, video_id, languages):
            raise Exception("No transcript found")

    monkeypatch.setattr("tools.youtube.YouTubeTranscriptApi", FakeApi)
    result = youtube_transcript(video_id="nonexistent")
    assert "error" in result.lower() or "No transcript" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/emmanuelorozco/Projects/python/manuclaw
python -m pytest tests/test_youtube.py -v
```

Expected: FAIL — `tools/youtube.py` doesn't have the functions yet.

- [ ] **Step 3: Implement `tools/youtube.py`**

```python
"""tools/youtube — detect YouTube URLs and fetch transcripts."""

import re
from youtube_transcript_api import YouTubeTranscriptApi


def youtube_detect(text: str) -> str | None:
    """Extract a YouTube video ID from a URL or text input.

    Returns the 11-character video ID, or None if no match found.
    """
    # Standard watch URL: youtube.com/watch?v=ID
    match = re.search(r"v=([A-Za-z0-9_-]{11})", text)
    if match:
        return match.group(1)

    # Shortened URL: youtu.be/ID
    match = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", text)
    if match:
        return match.group(1)

    # Shorts URL: youtube.com/shorts/ID
    match = re.search(r"/shorts/([A-Za-z0-9_-]{11})", text)
    if match:
        return match.group(1)

    # Bare 11-character ID
    match = re.fullmatch(r"[A-Za-z0-9_-]{11}", text.strip())
    if match:
        return text.strip()

    return None


def youtube_transcript(video_id: str) -> str:
    """Fetch the transcript of a YouTube video.

    Tries multiple language fallbacks. Returns the transcript text
    or an error message string starting with "Error:".
    """
    # Language fallback order (same as the youtube skill)
    languages = ["en", "en-US", "a.en", "fr", "fr-FR", "a.fr"]

    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=languages)
        return " ".join(seg.text for seg in fetched)
    except Exception as e:
        return f"Error: {e}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_youtube.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/youtube.py tests/test_youtube.py
git commit -m "feat: add youtube_detect and youtube_transcript tools"
```

---

## Task 3: Implement `tools/summarize.py` — the LLM summarizer tool

**Files:**
- Create: `tools/summarize.py`
- Create: `tests/test_summarize.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_summarize.py`:

```python
"""Tests for tools/summarize.py — summarize tool."""

import pytest
from tools.summarize import summarize


@pytest.mark.asyncio
async def test_summarize_calls_llm(monkeypatch):
    """Mock httpx to verify summarize sends the right request and returns content."""
    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "choices": [{"message": {"content": "This is a summary."}}]
            }

    class FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, headers=None, json=None):
            # Verify the transcript text is in the request
            assert json["messages"][1]["content"] == "some transcript text"
            return FakeResponse()

    monkeypatch.setenv("OPENROUTER_KEY", "test-key")
    import tools.summarize as mod
    mod.OPENROUTER_KEY = "test-key"
    monkeypatch.setattr("httpx.AsyncClient", lambda **kw: FakeClient())
    result = await summarize(text="some transcript text")
    assert result == "This is a summary."


@pytest.mark.asyncio
async def test_summarize_no_api_key(monkeypatch):
    """Return error string when API key is missing."""
    import tools.summarize as mod
    mod.OPENROUTER_KEY = None
    result = await summarize(text="hello")
    assert "error" in result.lower() or "OPENROUTER_KEY" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_summarize.py -v
```

Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Implement `tools/summarize.py`**

```python
"""tools/summarize — summarize text using an LLM via OpenRouter."""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
MODEL = "moonshotai/kimi-k2.5"


async def summarize(text: str) -> str:
    """Summarize text using an LLM. Good for long transcripts.

    Returns the summary string, or an error message string.
    """
    if not OPENROUTER_KEY:
        return "Error: OPENROUTER_KEY not set in environment."

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a concise summarizer. "
                            "Summarize the following text in 3-5 clear bullet points. "
                            "Be direct and informative."
                        ),
                    },
                    {"role": "user", "content": text[:12000]},
                ],
                "temperature": 0.3,
            },
        )

    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pip install pytest-asyncio  # needed for async tests
python -m pytest tests/test_summarize.py -v
```

Expected: Both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/summarize.py tests/test_summarize.py
git commit -m "feat: add summarize tool (LLM via OpenRouter)"
```

---

## Task 4: Implement `tools/files.py` — write_file tool

**Files:**
- Create: `tools/files.py`
- Create: `tests/test_files.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_files.py`:

```python
"""Tests for tools/files.py — write_file tool."""

from pathlib import Path
from tools.files import write_file


def test_write_file_creates_file(tmp_path, monkeypatch):
    """write_file should create a file in the output/ folder."""
    # Point OUTPUT_DIR to a temp directory for testing
    import tools.files as mod
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path)

    result = write_file(filename="test.md", content="# Hello\n\nWorld")
    expected_path = tmp_path / "test.md"
    assert expected_path.exists()
    assert expected_path.read_text() == "# Hello\n\nWorld"
    assert "test.md" in result


def test_write_file_creates_output_dir(tmp_path, monkeypatch):
    """write_file should create the output directory if it doesn't exist."""
    import tools.files as mod
    target = tmp_path / "new_output"
    monkeypatch.setattr(mod, "OUTPUT_DIR", target)

    write_file(filename="doc.txt", content="content")
    assert (target / "doc.txt").exists()


def test_write_file_rejects_path_traversal(tmp_path, monkeypatch):
    """write_file should reject filenames with path traversal."""
    import tools.files as mod
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path)

    result = write_file(filename="../etc/passwd", content="bad")
    assert "error" in result.lower() or not (tmp_path.parent / "etc" / "passwd").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_files.py -v
```

Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Implement `tools/files.py`**

```python
"""tools/files — write content to a file in the output/ folder."""

from pathlib import Path

# Output directory lives at the project root
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def write_file(filename: str, content: str) -> str:
    """Write content to a file in the output/ folder.

    Returns a confirmation message or an error message.
    """
    # Security: reject path traversal
    if ".." in filename or filename.startswith("/"):
        return "Error: invalid filename (no path traversal allowed)."

    # Create output directory if needed
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    file_path = OUTPUT_DIR / filename
    file_path.write_text(content, encoding="utf-8")
    return f"Saved to output/{filename}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_files.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/files.py tests/test_files.py
git commit -m "feat: add write_file tool"
```

---

## Task 5: Implement `tools/skill_loader.py` — load_skill tool

**Files:**
- Create: `tools/skill_loader.py`
- Create: `tests/test_skill_loader.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_skill_loader.py`:

```python
"""Tests for tools/skill_loader.py — load_skill tool."""

from pathlib import Path
from tools.skill_loader import load_skill


def test_load_existing_skill(tmp_path, monkeypatch):
    """load_skill should return the content of a skill file."""
    import tools.skill_loader as mod
    monkeypatch.setattr(mod, "SKILLS_DIR", tmp_path)

    (tmp_path / "youtube.md").write_text("# YouTube Skill\n\nSome content")
    result = load_skill(name="youtube")
    assert "YouTube Skill" in result
    assert "Some content" in result


def test_load_nonexistent_skill(tmp_path, monkeypatch):
    """load_skill should return an error for missing skills."""
    import tools.skill_loader as mod
    monkeypatch.setattr(mod, "SKILLS_DIR", tmp_path)

    result = load_skill(name="nonexistent")
    assert "error" in result.lower() or "not found" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_skill_loader.py -v
```

Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Implement `tools/skill_loader.py`**

```python
"""tools/skill_loader — load specialized knowledge from skill files."""

from pathlib import Path

# Skills directory lives at the project root
SKILLS_DIR = Path(__file__).parent.parent / "skills"


def load_skill(name: str) -> str:
    """Load specialized knowledge from a skill file.

    Looks for skills/<name>.md and returns its content.
    Returns an error message if the skill doesn't exist.
    """
    skill_path = SKILLS_DIR / f"{name}.md"

    if not skill_path.exists():
        return f"Error: skill '{name}' not found."

    return skill_path.read_text(encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_skill_loader.py -v
```

Expected: Both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/skill_loader.py tests/test_skill_loader.py
git commit -m "feat: add load_skill tool"
```

---

## Task 6: Rewrite `memory/index.py` — new SQLite schema

**Files:**
- Rewrite: `memory/index.py`
- Create: `tests/test_memory.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_memory.py`:

```python
"""Tests for memory/index.py — conversation memory backed by SQLite."""

import time
from memory.index import Memory


def test_save_and_get_history(tmp_path):
    """Save messages and retrieve them by conversation_id."""
    db_path = tmp_path / "test.db"
    mem = Memory(db_path=str(db_path))

    mem.save(conversation_id="conv1", role="user", content="Hello", tool_name=None)
    mem.save(conversation_id="conv1", role="assistant", content="Hi there", tool_name=None)

    history = mem.get_history("conv1")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"
    assert history[1]["role"] == "assistant"
    mem.close()


def test_save_tool_result(tmp_path):
    """Save a tool result message with tool_name set."""
    db_path = tmp_path / "test.db"
    mem = Memory(db_path=str(db_path))

    mem.save(
        conversation_id="conv1",
        role="tool_result",
        content='{"video_id": "abc123"}',
        tool_name="youtube_detect",
    )

    history = mem.get_history("conv1")
    assert len(history) == 1
    assert history[0]["tool_name"] == "youtube_detect"
    assert history[0]["role"] == "tool_result"
    mem.close()


def test_separate_conversations(tmp_path):
    """Messages from different conversations don't mix."""
    db_path = tmp_path / "test.db"
    mem = Memory(db_path=str(db_path))

    mem.save(conversation_id="conv1", role="user", content="Message 1")
    mem.save(conversation_id="conv2", role="user", content="Message 2")

    assert len(mem.get_history("conv1")) == 1
    assert len(mem.get_history("conv2")) == 1
    mem.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_memory.py -v
```

Expected: FAIL — the new Memory class doesn't exist yet.

- [ ] **Step 3: Implement `memory/index.py`**

Completely replace the existing file:

```python
"""memory — SQLite-backed conversation history.

Each row represents one message in the agent loop:
user messages, assistant responses, and tool results.
"""

import sqlite3
import time


class Memory:
    """Stores and retrieves conversation history using SQLite."""

    def __init__(self, db_path: str = "manuclaw.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self) -> None:
        """Create the memory table if it doesn't exist."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    tool_name TEXT,
                    content TEXT NOT NULL,
                    timestamp INTEGER NOT NULL
                )
            """)

    def save(self, conversation_id: str, role: str, content: str, tool_name: str = None) -> None:
        """Save a message to conversation history."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO memory (conversation_id, role, tool_name, content, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, role, tool_name, content, int(time.time())),
            )

    def get_history(self, conversation_id: str) -> list[dict]:
        """Retrieve all messages for a conversation, ordered by time."""
        cursor = self.conn.execute(
            """
            SELECT role, tool_name, content, timestamp
            FROM memory
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_memory.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add memory/index.py tests/test_memory.py
git commit -m "feat: rewrite memory module with new conversation schema"
```

---

## Task 7: Rewrite `gateway/index.py` — the agent loop

This is the core of the rewrite. The gateway runs the `while stop_reason == "tool_use"` loop.

**Files:**
- Rewrite: `gateway/index.py`
- Create: `tests/test_gateway.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_gateway.py`:

```python
"""Tests for gateway/index.py — the agent loop."""

import json
import pytest
from gateway.index import run_agent_loop


@pytest.mark.asyncio
async def test_agent_loop_single_tool_call(monkeypatch):
    """Simulate: LLM calls youtube_detect, then gives final answer."""
    call_count = 0

    async def fake_llm(conversation_history, tools):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: LLM wants to use youtube_detect
            return {
                "role": "assistant",
                "content": None,
                "stop_reason": "tool_use",
                "tool_calls": [
                    {"name": "youtube_detect", "id": "call_1", "input": {"text": "youtu.be/abc123DEF45"}}
                ],
            }
        else:
            # Second call: LLM gives final answer
            return {
                "role": "assistant",
                "content": "The video ID is abc123DEF45.",
                "stop_reason": "end_turn",
                "tool_calls": [],
            }

    def fake_youtube_detect(text):
        return "abc123DEF45"

    fake_handlers = {"youtube_detect": fake_youtube_detect}

    import gateway.index as mod
    monkeypatch.setattr(mod, "call_llm", fake_llm)
    monkeypatch.setattr(mod, "TOOL_HANDLERS", fake_handlers)

    messages = []

    async def on_event(event):
        messages.append(event)

    result = await run_agent_loop("Find the video ID in youtu.be/abc123DEF45", on_event=on_event)

    assert result["content"] == "The video ID is abc123DEF45."
    assert call_count == 2


@pytest.mark.asyncio
async def test_agent_loop_no_tool_calls(monkeypatch):
    """If the LLM doesn't want any tools, loop exits immediately."""
    async def fake_llm(conversation_history, tools):
        return {
            "role": "assistant",
            "content": "I can't help with that.",
            "stop_reason": "end_turn",
            "tool_calls": [],
        }

    import gateway.index as mod
    monkeypatch.setattr(mod, "call_llm", fake_llm)

    result = await run_agent_loop("random question", on_event=lambda e: None)
    assert result["content"] == "I can't help with that."
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_gateway.py -v
```

Expected: FAIL — `run_agent_loop` doesn't exist yet.

- [ ] **Step 3: Implement `gateway/index.py`**

Completely replace the existing file:

```python
"""gateway — WebSocket server + agent loop.

The gateway receives user messages via WebSocket, runs the agent loop,
and streams events back to the TUI.
"""

import asyncio
import json
import os
import uuid
from pathlib import Path

import httpx
import websockets
from dotenv import load_dotenv

load_dotenv()

# Resolve project root so we can import tools and load tools.json
ROOT = Path(__file__).parent.parent

# Import all tool handlers
from tools.youtube import youtube_detect, youtube_transcript
from tools.summarize import summarize
from tools.files import write_file
from tools.skill_loader import load_skill

# Import memory
from memory.index import Memory

# ── Configuration ─────────────────────────────────────────────────────────────

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
MODEL = "moonshotai/kimi-k2.5"

SYSTEM_PROMPT = """\
You are a helpful assistant that can process YouTube videos.
You have tools to detect YouTube URLs, fetch transcripts, summarize text, write files, and load skills.

When a user gives you a YouTube URL:
1. Detect the video ID
2. Fetch the transcript
3. Summarize it
4. Save the summary to a file in the output/ folder

Use the load_skill tool if you need specialized knowledge about YouTube.
Always save results to a file so the user has a copy."""

# ── Load tool definitions from tools.json ─────────────────────────────────────

def load_tool_definitions() -> list[dict]:
    """Load tool JSON schemas from tools.json."""
    tools_path = ROOT / "tools.json"
    with open(tools_path) as f:
        return json.load(f)

TOOL_DEFINITIONS = load_tool_definitions()

# ── The dispatch map — routes tool names to handler functions ─────────────────

TOOL_HANDLERS = {
    "youtube_detect":     youtube_detect,
    "youtube_transcript": youtube_transcript,
    "summarize":          summarize,
    "write_file":         write_file,
    "load_skill":         load_skill,
}

# ── LLM caller ────────────────────────────────────────────────────────────────

async def call_llm(conversation_history: list[dict], tools: list[dict]) -> dict:
    """Call the LLM via OpenRouter and return a structured response.

    Returns a dict with: role, content, stop_reason, tool_calls
    """
    # Build messages for the API — convert our internal format to OpenRouter's
    api_messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for msg in conversation_history:
        if msg["role"] == "user":
            api_messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant":
            # Rebuild the assistant message with tool_use blocks if present
            api_messages.append(msg.get("_raw", {"role": "assistant", "content": msg.get("content", "")}))
        elif msg["role"] == "tool_result":
            api_messages.append({
                "role": "tool",
                "tool_use_id": msg["tool_use_id"],
                "content": msg["content"],
            })

    # Build tools in Anthropic-compatible format for OpenRouter
    api_tools = []
    for t in tools:
        api_tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        })

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": api_messages,
                "tools": api_tools,
                "temperature": 0.3,
            },
        )

    resp.raise_for_status()
    data = resp.json()
    choice = data["choices"][0]
    message = choice["message"]

    # Parse tool calls from the response
    tool_calls = []
    if message.get("tool_calls"):
        for tc in message["tool_calls"]:
            args = tc["function"]["arguments"]
            if isinstance(args, str):
                args = json.loads(args)
            tool_calls.append({
                "name": tc["function"]["name"],
                "id": tc["id"],
                "input": args,
            })

    # Determine stop reason
    stop_reason = "tool_use" if tool_calls else "end_turn"

    return {
        "role": "assistant",
        "content": message.get("content"),
        "stop_reason": stop_reason,
        "tool_calls": tool_calls,
        "_raw": message,  # preserve for re-sending to API
    }


# ── The agent loop ────────────────────────────────────────────────────────────

async def run_agent_loop(user_message: str, on_event=None, memory: Memory = None, conversation_id: str = None) -> dict:
    """Run the agent loop for a single user message.

    Args:
        user_message: The user's input text.
        on_event: Async callback called with event dicts for TUI streaming.
        memory: Optional Memory instance for persistence.
        conversation_id: ID to group messages in memory.

    Returns:
        The final assistant response dict.
    """
    if on_event is None:
        on_event = lambda e: None

    # Start the conversation history with the user's message
    conversation_history = [{"role": "user", "content": user_message}]

    # Save user message to memory
    if memory and conversation_id:
        memory.save(conversation_id=conversation_id, role="user", content=user_message)

    loop_number = 0

    while True:
        loop_number += 1

        # Call the LLM with conversation history + tool definitions
        llm_answer = await call_llm(conversation_history, TOOL_DEFINITIONS)

        # Add the LLM's response to history
        conversation_history.append(llm_answer)

        # Check: does the LLM want to call a tool?
        if llm_answer["stop_reason"] != "tool_use":
            # Done! The LLM has its final answer.
            await on_event({
                "type": "final_answer",
                "loop": loop_number,
                "content": llm_answer["content"],
            })

            if memory and conversation_id:
                memory.save(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=llm_answer["content"] or "",
                )
            break

        # Execute each tool the LLM requested
        for tool_call in llm_answer["tool_calls"]:
            tool_name = tool_call["name"]
            tool_input = tool_call["input"]
            handler = TOOL_HANDLERS.get(tool_name)

            await on_event({
                "type": "tool_call",
                "loop": loop_number,
                "tool": tool_name,
                "input": tool_input,
            })

            if handler is None:
                result_str = f"Error: unknown tool '{tool_name}'"
            else:
                # Some handlers are async (summarize), some are sync
                import asyncio
                result = handler(**tool_input)
                if asyncio.iscoroutine(result):
                    result = await result
                result_str = result if isinstance(result, str) else json.dumps(result)

            await on_event({
                "type": "tool_result",
                "loop": loop_number,
                "tool": tool_name,
                "result": result_str[:200],  # abbreviated for display
            })

            # Feed the tool result back into conversation history
            conversation_history.append({
                "role": "tool_result",
                "tool_use_id": tool_call["id"],
                "content": result_str,
            })

            if memory and conversation_id:
                memory.save(
                    conversation_id=conversation_id,
                    role="tool_result",
                    content=result_str,
                    tool_name=tool_name,
                )

        # Loop continues — LLM sees the result and decides next step

    return llm_answer


# ── WebSocket server ──────────────────────────────────────────────────────────

async def handler(websocket):
    """Handle a single WebSocket connection."""
    print("[gateway] client connected")
    memory = Memory()
    try:
        async for message in websocket:
            print(f"[gateway] received: {message}")
            conversation_id = str(uuid.uuid4())

            async def on_event(event):
                """Stream events back to the TUI as JSON."""
                await websocket.send(json.dumps(event))

            try:
                result = await run_agent_loop(
                    user_message=message,
                    on_event=on_event,
                    memory=memory,
                    conversation_id=conversation_id,
                )
                await websocket.send(json.dumps({"type": "done"}))
            except Exception as e:
                await websocket.send(json.dumps({"type": "error", "message": str(e)}))

    except websockets.exceptions.ConnectionClosed:
        print("[gateway] client disconnected")
    finally:
        memory.close()


async def main():
    """Start the WebSocket server."""
    async with websockets.serve(handler, "localhost", 8765):
        print("[gateway] server started on ws://localhost:8765")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_gateway.py -v
```

Expected: Both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add gateway/index.py tests/test_gateway.py
git commit -m "feat: rewrite gateway with real agent loop and dispatch map"
```

---

## Task 8: Rewrite `manuclaw.py` — TUI showing loop state

The TUI needs to parse the new JSON events from the gateway and display loop iterations, tool calls, results, and the final answer.

**Files:**
- Rewrite: `manuclaw.py`

- [ ] **Step 1: Implement `manuclaw.py`**

Completely replace the existing file:

```python
"""manuclaw — TUI that shows the agent loop in action.

Connects to the gateway via WebSocket and displays each loop iteration:
which tool the LLM chose, the input, the result, and the stop reason.
"""

import json
from pathlib import Path

import websockets
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Input, Static
from textual import work

WS_URL = "ws://localhost:8765"


class ManuclawApp(App):
    """A Textual TUI that visualizes the agent loop."""

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

    .loop-header {
        color: #5cabff;
        margin: 1 0 0 0;
        padding: 0 2;
    }

    .tool-call {
        color: #f5c242;
        margin: 0 0 0 2;
        padding: 0 2;
    }

    .tool-result {
        color: #888888;
        margin: 0 0 0 2;
        padding: 0 2;
    }

    .stop-reason {
        color: #888888;
        margin: 0 0 0 2;
        padding: 0 2;
    }

    .final-answer {
        background: $success-darken-2;
        color: $text;
        margin: 1 4 0 0;
        padding: 1 2;
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
        chat_log.mount(Static(f"> {message}", classes="user-message"))
        chat_log.scroll_end(animate=False)
        self.send_message(message)

    @work(exclusive=True, exit_on_error=False)
    async def send_message(self, message: str) -> None:
        """Send message to gateway and stream loop events."""
        chat_log = self.query_one("#chat-log")
        status = self.query_one("#status-bar")

        try:
            status.update("Connecting...")
            async with websockets.connect(WS_URL) as ws:
                await ws.send(message)
                status.update("Agent loop running...")

                async for raw in ws:
                    event = json.loads(raw)
                    event_type = event.get("type")

                    if event_type == "tool_call":
                        # Show loop header and tool call
                        loop_num = event["loop"]
                        tool = event["tool"]
                        tool_input = json.dumps(event["input"], indent=None)
                        chat_log.mount(Static(
                            f"Loop #{loop_num}",
                            classes="loop-header",
                        ))
                        chat_log.mount(Static(
                            f"  LLM chose: {tool}",
                            classes="tool-call",
                        ))
                        chat_log.mount(Static(
                            f"  Input: {tool_input[:80]}",
                            classes="tool-call",
                        ))
                        status.update(f"Loop #{loop_num} | {tool}")

                    elif event_type == "tool_result":
                        result = event["result"]
                        chat_log.mount(Static(
                            f"  Result: {result[:100]}",
                            classes="tool-result",
                        ))
                        chat_log.mount(Static(
                            "  stop_reason: tool_use -> continuing",
                            classes="stop-reason",
                        ))

                    elif event_type == "final_answer":
                        loop_num = event["loop"]
                        content = event.get("content", "")
                        chat_log.mount(Static(
                            f"  stop_reason: end_turn -> done!",
                            classes="stop-reason",
                        ))
                        chat_log.mount(Static(
                            f"\n{content}",
                            classes="final-answer",
                        ))
                        status.update("Done")

                    elif event_type == "error":
                        chat_log.mount(Static(
                            f"Error: {event.get('message', 'unknown')}",
                            classes="error-message",
                        ))
                        status.update("Error")

                    elif event_type == "done":
                        status.update("Idle")
                        break

                    chat_log.scroll_end(animate=False)

        except Exception:
            chat_log.mount(Static(
                f"Cannot connect to gateway at {WS_URL}",
                classes="error-message",
            ))
            chat_log.scroll_end(animate=False)
            status.update("Disconnected")


if __name__ == "__main__":
    ManuclawApp().run()
```

- [ ] **Step 2: Verify the TUI loads without errors**

```bash
cd /Users/emmanuelorozco/Projects/python/manuclaw
python -c "from manuclaw import ManuclawApp; print('TUI imports OK')"
```

Expected: `TUI imports OK` (no import errors).

- [ ] **Step 3: Commit**

```bash
git add manuclaw.py
git commit -m "feat: rewrite TUI to display agent loop iterations"
```

---

## Task 9: Create `tests/__init__.py` and run full test suite

**Files:**
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `tests/__init__.py`**

```python
# tests/__init__.py
```

- [ ] **Step 2: Run the full test suite**

```bash
cd /Users/emmanuelorozco/Projects/python/manuclaw
python -m pytest tests/ -v
```

Expected: All tests pass (youtube: 8, summarize: 2, files: 3, skill_loader: 2, memory: 3, gateway: 2 = ~20 tests).

- [ ] **Step 3: Fix any failures**

If any tests fail, fix the issue and re-run.

- [ ] **Step 4: Commit**

```bash
git add tests/__init__.py
git commit -m "chore: add tests init and verify full test suite passes"
```

---

## Task 10: Integration smoke test — end-to-end run

- [ ] **Step 1: Verify all imports work together**

```bash
python -c "
from gateway.index import run_agent_loop, TOOL_HANDLERS, TOOL_DEFINITIONS
from memory.index import Memory
from tools.youtube import youtube_detect, youtube_transcript
from tools.summarize import summarize
from tools.files import write_file
from tools.skill_loader import load_skill
print('All imports OK')
print(f'Tools: {list(TOOL_HANDLERS.keys())}')
print(f'Definitions: {len(TOOL_DEFINITIONS)} tools')
"
```

Expected: All imports work, 5 tools listed, 5 definitions.

- [ ] **Step 2: Test youtube_detect end-to-end**

```bash
python -c "
from tools.youtube import youtube_detect
print(youtube_detect(text='https://youtu.be/dQw4w9WgXcQ'))
print(youtube_detect(text='https://www.youtube.com/shorts/dQw4w9WgXcQ'))
print(youtube_detect(text='random text'))
"
```

Expected: `dQw4w9WgXcQ`, `dQw4w9WgXcQ`, `None`

- [ ] **Step 3: Test load_skill end-to-end**

```bash
python -c "
from tools.skill_loader import load_skill
result = load_skill(name='youtube')
print(result[:50])
"
```

Expected: Prints first 50 chars of `skills/youtube.md`.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete manuclaw rewrite — real agent loop with dispatch map"
```
