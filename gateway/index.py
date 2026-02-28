"""gateway — WebSocket server that orchestrates the full agent pipeline."""

import sys
import asyncio
import importlib.util
import json
import time
from pathlib import Path
import websockets

# Resolve project root
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Import hyphen-named modules via importlib
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_subtask = _load("subtask_generator", ROOT / "subtask-generator" / "index.py")
TaskBreaker = _subtask.TaskBreaker

_orch = _load("ai_loop_orch", ROOT / "ai-loop-orch" / "index.py")
youtube_link_detection_tool = _orch.youtube_link_detection_tool
youtube_transcript_fetch_tool = _orch.youtube_transcript_fetch_tool
transcript_summarizer_tool = _orch.transcript_summarizer_tool

_memory = _load("memory_mod", ROOT / "memory" / "index.py")
MemoryModule = _memory.MemoryModule
MemoryData = _memory.MemoryData

TOOLS_PATH = ROOT / "tooling-detection" / "tooling.json"
CHAT_ID = 1
USER_ID = 1


async def run_pipeline(websocket, message: str):
    """Orchestrate the full pipeline for one user message."""
    memory = MemoryModule(user_id=USER_ID)

    async def send(text: str):
        await websocket.send(text)
        await asyncio.sleep(0.05)  # small flush gap

    # ── Step 1: break task into subtasks ──────────────────────────────────
    await send("📋 Breaking task into subtasks...")
    try:
        breaker = TaskBreaker(tools_config_path=str(TOOLS_PATH))
        plan = await breaker.break_task(message)
        steps = plan.get("execution_plan", [])
        await send(f"   Found {len(steps)} step(s) to execute.")
    except Exception as e:
        await send(f"❌ Task planning failed: {e}")
        await send("END")
        memory.close()
        return

    # ── Step 2: execute each step ─────────────────────────────────────────
    context = {"raw_input": message}  # carries outputs between steps

    for step in steps:
        tool = step.get("tool_to_use", "")
        name = step.get("subtask_name", tool)
        await send(f"🔧 Step {step['step']}: {name}")

        result = {}
        response_code = 200

        try:
            if tool == "youtube_link_detection_tool":
                result = youtube_link_detection_tool(context["raw_input"])
                if result["error"]:
                    raise ValueError(result["error"])
                context["video_id"] = result["video_id"]
                await send(f"   ✓ Video ID: {result['video_id']}")

            elif tool == "youtube_transcript_fetch_tool":
                result = youtube_transcript_fetch_tool(context["video_id"])
                if result["error"]:
                    raise ValueError(result["error"])
                context["transcript_text"] = result["transcript_text"]
                words = len(result["transcript_text"].split())
                await send(f"   ✓ Transcript fetched ({words} words)")

            elif tool == "transcript_summarizer_tool":
                await send("   ⏳ Asking Kimi K2.5 to summarize...")
                result = await transcript_summarizer_tool(context["transcript_text"])
                if result["error"]:
                    raise ValueError(result["error"])
                context["summary"] = result["summary"]
                await send("   ✓ Summary ready")

            else:
                await send(f"   ⚠ Unknown tool '{tool}', skipping.")
                continue

        except Exception as e:
            response_code = 500
            result = {"error": str(e)}
            await send(f"   ❌ Failed: {e}")

        # ── save step to memory ────────────────────────────────────────────
        memory.add_memory(MemoryData(
            chat_id=CHAT_ID,
            user_id=USER_ID,
            prompt=message,
            tool=tool,
            response=json.dumps(result),
            response_code=response_code,
            timestamp=int(time.time()),
        ))

        if response_code != 200:
            await send("⛔ Pipeline stopped due to error.")
            await send("END")
            memory.close()
            return

    # ── Step 3: send final result ─────────────────────────────────────────
    await send("💾 Results saved to memory.")
    summary = context.get("summary", "No summary produced.")
    await send(f"\n✅ Summary:\n{summary}")
    await send("END")
    memory.close()


async def handler(websocket):
    print("[gateway] client connected")
    try:
        async for message in websocket:
            print(f"[gateway] received: {message}")
            await run_pipeline(websocket, message)
    except websockets.exceptions.ConnectionClosedOK:
        print("[gateway] client disconnected")
    except websockets.exceptions.ConnectionClosedError:
        print("[gateway] client disconnected")


async def main():
    async with websockets.serve(handler, "localhost", 8765):
        print("[gateway] server started on ws://localhost:8765")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
