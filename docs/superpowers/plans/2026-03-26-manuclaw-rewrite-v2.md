# Manuclaw Rewrite v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a full, beginner-readable rewrite that runs a real LLM tool loop, emits structured gateway events, persists loop history, and safely saves YouTube summaries.

**Architecture:** Keep a simple TUI ↔ gateway WebSocket boundary. Gateway owns a bounded `while stop_reason == "tool_use"` loop with a fixed 5-tool dispatch map and strict tool contracts. SQLite stores one row per loop message with iteration metadata so TUI can replay state after reconnect.

**Tech Stack:** Python 3.11+, Textual, websockets, httpx/OpenRouter, youtube-transcript-api, SQLite, pytest

**Spec:** `docs/superpowers/specs/2026-03-26-manuclaw-rewrite-design.md`

---

## File Responsibility Map

- `gateway/index.py` — agent loop lifecycle, event emission, tool dispatch, LLM bridge
- `memory/index.py` — SQLite schema + persistence/query API for loop replay
- `tools/youtube.py` — URL/video-id detection and transcript retrieval
- `tools/summarize.py` — transcript summarization via OpenRouter
- `tools/files.py` — safe output writes (output-only, traversal blocked)
- `tools/skill_loader.py` — controlled skill file reads (`skills/*.md`)
- `skills/youtube.md` — YouTube-specific edge cases and language fallback guidance
- `tools.json` — LLM-visible JSON schemas for the fixed 5 tools
- `manuclaw.py` — Textual UI that renders loop/tool/status events
- `tests/test_*.py` — unit/integration coverage by module

---

## Task 1: Lock contracts first (schemas, event types, DB shape)

**Files:**
- Modify: `tools.json`
- Modify: `memory/index.py`
- Modify: `gateway/index.py` (event type constants)
- Create: `tests/test_contracts.py`

- [ ] **Step 1: Write failing contract tests (TDD)**

```python
def test_tools_json_has_exactly_five_tools():
    ...

def test_memory_schema_contains_iteration_column():
    ...

def test_event_types_are_whitelisted():
    ...

def test_event_envelope_has_required_fields():
    # type, conversation_id, iteration, payload, stop_reason(optional but present when applicable)
    ...
```

- [ ] **Step 2: Run contract tests (expect FAIL)**

Run: `python -m pytest tests/test_contracts.py -v`

- [ ] **Step 3: Implement minimal contract compliance**
  - Ensure `tools.json` includes only: `youtube_detect`, `youtube_transcript`, `summarize`, `write_file`, `load_skill`
  - Add `iteration INTEGER NOT NULL` to memory table schema
- Define event constants: `user_input`, `loop_update`, `tool_start`, `tool_result`, `final_response`, `error`
- Enforce shared event envelope shape:
  - required: `type`, `conversation_id`, `iteration`, `payload`
  - required when terminal or loop status is emitted: `stop_reason`

- [ ] **Step 4: Re-run contract tests (expect PASS)**

Run: `python -m pytest tests/test_contracts.py -v`

---

## Task 2: Implement safe tool layer with uniform return shape

**Files:**
- Create or Modify: `tools/youtube.py`
- Create or Modify: `tools/summarize.py`
- Create or Modify: `tools/files.py`
- Create or Modify: `tools/skill_loader.py`
- Create: `tests/test_tools_youtube.py`
- Create: `tests/test_tools_files.py`
- Create: `tests/test_tools_skill_loader.py`
- Create: `tests/test_tools_summarize.py`
- Create or Modify: `skills/youtube.md`

- [ ] **Step 1: Write failing tests for each tool's success + error shape**

Required return contract for every tool:

```python
{
    "ok": bool,
    "tool_name": str,
    "data": dict | None,
    "error": str | None,
}
```

- [ ] **Step 2: Run tool tests (expect FAIL)**

Run: `python -m pytest tests/test_tools_*.py -v`

- [ ] **Step 3: Implement minimal tool logic + guards**
  - `youtube_detect`: parse standard/short/shorts/bare-id patterns
  - `youtube_transcript`: language fallback list from `skills/youtube.md`; when all fallback attempts fail, return structured error including available transcript languages
  - `summarize`: require non-empty input and API key; return structured error on failure
  - `write_file`: deny absolute/traversal paths; write only under `output/`; create `output/` directory when missing
  - `load_skill`: allow only `skills/<name>.md`
  - Create/validate `skills/youtube.md` with edge cases + language fallback order used by transcript behavior

- [ ] **Step 4: Re-run tool tests (expect PASS)**

Run: `python -m pytest tests/test_tools_*.py -v`

---

## Task 3: Align memory API before gateway loop integration

**Files:**
- Modify: `memory/index.py`
- Create: `tests/test_memory.py`

- [ ] **Step 1: Write failing memory tests**

Cover:
- save/retrieve by `conversation_id`
- ordering by `iteration`, then `timestamp`
- tool rows include `tool_name`
- reconnect replay query returns deterministic sequence

- [ ] **Step 2: Run memory tests (expect FAIL)**

Run: `python -m pytest tests/test_memory.py -v`

- [ ] **Step 3: Implement memory class methods**
  - `save(conversation_id, role, content, iteration, tool_name=None)`
  - `get_history(conversation_id)`
  - defensive DB init and connection close

