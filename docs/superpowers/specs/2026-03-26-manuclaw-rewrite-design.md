# Manuclaw Rewrite — Design Spec

## Overview

Full rewrite of manuclaw to align with the "How AI Agents Work" talk. The repo becomes a real, working agent that demonstrates the core patterns: while loop, dispatch map, tool calling, skills, and a gateway — applied to a YouTube summarizer use case.

## Goal

A beginner-readable agent that: receives a YouTube URL via a TUI, fetches the transcript, summarizes it, and saves the result to a file — all driven by an LLM in a real agent loop (not a hardcoded pipeline).

## Approved Direction (2026-03-26)

This redesign is approved as a **full spec-aligned rewrite** (not a partial migration).

### Decision Criteria

1. **Teaching clarity over delivery speed**
   - Prefer explicit code and obvious control flow over short-term reuse.
   - Keep module boundaries simple enough for beginners to follow line by line.
2. **Agent-loop correctness over legacy compatibility**
   - The gateway must implement the real `while stop_reason == "tool_use"` loop.
   - No fallback to the old subtask-planner pipeline.
3. **Visibility over abstraction**
   - TUI must make loop iterations and tool usage visible.
   - Avoid hiding orchestration behind framework-heavy patterns.

### Redesign Principles

- Prefer one responsibility per module (`tools/*.py`, `memory/index.py`, `gateway/index.py`, `manuclaw.py`).
- Keep tool contracts stable via `tools.json` JSON schemas.
- Make failure paths explicit (invalid URL, transcript unavailable, write errors).
- Preserve a beginner-readable narrative across the codebase: receive input → loop → call tool → feed result back → finish.

### Explicit Non-Goals

- No incremental compatibility layer for `subtask-generator/` or `ai-loop-orch/`.
- No generalized plugin architecture beyond the 5 documented tools.
- No optimization pass before correctness and readability are complete.

## Architecture

```
manuclaw.py (TUI)  ←WebSocket→  gateway/index.py  →  agent loop (while loop)
                                                         ↓
                                                    dispatch map
                                                    ├── youtube_detect
                                                    ├── youtube_transcript
                                                    ├── summarize
                                                    ├── write_file
                                                    └── load_skill
                                                         ↓
                                                    skills/youtube.md
```

- **TUI** connects to the **Gateway** via WebSocket
- **Gateway** runs the **agent loop** — a real `while stop_reason == "tool_use"` loop
- The LLM decides which tool to call at each step — no upfront planning
- **Dispatch map** routes tool calls to handler functions
- **One skill** (`youtube.md`) loaded on demand when the LLM needs YouTube knowledge
- **Memory** — SQLite, saves conversation history

The subtask planner (TaskBreaker) is deleted. The LLM IS the planner.

## File Structure

```
manuclaw.py                      # TUI (Textual framework, rewrite)
gateway/index.py                 # WebSocket server + agent loop (rewrite)
tools/
  youtube.py                     # youtube_detect + youtube_transcript
  summarize.py                   # transcript_summarizer (LLM call)
  files.py                       # write_file tool
  skill_loader.py                # load_skill tool
skills/
  youtube.md                     # YouTube edge cases, language fallbacks
memory/index.py                  # SQLite memory (rewrite to match new schema)
tools.json                       # Tool definitions (JSON schemas for the LLM)
requirements.txt                 # Dependencies
```

### What changes vs current repo

- `ai-loop-orch/` → split into `tools/` with one file per tool
- `subtask-generator/` → deleted (LLM decides in the loop)
- `tooling-detection/tooling.json` → simplified to `tools.json` (just JSON schemas, no execution_flow graph)
- `gateway/index.py` → rewritten with the real while loop + dispatch map
- `manuclaw.py` → rewritten to show loop state clearly
- `memory/index.py` → rewritten with new schema
- New: `tools/files.py`, `tools/skill_loader.py`, `skills/youtube.md`

## Core Pattern: The Agent Loop

The gateway runs this loop (same pattern as the talk):

- Start state: `conversation_history` begins with one user message and a generated `conversation_id`.
- Continue while the model returns `stop_reason == "tool_use"`.
- Hard guardrail: `max_iterations = 10` (to prevent runaway loops).
- Exit conditions:
  - `stop_reason != "tool_use"` → normal completion (`final_response`).
  - iteration limit hit or unrecoverable error → terminal `error` event and graceful stop.
