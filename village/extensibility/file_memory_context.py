"""File-based memory context using MemoryStore for chat session state."""

from pathlib import Path

from village.config import Config
from village.extensibility.context import ChatContext, DefaultChatContext, SessionContext
from village.memory import MemoryStore


class FileMemoryContext(ChatContext):
    """ChatContext backed by file-based MemoryStore."""

    def __init__(self, memory_path: Path) -> None:
        self._store = MemoryStore(memory_path)

    async def load_context(self, session_id: str) -> SessionContext:
        """Load recent memories from MemoryStore into session context."""
        recent = self._store.recent(limit=10)

        memories: list[dict[str, str]] = []
        for entry in recent:
            memories.append(
                {
                    "id": entry.id,
                    "title": entry.title,
                    "text": entry.text,
                }
            )

        context = SessionContext(session_id=session_id)
        context.set("memories", memories)
        return context

    async def save_context(self, context: SessionContext) -> None:
        """Write pending memories from session context to MemoryStore."""
        pending = context.get("pending_memories", [])
        for item in pending:
            title = item.get("title", "untitled")
            text = item.get("text", "")
            tags = item.get("tags", [])
            self._store.put(title=title, text=text, tags=tags)

    async def enrich_context(self, context: SessionContext) -> SessionContext:
        """Return context unchanged."""
        return context


def create_file_memory_context(config: Config) -> ChatContext:
    """Factory: return FileMemoryContext if memory enabled, else DefaultChatContext."""
    if not config.memory.enabled:
        return DefaultChatContext()

    memory_path = Path(config.memory.store_path)
    if not memory_path.is_absolute():
        memory_path = config.village_dir / memory_path

    return FileMemoryContext(memory_path)
