"""ai-loop-orch — executes tools defined in tooling.json."""

import re
import os
import httpx
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
MODEL = "moonshotai/kimi-k2.5"


def youtube_link_detection_tool(raw_input: str) -> dict:
    """Extract a YouTube video ID from raw user input."""
    # Standard watch URL: v=XXXXXXXXXXX
    match = re.search(r"v=([A-Za-z0-9_-]{11})", raw_input)
    if match:
        return {"video_id": match.group(1), "error": None}

    # Shortened URL: youtu.be/XXXXXXXXXXX
    match = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", raw_input)
    if match:
        return {"video_id": match.group(1), "error": None}

    # Bare 11-char ID
    match = re.fullmatch(r"[A-Za-z0-9_-]{11}", raw_input.strip())
    if match:
        return {"video_id": raw_input.strip(), "error": None}

    return {"video_id": None, "error": "No valid YouTube video ID found in input."}


def youtube_transcript_fetch_tool(video_id: str, language_preference: str = "en") -> dict:
    """Fetch transcript for a YouTube video."""
    fallbacks = [language_preference, "en", "en-US", "a.en", "fr", "fr-FR", "a.fr"]
    seen = []
    langs = [l for l in fallbacks if not (l in seen or seen.append(l))]

    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=langs)
        text = " ".join(seg.text for seg in fetched)
        return {"transcript_text": text, "error": None}
    except Exception as e:
        return {"transcript_text": None, "error": str(e)}


async def transcript_summarizer_tool(transcript_text: str, system_prompt: str = None) -> dict:
    """Summarize a transcript using Kimi K2.5 via OpenRouter."""
    if not OPENROUTER_KEY:
        return {"summary": None, "error": "OPENROUTER_KEY not set in environment."}

    prompt = system_prompt or (
        "You are a concise summarizer. "
        "Summarize the following YouTube transcript in 3-5 clear bullet points. "
        "Be direct and informative."
    )

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
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": transcript_text[:12000]},  # cap tokens
                ],
                "temperature": 0.3,
            },
        )

    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return {"summary": content, "error": None}
