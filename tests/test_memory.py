"""Tests for MemoryStore — file-based markdown memory."""

from datetime import datetime
from pathlib import Path

from village.memory import MemoryEntry, MemoryStore


class TestMemoryEntry:
    def test_filename(self) -> None:
        entry = MemoryEntry(id="note-001", title="Test", text="body")
        assert entry.filename() == "note-001.md"

    def test_default_values(self) -> None:
        entry = MemoryEntry(id="note-001", title="Test", text="body")
        assert entry.tags == []
        assert entry.metadata == {}
        assert isinstance(entry.created, datetime)


class TestPutAndGet:
    def test_roundtrip(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        entry_id = store.put(
            title="Auth setup",
            text="Requires VILLAGE_AUTH_KEY env var",
            tags=["auth", "configuration"],
            metadata={"source": "https://docs.example.com/auth"},
        )

        result = store.get(entry_id)
        assert result is not None
        assert result.title == "Auth setup"
        assert "VILLAGE_AUTH_KEY" in result.text
        assert "auth" in result.tags
        assert result.metadata.get("source") == "https://docs.example.com/auth"

    def test_auto_increment_id(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        id1 = store.put(title="First", text="one")
        id2 = store.put(title="Second", text="two")
        assert id1 == "note-001"
        assert id2 == "note-002"

    def test_custom_entry_id(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        entry_id = store.put(title="Custom", text="body", entry_id="auth-setup")
        assert entry_id == "auth-setup"
        assert store.get("auth-setup") is not None

    def test_creates_directories(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "deep" / "memory")
        store.put(title="Test", text="body")
        assert (tmp_path / "deep" / "memory" / "entries").exists()


class TestFind:
    def test_finds_by_title(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Authentication setup", text="Use env vars")
        store.put(title="Git configuration", text="Set up git hooks")

        results = store.find("authentication")
        assert len(results) == 1
        assert results[0].title == "Authentication setup"

    def test_finds_by_text(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Setup", text="Requires VILLAGE_AUTH_KEY to be set")
        store.put(title="Other", text="Unrelated content")

        results = store.find("VILLAGE_AUTH_KEY")
        assert len(results) == 1
        assert results[0].title == "Setup"

    def test_finds_by_tag(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="A", text="a", tags=["auth", "setup"])
        store.put(title="B", text="b", tags=["git", "configuration"])

        results = store.find("auth")
        assert len(results) == 1
        assert results[0].id == "note-001"

    def test_respects_k_limit(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        for i in range(10):
            store.put(title=f"Auth item {i}", text=f"auth content {i}", tags=["auth"])

        results = store.find("auth", k=3)
        assert len(results) == 3

    def test_case_insensitive(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Authentication", text="body")

        results = store.find("AUTHENTICATION")
        assert len(results) == 1

    def test_no_match_returns_empty(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Something", text="body")

        results = store.find("nonexistent")
        assert results == []


class TestRecent:
    def test_ordering(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="First", text="body")
        store.put(title="Second", text="body")
        store.put(title="Third", text="body")

        results = store.recent(limit=2)
        assert len(results) == 2
        assert results[0].title == "Third"

    def test_empty_store(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        results = store.recent()
        assert results == []


class TestRelated:
    def test_finds_by_tag_overlap(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth", "env", "configuration"], entry_id="a")
        store.put(title="Git setup", text="body", tags=["git", "env", "configuration"], entry_id="b")
        store.put(title="Cooking", text="body", tags=["food", "recipe"], entry_id="c")

        results = store.related("a")
        assert len(results) == 1
        assert results[0].id == "b"

    def test_excludes_self(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth", text="body", tags=["auth"], entry_id="a")

        results = store.related("a")
        assert results == []

    def test_no_tags_returns_empty(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="No tags", text="body", entry_id="a")
        store.put(title="Also no tags", text="body", entry_id="b")

        results = store.related("a")
        assert results == []


class TestDelete:
    def test_delete_existing(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        entry_id = store.put(title="To delete", text="body")
        assert store.delete(entry_id) is True
        assert store.get(entry_id) is None

    def test_delete_nonexistent(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        assert store.delete("nonexistent") is False


class TestRebuildIndex:
    def test_generates_index(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth setup", text="body", tags=["auth", "configuration"])
        store.put(title="Git hooks", text="body", tags=["git"])

        store.rebuild_index()
        content = store.index_path.read_text(encoding="utf-8")
        assert "# Memory Index" in content
        assert "Auth setup" in content
        assert "Git hooks" in content
        assert "auth, configuration" in content

    def test_empty_store_index(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.rebuild_index()
        content = store.index_path.read_text(encoding="utf-8")
        assert "# Memory Index" in content


class TestAllEntries:
    def test_returns_all(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="A", text="a")
        store.put(title="B", text="b")
        store.put(title="C", text="c")

        entries = store.all_entries()
        assert len(entries) == 3

    def test_empty_store(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        assert store.all_entries() == []
