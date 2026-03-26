from memory.index import Memory


def test_save_and_get_history(tmp_path):
    memory = Memory(str(tmp_path / "memory.db"))
    memory.save("conv-1", "user", "hello", iteration=0)
    memory.save("conv-1", "assistant", "hi", iteration=1)
    rows = memory.get_history("conv-1")
    memory.close()

    assert len(rows) == 2
    assert rows[0]["role"] == "user"
    assert rows[1]["role"] == "assistant"


def test_separate_conversations(tmp_path):
    memory = Memory(str(tmp_path / "memory.db"))
    memory.save("conv-1", "user", "a", iteration=0)
    memory.save("conv-2", "user", "b", iteration=0)
    rows_1 = memory.get_history("conv-1")
    rows_2 = memory.get_history("conv-2")
    memory.close()

    assert len(rows_1) == 1
    assert len(rows_2) == 1
    assert rows_1[0]["content"] == "a"
    assert rows_2[0]["content"] == "b"
