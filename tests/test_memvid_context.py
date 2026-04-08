"""Tests for MemvidChatContext adapter."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from village.extensibility.context import DefaultChatContext, SessionContext
from village.extensibility.memvid_context import (
    MemvidChatContext,
    _memvid_available,
    create_memvid_context,
)


class TestMemvidAvailable:
    @patch.dict("sys.modules", {"memvid_sdk": None})
    def test_returns_false_when_sdk_not_installed(self):
        assert _memvid_available(Path("test.mv2")) is False


class TestMemvidChatContext:
    @pytest.mark.asyncio
    async def test_load_context_no_memory_file(self, tmp_path: Path):
        ctx = MemvidChatContext(tmp_path / "nonexistent.mv2")
        result = await ctx.load_context("session-1")
        assert result.session_id == "session-1"
        assert result.get("memories") is None

    @pytest.mark.asyncio
    async def test_save_context_no_pending(self, tmp_path: Path):
        ctx = MemvidChatContext(tmp_path / "memory.mv2")
        context = SessionContext(session_id="session-1")
        await ctx.save_context(context)
        assert context.get("pending_memories") is None

    @pytest.mark.asyncio
    async def test_save_context_appends_memories(self, tmp_path: Path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        ctx = MemvidChatContext(tmp_path / "memory.mv2")
        context = SessionContext(session_id="session-1")
        context.set(
            "pending_memories",
            [
                {
                    "type": "discovery",
                    "title": "Test",
                    "text": "Learned something",
                    "metadata": {},
                }
            ],
        )

        await ctx.save_context(context)
        assert context.get("pending_memories") == []

        from village.memvid_queue import read_session_memories

        path = tmp_path / "context" / "session-1" / "memories.jsonl"
        entries = read_session_memories(path)
        assert len(entries) == 1
        assert entries[0].title == "Test"

    @pytest.mark.asyncio
    async def test_enrich_context_no_entities(self, tmp_path: Path):
        ctx = MemvidChatContext(tmp_path / "memory.mv2")
        context = SessionContext(session_id="session-1")
        result = await ctx.enrich_context(context)
        assert result.get("entity_states") is None

    @pytest.mark.asyncio
    async def test_enrich_context_no_memory_file(self, tmp_path: Path):
        ctx = MemvidChatContext(tmp_path / "nonexistent.mv2")
        context = SessionContext(session_id="session-1")
        context.set("entities", ["Alice"])
        result = await ctx.enrich_context(context)
        assert result.get("entity_states") is None


class TestCreateMemvidContext:
    def test_returns_default_when_disabled(self):
        from village.config import Config, MemvidConfig

        config = MagicMock(spec=Config)
        config.memvid = MemvidConfig(enabled=False)

        result = create_memvid_context(config)
        assert isinstance(result, DefaultChatContext)

    def test_returns_default_for_non_config(self):
        result = create_memvid_context("not a config")
        assert isinstance(result, DefaultChatContext)

    def test_returns_memvid_when_enabled(self):
        from village.config import Config, MemvidConfig

        config = MagicMock(spec=Config)
        config.memvid = MemvidConfig(enabled=True, memory_path=".village/memory.mv2")
        config.village_dir = Path("/tmp/test-village")

        result = create_memvid_context(config)
        assert isinstance(result, MemvidChatContext)
