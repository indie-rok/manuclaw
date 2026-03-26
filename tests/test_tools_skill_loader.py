from tools import skill_loader


def test_load_skill_success(tmp_path, monkeypatch):
    (tmp_path / "youtube.md").write_text("# YT\ncontent", encoding="utf-8")
    monkeypatch.setattr(skill_loader, "SKILLS_DIR", tmp_path)
    result = skill_loader.load_skill("youtube")
    assert result["ok"] is True
    assert result["data"]["name"] == "youtube"
    assert "content" in result["data"]["content"]


def test_load_skill_rejects_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(skill_loader, "SKILLS_DIR", tmp_path)
    assert skill_loader.load_skill("../secret")["ok"] is False
    assert skill_loader.load_skill("youtube.md")["ok"] is False