- [ ] **Step 4: Re-run memory tests (expect PASS)**

Run: `python -m pytest tests/test_memory.py -v`

---

## Task 4: Build gateway loop lifecycle + fixed dispatch map

**Files:**
- Rewrite: `gateway/index.py`
- Create: `tests/test_gateway_loop.py`

- [ ] **Step 1: Write failing gateway loop tests**

Cover:
1. `stop_reason=tool_use` repeats loop
2. `stop_reason!=tool_use` exits with `final_response`
3. unknown tool emits structured `tool_result` error
4. `max_iterations=10` emits terminal `error`
5. event ordering: `loop_update -> tool_start -> tool_result`
6. emit/persist initial `user_input` with `iteration=0`
7. system prompt constant is present and sent in first LLM message
8. happy path includes `write_file` tool call before terminal `final_response`

- [ ] **Step 2: Run gateway tests (expect FAIL)**

Run: `python -m pytest tests/test_gateway_loop.py -v`

- [ ] **Step 3: Implement gateway loop**
  - Build conversation history and call LLM with `tools.json`
  - Enforce fixed dispatch map (no dynamic registration)
  - Emit structured events with `conversation_id` + `iteration`
  - Persist each user/assistant/tool_result entry to memory
  - Define explicit readable `SYSTEM_PROMPT` constant aligned with spec
  - Ensure YouTube happy path can invoke `write_file` before final completion

- [ ] **Step 4: Re-run gateway tests (expect PASS)**

Run: `python -m pytest tests/test_gateway_loop.py -v`

---

## Task 5: Add websocket integration acceptance test (wire-level)

**Files:**
- Create: `tests/test_gateway_websocket_integration.py`
- Modify: `gateway/index.py` (if test reveals protocol mismatch)

- [ ] **Step 1: Write failing integration test**

Cover one end-to-end conversation over WebSocket:
- first event includes `type=user_input`, `iteration=0`
- at least one tool iteration emits `loop_update -> tool_start -> tool_result`
- terminal event is `final_response` or `error`

- [ ] **Step 2: Run integration test (expect FAIL)**

Run: `python -m pytest tests/test_gateway_websocket_integration.py -v`

- [ ] **Step 3: Implement minimal fixes in gateway**

- [ ] **Step 4: Re-run integration test (expect PASS)**

Run: `python -m pytest tests/test_gateway_websocket_integration.py -v`

---

## Task 6: Redesign TUI to reflect loop visibility + reconnect rules

**Files:**
- Rewrite: `manuclaw.py`
- Create: `tests/test_tui_events.py`
- Create: `tests/test_tui_reconnect.py`

- [ ] **Step 1: Write failing TUI tests**

Cover:
- loop iteration line
- selected tool + abbreviated input
- tool result + stop reason
- final response/error blocks
- reconnect dedupe by (`conversation_id`, `iteration`, `type`, `tool_name?`)

- [ ] **Step 2: Run TUI tests (expect FAIL)**

Run: `python -m pytest tests/test_tui_events.py tests/test_tui_reconnect.py -v`

- [ ] **Step 3: Implement event-driven rendering + reconnect behavior**
  - consume event `type` field from gateway messages
  - show per-iteration status
  - display graceful connection and gateway errors
  - on reconnect, rehydrate and dedupe using DB-backed sequence keys

- [ ] **Step 4: Re-run TUI tests (expect PASS)**

Run: `python -m pytest tests/test_tui_events.py tests/test_tui_reconnect.py -v`

---

## Task 7: End-to-end verification and regression gate

**Files:**
- Modify: `README.md` (architecture + event examples)
- Delete: `subtask-generator/` (entire directory)
- Delete: `ai-loop-orch/` (entire directory)
- Delete: `tooling-detection/` (entire directory)
- Verify: entire repository

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests -v`

- [ ] **Step 1b: Remove legacy pipeline artifacts (no compatibility layer)**

Run: `rm -rf subtask-generator ai-loop-orch tooling-detection`

- [ ] **Step 1c: Verify no legacy imports/usages remain**

Run: `python -m pytest tests -k "not legacy" -v`

- [ ] **Step 2: Run lightweight type/lint/compile checks**

Run: `python -m compileall gateway memory tools manuclaw.py`

- [ ] **Step 3: Run smoke integration script**

Run:

```bash
python -c "from gateway.index import TOOL_HANDLERS; print(sorted(TOOL_HANDLERS.keys()))"
```

Expected keys (exact):

```python
['load_skill', 'summarize', 'write_file', 'youtube_detect', 'youtube_transcript']
```

- [ ] **Step 4: Update README architecture section to match new loop**

Confirm docs no longer describe subtask-generator pipeline.

- [ ] **Step 5: Enforce beginner-readability code style gates**

Checklist to apply before done:
- explicit variable names (`conversation_history`, `llm_answer`, etc.)
- comments explain *why* on non-obvious blocks
- no metaprogramming/clever abstractions in loop and tool flow
- each tool file remains top-to-bottom readable and focused

---

## Done Criteria

- Fixed 5-tool dispatch map enforced in code and tests
- Gateway loop bounded and deterministic with explicit error exits
- Event schema emitted consistently and rendered by TUI
- Memory includes iteration-aware replay for reconnect
- File writes constrained to `output/` safely
- Full tests pass and README matches implemented architecture