- Every loop step is persisted to SQLite and emitted to the TUI.

```python
# The agent loop — same pattern from the talk
conversation_history = [{"role": "user", "content": user_message}]

while True:
    # Call the LLM with conversation history + tool definitions
    llm_answer = llm(conversation_history, tools)

    # Add the LLM's response to history
    conversation_history.append(llm_answer)

    # Check: does the LLM want to call a tool?
    if llm_answer.stop_reason != "tool_use":
        break  # Done! The LLM has its final answer.

    # Execute each tool the LLM requested
    for tool_call in llm_answer.tool_calls:
        handler = TOOL_HANDLERS[tool_call.name]  # dispatch map lookup
        result = handler(**tool_call.input)       # execute the tool
        conversation_history.append(result)       # feed result back

    # Loop continues — LLM sees the result and decides next step
```

## Dispatch Map

```python
# The dispatch map — routes tool names to handler functions
TOOL_HANDLERS = {
    "youtube_detect":     youtube_detect,      # extract video ID from URL
    "youtube_transcript": youtube_transcript,   # fetch transcript
    "summarize":          summarize,            # summarize via LLM
    "write_file":         write_file,           # save result to disk
    "load_skill":         load_skill,           # load knowledge on demand
}
```

Dispatch constraints:
- Exactly these 5 tool names are allowed.
- Unknown tool names must return a structured `tool_error` result (no crash).
- No dynamic registration, runtime plugin loading, or reflection-based dispatch.

## Tool Definitions (tools.json)

JSON schemas sent to the LLM so it knows what tools are available:

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

## Tool Contracts & Safety Rules

- All tool handlers return a JSON-serializable dictionary with:
  - `ok: bool`
  - `tool_name: str`
  - `data: object | null`
  - `error: str | null`
- On failure, tools return `ok=false` and a non-empty `error`.
- `write_file` safety:
  - Writes only inside project `output/`.
  - Rejects absolute paths.
  - Rejects path traversal (`..`).
  - Creates `output/` if missing.
- `load_skill` safety:
  - Reads only from `skills/*.md`.
  - Rejects paths or extensions outside this boundary.
- `summarize` input guard:
  - Requires non-empty text.
  - Returns explicit error when transcript is missing/empty.

## Skill: youtube.md

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

## SQLite Schema

```sql
CREATE TABLE memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,           -- 'user', 'assistant', 'tool_result'
    tool_name TEXT,               -- which tool was called (null for user/assistant text)
    content TEXT NOT NULL,        -- the message or tool result
    iteration INTEGER NOT NULL,   -- loop number for replay/debug in TUI
    timestamp INTEGER NOT NULL
);
```

Matches the conversation_history model — each row is a message in the loop.

## WebSocket Event Schema (Gateway ↔ TUI)

Each event is JSON with the shared envelope:

```json
{
  "type": "loop_update",
  "conversation_id": "uuid-or-short-id",
  "iteration": 2,
  "payload": {}
}
```

Required `type` values:
- `user_input` — TUI sent user text
- `loop_update` — gateway iteration status
- `tool_start` — tool selected and input prepared
- `tool_result` — tool returned output/error
- `final_response` — assistant final answer
- `error` — terminal unrecoverable failure

Ordering rule per iteration:
`loop_update` → `tool_start` → `tool_result` (repeat) → `final_response` or `error`.

Reconnect/idempotency rule:
- Gateway event delivery is **at-most-once** for a live socket.
- On reconnect, TUI rehydrates from SQLite history by `conversation_id` + `iteration`.
- TUI should deduplicate events by (`conversation_id`, `iteration`, `type`, `tool_name?`).

## TUI Display

The TUI should show clearly what's happening at each step:

