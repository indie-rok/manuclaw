import sys
import types

from tools import youtube


def _inject_fake_module(fake_api_class):
    module = types.ModuleType("youtube_transcript_api")
    setattr(module, "YouTubeTranscriptApi", fake_api_class)
    sys.modules["youtube_transcript_api"] = module


def test_detect_standard_shorts_and_bare_id():
    assert (
        youtube.youtube_detect("https://www.youtube.com/watch?v=dQw4w9WgXcQ")["data"][
            "video_id"
        ]
        == "dQw4w9WgXcQ"
    )
    assert (
        youtube.youtube_detect("https://youtu.be/dQw4w9WgXcQ")["data"]["video_id"]
        == "dQw4w9WgXcQ"
    )
    assert (
        youtube.youtube_detect("https://www.youtube.com/shorts/dQw4w9WgXcQ")["data"][
            "video_id"
        ]
        == "dQw4w9WgXcQ"
    )
    assert youtube.youtube_detect("dQw4w9WgXcQ")["data"]["video_id"] == "dQw4w9WgXcQ"


def test_detect_failure_shape():
    result = youtube.youtube_detect("not a youtube link")
    assert result["ok"] is False
    assert result["tool_name"] == "youtube_detect"
    assert result["data"] is None
    assert isinstance(result["error"], str)


def test_transcript_success_shape():
    class Segment:
        def __init__(self, text):
            self.text = text

    class FakeApi:
        def fetch(self, video_id, languages):
            return [Segment("hello"), Segment("world")]

    _inject_fake_module(FakeApi)
    result = youtube.youtube_transcript("abc123DEF45")
    assert result == {
        "ok": True,
        "tool_name": "youtube_transcript",
        "data": {"transcript_text": "hello world"},
        "error": None,
    }


def test_transcript_failure_reports_available_languages():
    class Language:
        def __init__(self, language_code):
            self.language_code = language_code

    class FakeApi:
        def fetch(self, video_id, languages):
            raise RuntimeError("missing transcript")

        def list(self, video_id):
            return [Language("es"), Language("de")]

    _inject_fake_module(FakeApi)
    result = youtube.youtube_transcript("abc123DEF45")
    assert result["ok"] is False
    assert "available languages" in result["error"]
    assert "es" in result["error"]


def test_transcript_retries_with_available_language_list():
    class Segment:
        def __init__(self, text):
            self.text = text

    class Language:
        def __init__(self, language_code):
            self.language_code = language_code

    class FakeApi:
        def __init__(self):
            self.calls = 0

        def fetch(self, video_id, languages):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("fallback miss")
            if languages == ["en-GB"]:
                return [Segment("hello"), Segment("uk")]
            raise RuntimeError("unexpected languages")

        def list(self, video_id):
            return [Language("en-GB")]

    _inject_fake_module(FakeApi)
    result = youtube.youtube_transcript("abc123DEF45")
    assert result["ok"] is True
    assert result["data"]["transcript_text"] == "hello uk"
    assert result["data"]["language_used"] == "en-GB"
