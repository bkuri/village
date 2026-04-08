"""Tests for memvid write-behind queue."""

import json
from pathlib import Path

from village.memvid_queue import (
    MEMORY_TYPE_CONVENTION,
    MEMORY_TYPE_DISCOVERY,
    MEMORY_TYPE_MISTAKE,
    MEMORY_TYPE_PATTERN,
    MemoryEntry,
    append_memory,
    drain_queue,
    enqueue_session,
    get_memvid_queue_dir,
    get_pending_queues,
    read_session_memories,
)


class TestMemoryEntry:
    def test_to_dict_minimal(self):
        entry = MemoryEntry(type=MEMORY_TYPE_DISCOVERY, title="Test", text="Content")
        d = entry.to_dict()
        assert d["type"] == "discovery"
        assert d["title"] == "Test"
        assert d["text"] == "Content"
        assert "entity" not in d

    def test_to_dict_with_entity(self):
        entry = MemoryEntry(
            type=MEMORY_TYPE_PATTERN,
            title="Pattern",
            text="Use dataclasses",
            entity="project",
            slot="style",
            value="dataclass",
        )
        d = entry.to_dict()
        assert d["entity"] == "project"
        assert d["slot"] == "style"
        assert d["value"] == "dataclass"

    def test_roundtrip_jsonl(self):
        entry = MemoryEntry(
            type=MEMORY_TYPE_MISTAKE,
            title="Bad approach",
            text="Don't use print()",
            metadata={"source": "bd-abc1"},
        )
        line = entry.to_jsonl()
        parsed = MemoryEntry.from_jsonl(line)
        assert parsed.type == MEMORY_TYPE_MISTAKE
        assert parsed.title == "Bad approach"
        assert parsed.text == "Don't use print()"
        assert parsed.metadata["source"] == "bd-abc1"

    def test_from_dict(self):
        data = {"type": "convention", "title": "T", "text": "X", "metadata": {}}
        entry = MemoryEntry.from_dict(data)
        assert entry.type == MEMORY_TYPE_CONVENTION


class TestAppendMemory:
    def test_append_creates_file(self, tmp_path: Path):
        entry = MemoryEntry(type=MEMORY_TYPE_DISCOVERY, title="Test", text="Content")
        path = append_memory(entry, tmp_path, "session-1")
        assert path.exists()
        entries = read_session_memories(path)
        assert len(entries) == 1
        assert entries[0].title == "Test"

    def test_append_multiple(self, tmp_path: Path):
        for i in range(3):
            entry = MemoryEntry(type=MEMORY_TYPE_DISCOVERY, title=f"Entry {i}", text=f"Content {i}")
            append_memory(entry, tmp_path, "session-1")

        path = tmp_path / "context" / "session-1" / "memories.jsonl"
        entries = read_session_memories(path)
        assert len(entries) == 3


class TestEnqueueSession:
    def test_enqueue_moves_file(self, tmp_path: Path):
        entry = MemoryEntry(type=MEMORY_TYPE_DISCOVERY, title="Test", text="Content")
        path = append_memory(entry, tmp_path, "session-1")

        result = enqueue_session(tmp_path, "session-1")
        assert result is not None
        assert result.exists()
        assert not path.exists()

        queue_dir = get_memvid_queue_dir(tmp_path)
        assert result.parent == queue_dir

    def test_enqueue_empty_file_removes(self, tmp_path: Path):
        path = tmp_path / "context" / "session-1" / "memories.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

        result = enqueue_session(tmp_path, "session-1")
        assert result is None
        assert not path.exists()

    def test_enqueue_nonexistent_returns_none(self, tmp_path: Path):
        result = enqueue_session(tmp_path, "nonexistent-session")
        assert result is None


class TestPendingQueues:
    def test_empty_queue(self, tmp_path: Path):
        pending = get_pending_queues(tmp_path)
        assert pending == []

    def test_lists_queue_files(self, tmp_path: Path):
        queue_dir = get_memvid_queue_dir(tmp_path)
        (queue_dir / "session-1.jsonl").write_text("{}", encoding="utf-8")
        (queue_dir / "session-2.jsonl").write_text("{}", encoding="utf-8")

        pending = get_pending_queues(tmp_path)
        assert len(pending) == 2


class TestDrainQueue:
    def test_drain_empty_queue(self, tmp_path: Path):
        memory_path = tmp_path / "memory.mv2"
        result = drain_queue(tmp_path, memory_path)
        assert result["files_processed"] == 0
        assert result["entries_written"] == 0

    def test_drain_without_memvid_sdk(self, tmp_path: Path):
        queue_dir = get_memvid_queue_dir(tmp_path)
        entry_json = json.dumps({"type": "discovery", "title": "T", "text": "X", "metadata": {}})
        (queue_dir / "session-1.jsonl").write_text(entry_json + "\n", encoding="utf-8")

        memory_path = tmp_path / "memory.mv2"
        result = drain_queue(tmp_path, memory_path)
        assert "error" in result
