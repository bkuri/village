"""Write-behind queue for memvid .mv2 concurrent access."""

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MEMORY_TYPE_DISCOVERY = "discovery"
MEMORY_TYPE_PATTERN = "pattern"
MEMORY_TYPE_MISTAKE = "mistake"
MEMORY_TYPE_CONVENTION = "convention"
MEMORY_TYPE_BLOCKER = "blocker"

VALID_MEMORY_TYPES = frozenset(
    {
        MEMORY_TYPE_DISCOVERY,
        MEMORY_TYPE_PATTERN,
        MEMORY_TYPE_MISTAKE,
        MEMORY_TYPE_CONVENTION,
        MEMORY_TYPE_BLOCKER,
    }
)


@dataclass
class MemoryEntry:
    """Structured memory entry from agent session."""

    type: str
    title: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)
    entity: str = ""
    slot: str = ""
    value: str = ""

    def to_dict(self) -> dict[str, str | dict[str, str]]:
        d: dict[str, str | dict[str, str]] = {
            "type": self.type,
            "title": self.title,
            "text": self.text,
            "metadata": self.metadata,
        }
        if self.entity:
            d["entity"] = self.entity
        if self.slot:
            d["slot"] = self.slot
        if self.value:
            d["value"] = self.value
        return d

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "MemoryEntry":
        raw_meta = data.get("metadata")
        meta: dict[str, str] = {}
        if isinstance(raw_meta, dict):
            meta = {str(k): str(v) for k, v in raw_meta.items()}
        return cls(
            type=str(data.get("type", MEMORY_TYPE_DISCOVERY)),
            title=str(data.get("title", "")),
            text=str(data.get("text", "")),
            metadata=meta,
            entity=str(data.get("entity", "")),
            slot=str(data.get("slot", "")),
            value=str(data.get("value", "")),
        )

    @classmethod
    def from_jsonl(cls, line: str) -> "MemoryEntry":
        data = json.loads(line.strip())
        return cls.from_dict(data)


def get_session_memories_path(village_dir: Path, session_id: str) -> Path:
    """Get path for session's intermediate memories file."""
    context_dir = village_dir / "context" / session_id
    context_dir.mkdir(parents=True, exist_ok=True)
    return context_dir / "memories.jsonl"


def get_memvid_queue_dir(village_dir: Path) -> Path:
    """Get path for memvid write queue directory."""
    queue_dir = village_dir / "queue" / "memvid"
    queue_dir.mkdir(parents=True, exist_ok=True)
    return queue_dir


def append_memory(entry: MemoryEntry, village_dir: Path, session_id: str) -> Path:
    """Append a memory entry to session's intermediate file.

    Args:
        entry: Memory entry to append
        village_dir: Path to .village/
        session_id: Session identifier

    Returns:
        Path to the memories file
    """
    path = get_session_memories_path(village_dir, session_id)
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry.to_jsonl() + "\n")
    logger.debug("Appended memory to %s", path)
    return path


def read_session_memories(path: Path) -> list[MemoryEntry]:
    """Read all memory entries from a JSONL file.

    Args:
        path: Path to memories.jsonl

    Returns:
        List of MemoryEntry objects
    """
    entries: list[MemoryEntry] = []
    if not path.exists():
        return entries

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(MemoryEntry.from_jsonl(line))
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Skipping invalid memory entry: %s", e)
    return entries


def enqueue_session(village_dir: Path, session_id: str) -> Optional[Path]:
    """Move session memories to the write queue.

    Called when a task is closed (bd close). Moves the intermediate
    file to the queue directory for single-writer processing.

    Args:
        village_dir: Path to .village/
        session_id: Session identifier

    Returns:
        Path to queued file, or None if nothing to enqueue
    """
    source = get_session_memories_path(village_dir, session_id)

    if not source.exists():
        logger.debug("No memories to enqueue for session %s", session_id)
        return None

    if source.stat().st_size == 0:
        source.unlink()
        logger.debug("Empty memories file removed for session %s", session_id)
        return None

    queue_dir = get_memvid_queue_dir(village_dir)
    dest = queue_dir / f"{session_id}.jsonl"

    shutil.move(str(source), str(dest))
    logger.info("Enqueued memories for session %s: %s", session_id, dest)
    return dest


def get_pending_queues(village_dir: Path) -> list[Path]:
    """Get all pending queue files awaiting drain.

    Args:
        village_dir: Path to .village/

    Returns:
        List of queue file paths, sorted by modification time
    """
    queue_dir = get_memvid_queue_dir(village_dir)
    files = sorted(queue_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    return files


def drain_queue(village_dir: Path, memory_path: Path) -> dict[str, int | str]:
    """Drain all pending queue files into the .mv2 memory file.

    Single-writer operation: processes all queued JSONL files
    and merges their contents into the shared .mv2 file.

    Args:
        village_dir: Path to .village/
        memory_path: Path to .mv2 file

    Returns:
        Dict with drain statistics
    """
    pending = get_pending_queues(village_dir)

    if not pending:
        logger.debug("No pending memories to drain")
        return {"files_processed": 0, "entries_written": 0, "cards_written": 0}

    try:
        import memvid_sdk as memvid  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("memvid-sdk not installed, skipping drain")
        return {"files_processed": 0, "entries_written": 0, "cards_written": 0, "error": "memvid-sdk not installed"}

    total_entries = 0
    total_cards = 0
    files_processed = 0

    if memory_path.exists():
        mem = memvid.use("basic", str(memory_path))
    else:
        mem = memvid.create(str(memory_path), "basic")

    try:
        for queue_file in pending:
            entries = read_session_memories(queue_file)

            for entry in entries:
                try:
                    mem.put(
                        title=entry.title,
                        label=entry.type,
                        metadata=entry.metadata,
                        text=entry.text,
                        enable_embedding=True,
                    )
                    total_entries += 1

                    if entry.entity and entry.slot and entry.value:
                        mem.add_memory_cards(
                            [
                                {
                                    "entity": entry.entity,
                                    "slot": entry.slot,
                                    "value": entry.value,
                                }
                            ]
                        )
                        total_cards += 1

                except Exception as e:
                    logger.error("Failed to write memory entry: %s", e)

            queue_file.unlink()
            files_processed += 1
            logger.info("Drained queue file: %s (%d entries)", queue_file, len(entries))
    finally:
        mem.close()

    logger.info(
        "Queue drain complete: %d files, %d entries, %d cards",
        files_processed,
        total_entries,
        total_cards,
    )
    return {
        "files_processed": files_processed,
        "entries_written": total_entries,
        "cards_written": total_cards,
    }