```
┌─────────────────────────────────────────┐
│ manuclaw                                │
├─────────────────────────────────────────┤
│                                         │
│ > Summarize this video: youtu.be/abc123 │
│                                         │
│ 🔄 Loop #1                              │
│   LLM chose: youtube_detect             │
│   Input: {"text": "youtu.be/abc123"}    │
│   Result: video_id = "abc123"           │
│   stop_reason: tool_use → continuing    │
│                                         │
│ 🔄 Loop #2                              │
│   LLM chose: load_skill                 │
│   Input: {"name": "youtube"}            │
│   Result: skill loaded (YouTube Skill)  │
│   stop_reason: tool_use → continuing    │
│                                         │
│ 🔄 Loop #3                              │
│   LLM chose: youtube_transcript         │
│   Input: {"video_id": "abc123"}         │
│   Result: transcript (4,231 words)      │
│   stop_reason: tool_use → continuing    │
│                                         │
│ 🔄 Loop #4                              │
│   LLM chose: summarize                  │
│   Input: {"text": "..."}                │
│   Result: summary ready                 │
│   stop_reason: tool_use → continuing    │
│                                         │
│ 🔄 Loop #5                              │
│   LLM chose: write_file                 │
│   Input: {"filename": "abc123.md", ...} │
│   Result: saved to output/abc123.md     │
│   stop_reason: end_turn → done!         │
│                                         │
│ ✅ Summary:                              │
│ • Point 1...                            │
│ • Point 2...                            │
│ • Point 3...                            │
│                                         │
│ 💾 Saved to output/abc123.md            │
│                                         │
├─────────────────────────────────────────┤
│ > _                                     │
└─────────────────────────────────────────┘
```

Key elements visible:
- Loop iteration number
- Which tool the LLM chose
- Tool input (abbreviated)
- Tool result (abbreviated)
- stop_reason at each step (tool_use → continuing / end_turn → done!)
- When a skill gets loaded
- Final result clearly separated
- File save confirmation

## Code Style

- **Beginner-friendly variable names**: `conversation_history`, `llm_answer`, `tool_handlers` (same as the talk)
- **Comments on every block** explaining *why*, not just *what*
- **No clever abstractions** — explicit over implicit, no metaprogramming
- **Each tool file is self-contained**, readable top to bottom
- **System prompt** clearly visible and readable

## System Prompt

```
You are a helpful assistant that can process YouTube videos.
You have tools to detect YouTube URLs, fetch transcripts, summarize text, write files, and load skills.

When a user gives you a YouTube URL:
1. Detect the video ID
2. Fetch the transcript
3. Summarize it
4. Save the summary to a file in the output/ folder

Use the load_skill tool if you need specialized knowledge about YouTube.
Always save results to a file so the user has a copy.
```

## Tech Stack

- Python 3.11+
- Textual (TUI)
- websockets (gateway ↔ TUI)
- OpenRouter API (Kimi K2.5 or any model)
- youtube-transcript-api
- SQLite (memory)

## Acceptance Tests

Must pass before implementation is considered complete:

1. Agent loop executes multi-step tool sequence until final response.
2. Unknown tool name returns structured `tool_error` and loop continues or exits cleanly.
3. WebSocket event ordering matches schema and sequence rules.
4. SQLite stores all loop steps with `conversation_id`, `tool_name`, and `iteration`.
5. TUI visibly renders iteration, chosen tool, abbreviated input/result, and stop reason.
6. `write_file` blocks absolute/traversal paths and writes only under `output/`.

Verification mapping (artifact per test):
- (1) Loop sequence: captured gateway logs + final `final_response` event.
- (2) Unknown tool handling: emitted `tool_result` with `ok=false`, `tool_name`, and `error`.
- (3) Event ordering: recorded websocket event transcript for one conversation.
- (4) Persistence: DB query grouped by `conversation_id` ordered by `iteration`, `timestamp`.
- (5) TUI visibility: screenshot/snapshot showing iteration, tool, result, stop reason.
- (6) Path safety: unit tests asserting rejection of `/tmp/x.md` and `../x.md`, acceptance of `output/x.md`.

Canonical iteration example (with error path):
1. User enters URL → `user_input` emitted and persisted (`iteration=0`).
2. Loop #1 emits `loop_update`; model requests `youtube_detect`; `tool_start` then `tool_result(ok=true)`.
3. Loop #2 emits `loop_update`; model requests unknown tool `youtube_magic`; gateway emits `tool_result(ok=false,error="unknown tool")`.
4. Model receives error context and returns final explanation; gateway emits `final_response` and stops.

## What Gets Deleted

- `subtask-generator/` — entire directory (LLM decides in the loop now)
- `tooling-detection/` — replaced by simpler `tools.json`
- `ai-loop-orch/` — split into `tools/` directory
- The hardcoded pipeline in `gateway/index.py`
- The `execution_flow` concept from tooling.json
