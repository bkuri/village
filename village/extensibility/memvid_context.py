"""Memvid-backed ChatContext for persistent cross-session agent memory."""

import logging
from pathlib import Path
from typing import Any

from village.extensibility.context import ChatContext, SessionContext

logger = logging.getLogger(__name__)


def _memvid_available(memory_path: Path) -> bool:
    """Check if memvid SDK is available and memory file exists."""
    try:
        import memvid_sdk  # type: ignore[import-not-found]  # noqa: F401

        return True
    except ImportError:
        return False


class MemvidChatContext(ChatContext):
    """ChatContext backed by memvid persistent memory.

    - load_context(): Queries memvid for relevant memories using task description
    - save_context(): Appends structured entries to intermediate JSONL (no .mv2 writes)
    - enrich_context(): Performs additional entity lookups via memvid state()

    Falls back to default behavior if memvid-sdk is not installed or memory file
    doesn't exist yet.
    """

    def __init__(self, memory_path: Path) -> None:
        """Initialize with path to .mv2 file.

        Args:
            memory_path: Path to the project's .mv2 memory file
        """
        self._memory_path = memory_path

    async def load_context(self, session_id: str) -> SessionContext:
        """Load context by querying memvid with session metadata.

        Args:
            session_id: Session identifier

        Returns:
            SessionContext with relevant memories injected
        """
        context = SessionContext(session_id=session_id)

        if not _memvid_available(self._memory_path):
            return context

        if not self._memory_path.exists():
            logger.debug(f"Memory file not found: {self._memory_path}")
            return context

        try:
            import memvid_sdk as memvid

            mem = memvid.use("basic", str(self._memory_path))
            try:
                results = mem.find(session_id, k=5)
                hits = results.get("hits", [])

                if hits:
                    memories = []
                    for hit in hits:
                        text = hit.get("text", "") if isinstance(hit, dict) else str(hit)
                        title = hit.get("title", "") if isinstance(hit, dict) else ""
                        memories.append({"title": title, "text": text})

                    context.set("memories", memories)
                    logger.debug(f"Loaded {len(memories)} memories for session {session_id}")
            finally:
                mem.close()

        except Exception as e:
            logger.warning(f"Failed to load memories from memvid: {e}")

        return context

    async def save_context(self, context: SessionContext) -> None:
        """Save context by appending to intermediate JSONL file.

        Does NOT write to .mv2 directly. The write-behind queue handles that.

        Args:
            context: SessionContext to save
        """
        from village.memvid_queue import MemoryEntry, append_memory

        village_dir = self._memory_path.parent
        session_id = context.session_id

        memories = context.get("pending_memories", [])
        if not memories:
            return

        for mem_data in memories:
            if isinstance(mem_data, dict):
                entry = MemoryEntry(
                    type=mem_data.get("type", "discovery"),
                    title=mem_data.get("title", ""),
                    text=mem_data.get("text", ""),
                    metadata=mem_data.get("metadata", {}),
                    entity=mem_data.get("entity", ""),
                    slot=mem_data.get("slot", ""),
                    value=mem_data.get("value", ""),
                )
                append_memory(entry, village_dir, session_id)

        context.set("pending_memories", [])
        logger.debug(f"Saved {len(memories)} memories for session {session_id}")

    async def enrich_context(self, context: SessionContext) -> SessionContext:
        """Enrich context with entity lookups from memvid.

        Args:
            context: SessionContext to enrich

        Returns:
            Enriched SessionContext with entity state data
        """
        if not _memvid_available(self._memory_path):
            return context

        if not self._memory_path.exists():
            return context

        entities_to_lookup = context.get("entities", [])
        if not entities_to_lookup:
            return context

        try:
            import memvid_sdk as memvid

            mem = memvid.use("basic", str(self._memory_path))
            try:
                entity_states = {}
                for entity in entities_to_lookup:
                    state = mem.state(entity)
                    if state and isinstance(state, dict):
                        slots = state.get("slots", {})
                        if slots:
                            entity_states[entity] = slots

                if entity_states:
                    context.set("entity_states", entity_states)
                    logger.debug(f"Enriched context with {len(entity_states)} entity states")
            finally:
                mem.close()

        except Exception as e:
            logger.warning(f"Failed to enrich context from memvid: {e}")

        return context


def create_memvid_context(config: Any) -> ChatContext:
    """Factory function to create MemvidChatContext from Village config.

    Returns MemvidChatContext if memvid is enabled in config,
    otherwise returns DefaultChatContext.

    Args:
        config: Village Config object

    Returns:
        ChatContext implementation
    """
    from village.config import Config

    if not isinstance(config, Config):
        from village.extensibility.context import DefaultChatContext

        return DefaultChatContext()

    if not hasattr(config, "memvid") or not config.memvid.enabled:
        from village.extensibility.context import DefaultChatContext

        return DefaultChatContext()

    memory_path = Path(config.memvid.memory_path)
    if not memory_path.is_absolute():
        memory_path = config.village_dir / memory_path

    return MemvidChatContext(memory_path)
