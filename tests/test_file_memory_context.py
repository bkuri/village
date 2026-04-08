"""Tests for FileMemoryContext and create_file_memory_context factory."""

from pathlib import Path

import pytest

from village.config import Config, MemoryConfig
from village.extensibility.context import DefaultChatContext, SessionContext
from village.extensibility.file_memory_context import (
    FileMemoryContext,
    create_file_memory_context,
)
from village.memory import MemoryStore


class TestFileMemoryContextLoad:
    @pytest.mark.asyncio
    async def test_load_context_empty_store(self, tmp_path: Path) -> None:
        ctx = FileMemoryContext(tmp_path)
        result = await ctx.load_context("session-1")
        assert result.session_id == "session-1"
        assert result.get("memories") == []

    @pytest.mark.asyncio
    async def test_load_context_with_existing_memories(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        store.put(title="Auth note", text="Set VILLAGE_AUTH_KEY", tags=["auth"])
        store.put(title="Git note", text="Configure git hooks", tags=["git"])

        ctx = FileMemoryContext(tmp_path)
        result = await ctx.load_context("session-1")

        memories = result.get("memories")
        assert len(memories) == 2
        titles = [m["title"] for m in memories]
        assert "Auth note" in titles
        assert "Git note" in titles


class TestFileMemoryContextSave:
    @pytest.mark.asyncio
    async def test_save_context_writes_entries(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path)
        ctx = FileMemoryContext(tmp_path)

        context = SessionContext(session_id="session-1")
        context.set(
            "pending_memories",
            [
                {"title": "Discovery", "text": "Found new API", "tags": ["api"]},
                {"title": "Fix", "text": "Patched auth bug", "tags": ["auth", "bug"]},
            ],
        )

        await ctx.save_context(context)

        entries = store.all_entries()
        assert len(entries) == 2
        assert entries[0].title == "Discovery"
        assert entries[1].title == "Fix"


class TestFileMemoryContextEnrich:
    @pytest.mark.asyncio
    async def test_enrich_returns_unchanged(self, tmp_path: Path) -> None:
        ctx = FileMemoryContext(tmp_path)
        original = SessionContext(session_id="session-1")
        original.set("key", "value")

        result = await ctx.enrich_context(original)
        assert result is original
        assert result.get("key") == "value"


class TestCreateFileMemoryContextFactory:
    def test_returns_default_when_disabled(self, tmp_path: Path) -> None:
        config = Config(
            git_root=tmp_path,
            village_dir=tmp_path / ".village",
            worktrees_dir=tmp_path / ".worktrees",
            memory=MemoryConfig(enabled=False),
        )

        result = create_file_memory_context(config)
        assert isinstance(result, DefaultChatContext)

    def test_returns_file_memory_when_enabled(self, tmp_path: Path) -> None:
        config = Config(
            git_root=tmp_path,
            village_dir=tmp_path / ".village",
            worktrees_dir=tmp_path / ".worktrees",
            memory=MemoryConfig(enabled=True, store_path=".village/memory/"),
        )

        result = create_file_memory_context(config)
        assert isinstance(result, FileMemoryContext)

    def test_relative_store_path_resolves_against_village_dir(self, tmp_path: Path) -> None:
        config = Config(
            git_root=tmp_path,
            village_dir=tmp_path / ".village",
            worktrees_dir=tmp_path / ".worktrees",
            memory=MemoryConfig(enabled=True, store_path="custom-memory/"),
        )

        result = create_file_memory_context(config)
        assert isinstance(result, FileMemoryContext)
        assert result._store.path == tmp_path / ".village" / "custom-memory/"
