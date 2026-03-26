from __future__ import annotations

import re
from typing import Any


TOOL_DETECT = "youtube_detect"
TOOL_TRANSCRIPT = "youtube_transcript"
LANGUAGE_FALLBACKS = ["en", "en-US", "a.en", "fr", "fr-FR", "a.fr"]


def _ok(tool_name: str, data: Any) -> dict[str, Any]:
    return {"ok": True, "tool_name": tool_name, "data": data, "error": None}


def _err(tool_name: str, message: str) -> dict[str, Any]:
    return {"ok": False, "tool_name": tool_name, "data": None, "error": message}


def youtube_detect(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        return _err(TOOL_DETECT, "text is required")

    value = text.strip()

    patterns = [
        r"v=([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"/shorts/([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return _ok(TOOL_DETECT, {"video_id": match.group(1)})

    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return _ok(TOOL_DETECT, {"video_id": value})

    return _err(TOOL_DETECT, "no YouTube video ID found")


def youtube_transcript(video_id: str) -> dict[str, Any]:
    if not video_id or not video_id.strip():
        return _err(TOOL_TRANSCRIPT, "video_id is required")

    api_module = __import__("youtube_transcript_api")
    api = api_module.YouTubeTranscriptApi()
    normalized_id = video_id.strip()

    try:
        fetched = api.fetch(normalized_id, languages=LANGUAGE_FALLBACKS)
        transcript_text = " ".join(segment.text for segment in fetched)
        if not transcript_text.strip():
            return _err(TOOL_TRANSCRIPT, "transcript is empty")
        return _ok(TOOL_TRANSCRIPT, {"transcript_text": transcript_text})
    except Exception as exc:
        available_languages: list[str] = []
        try:
            transcript_list = api.list(normalized_id)
            available_languages = [item.language_code for item in transcript_list]
        except Exception:
            available_languages = []

        if available_languages:
            try:
                fallback_fetched = api.fetch(
                    normalized_id, languages=available_languages
                )
                fallback_text = " ".join(segment.text for segment in fallback_fetched)
                if fallback_text.strip():
                    return _ok(
                        TOOL_TRANSCRIPT,
                        {
                            "transcript_text": fallback_text,
                            "language_used": available_languages[0],
                        },
                    )
            except Exception:
                pass

        if available_languages:
            message = (
                f"failed transcript fetch with fallbacks {LANGUAGE_FALLBACKS}; "
                f"available languages: {available_languages}; cause: {exc}"
            )
        else:
            message = f"failed transcript fetch: {exc}"
        return _err(TOOL_TRANSCRIPT, message)
