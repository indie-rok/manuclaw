from memory.index import Memory
import manuclaw as ui_module


class FakeStatus:
    def update(self, _value):
        return None


def test_rehydrate_deduplicates(tmp_path, monkeypatch):
    db_path = tmp_path / "manuclaw.db"
    memory = Memory(str(db_path))
    memory.save("conv-z", "user", "hello", iteration=0)
    memory.save(
        "conv-z", "tool_result", '{"ok": true}', iteration=1, tool_name="youtube_detect"
    )
    memory.save("conv-z", "assistant", "done", iteration=2)
    memory.close()

    app = ui_module.ManuclawApp()
    mounted = []

    monkeypatch.setattr(ui_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        app, "_mount_text", lambda text, css: mounted.append((text, css))
    )
    monkeypatch.setattr(
        app, "query_one", lambda selector, *_args, **_kwargs: FakeStatus()
    )

    app._rehydrate("conv-z")
    first_count = len(mounted)
    app._rehydrate("conv-z")
    second_count = len(mounted)

    assert first_count > 0
    assert second_count == first_count
