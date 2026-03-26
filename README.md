# manuclaw

Manuclaw is a learning project that demonstrates a real LLM agent loop for a YouTube summarizer workflow.

## What it does

You paste a YouTube URL in a Textual TUI, then the gateway agent:

1. detects the video ID,
2. fetches transcript text,
3. summarizes it,
4. saves the result under `output/`.

The loop is tool-driven (`while stop_reason == "tool_use"`), not a preplanned pipeline.

## Architecture

```
┌──────────────────────┐
│   manuclaw.py (TUI)  │
└──────────┬───────────┘
           │  WebSocket
           ▼
┌──────────────────────┐
│ gateway/index.py     │
│ (Gateway)            │
└──────────┬───────────┘
           ▼
┌────────────────────────────────────┐
│ Agent Loop                         │
│ while stop_reason==tool_use        │
│ 1) call LLM(messages, tools)       │
│ 2) dispatch + execute tool call    │
│ 3) append result and continue      │
│                                    │
│ Internal components of this loop:  │
│ • Tool Dispatch Map                │
│   - youtube_detect                 │
│   - youtube_transcript             │
│   - summarize                      │
│   - write_file                     │
│   - load_skill                     │
│ • Memory (memory/index.py)         │
│   - SQLite conversation log        │
│   - conversation_id + iteration    │
└──────────┬─────────────────────────┘
           │
           ▼
┌──────────────────────┐
│ Skills (loop input)  │
│ - skills/*.md menu   │
│ - load_skill(...)    │
└──────────────────────┘
```

Gateway events use a shared JSON envelope:

```json
{
  "type": "tool_result",
  "conversation_id": "...",
  "iteration": 3,
  "payload": {},
  "stop_reason": "tool_use"
}
```

Event types:
- `user_input`
- `loop_update`
- `tool_start`
- `tool_result`
- `final_response`
- `error`

## Setup (venv)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Create `.env`:

```
OPENROUTER_KEY=sk-or-...
OPENROUTER_API_KEY=sk-or-...
```

## Run

Terminal 1:

```bash
.venv/bin/python gateway/index.py
```

Terminal 2:

```bash
.venv/bin/python manuclaw.py
```

## Tests

```bash
.venv/bin/python -m pytest tests -v
```

## Project structure

```
manuclaw.py
gateway/index.py
memory/index.py
tools/
  youtube.py
  summarize.py
  files.py
  skill_loader.py
tools.json
skills/youtube.md
tests/
```
