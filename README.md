# manuclaw

A learning project that builds a simple AI agent from scratch — a terminal UI that talks to an orchestrating gateway, which uses an LLM to plan and execute tasks.

The demo use case: paste a YouTube URL and the agent will detect the video, fetch its transcript, and summarize it using Kimi K2.5.

## How it works

```
┌─────────────┐     WebSocket      ┌──────────────────┐
│  manuclaw   │ ◄──────────────►   │     gateway      │
│   (TUI)     │   streams status   │  (orchestrator)  │
└─────────────┘                    └────────┬─────────┘
                                            │
                              ┌─────────────▼──────────────┐
                              │      agent runtime         │
                              │                            │
                              │  ┌───────────┐ ┌─────────┐ │
                              │  │  subtask  │ │ ai-loop │ │
                              │  │ generator │ │  orch   │ │
                              │  └───────────┘ └─────────┘ │
                              │        ┌─────────┐         │
                              │        │ memory  │         │
                              │        │ (SQLite)│         │
                              │        └─────────┘         │
                              └────────────────────────────┘
```

1. **You type** a YouTube URL in the TUI
2. **Gateway** receives it via WebSocket and sends it to the **subtask generator**
3. **Subtask generator** calls Kimi K2.5 (via OpenRouter) to break the task into steps based on available tools defined in `tooling.json`
4. **Gateway** executes each step using the **ai-loop-orch** tools:
   - `youtube_link_detection_tool` — extracts the video ID
   - `youtube_transcript_fetch_tool` — fetches the transcript
   - `transcript_summarizer_tool` — summarizes via Kimi K2.5
5. Each step result is saved to **memory** (SQLite)
6. The TUI shows real-time progress, color-coded by phase

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file with your OpenRouter API key:

```
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_KEY=sk-or-...
```

## Running

Terminal 1 — start the gateway:

```bash
python gateway/index.py
```

Terminal 2 — start the TUI:

```bash
python manuclaw.py
```

Then type a YouTube URL (e.g. `https://www.youtube.com/watch?v=dQw4w9WgXcQ`) and hit Enter.

## TUI keybindings

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Ctrl+B` | Toggle memory viewer (shows stored tool executions) |
| `Ctrl+C` | Quit |

## Project structure

```
manuclaw.py                    # TUI — Textual chat interface
gateway/index.py               # WebSocket server — orchestrates the pipeline
ai-loop-orch/index.py          # Tool implementations (YouTube tools)
subtask-generator/index.py     # LLM-based task planner
tooling-detection/tooling.json # Tool definitions and execution flow
memory/index.py                # SQLite memory module
```

## Tech stack

- **Textual** — TUI framework
- **Kimi K2.5** (`moonshotai/kimi-k2.5`) via OpenRouter — LLM for planning and summarization
- **websockets** — gateway ↔ TUI communication
- **youtube-transcript-api** — transcript fetching
- **SQLite** — memory storage
