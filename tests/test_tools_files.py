from pathlib import Path

from tools import files


def test_write_file_creates_output_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(files, "OUTPUT_DIR", tmp_path / "output")
    result = files.write_file("note.md", "hello")
    assert result["ok"] is True
    saved = Path(result["data"]["path"])
    assert saved.exists()
    assert saved.read_text(encoding="utf-8") == "hello"


def test_write_file_rejects_absolute_and_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(files, "OUTPUT_DIR", tmp_path / "output")
    assert files.write_file("/tmp/evil.md", "x")["ok"] is False
    assert files.write_file("../evil.md", "x")["ok"] is False
