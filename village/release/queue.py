"""Release queue management for automated versioning."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from village.config import get_config
from village.release.version import BumpType

logger = logging.getLogger(__name__)


@dataclass
class PendingBump:
    """A pending version bump from a completed task."""

    task_id: str
    bump: BumpType
    completed_at: datetime
    title: str = ""
    task_type: str = ""


@dataclass
class ReleaseRecord:
    """A record of a completed release."""

    version: str
    released_at: datetime
    aggregate_bump: BumpType
    tasks: list[str]
    changelog_entry: str = ""


@dataclass
class ReleaseQueue:
    """Release queue state."""

    version: int = 1
    pending: list[dict[str, str]] = field(default_factory=list)
    last_release: dict[str, str | list[str]] | None = None


def get_release_queue_path() -> Path:
    """Get path to release queue file."""
    config = get_config()
    return config.village_dir / "release_queue.json"


def get_release_history_path() -> Path:
    """Get path to release history file."""
    config = get_config()
    return config.village_dir / "release_history.jsonl"


def load_release_queue() -> ReleaseQueue:
    """Load release queue from file."""
    queue_path = get_release_queue_path()

    if not queue_path.exists():
        return ReleaseQueue()

    try:
        with open(queue_path, encoding="utf-8") as f:
            data = json.load(f)
        return ReleaseQueue(
            version=data.get("version", 1),
            pending=data.get("pending", []),
            last_release=data.get("last_release"),
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to load release queue: {e}")
        return ReleaseQueue()


def save_release_queue(queue: ReleaseQueue) -> None:
    """Save release queue to file."""
    queue_path = get_release_queue_path()
    queue_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "version": queue.version,
        "pending": queue.pending,
        "last_release": queue.last_release,
    }

    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def queue_bump(task_id: str, bump: BumpType, title: str = "") -> None:
    """Add a pending bump to the release queue."""
    queue = load_release_queue()

    pending_bump = {
        "task_id": task_id,
        "bump": bump,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
    }

    queue.pending.append(pending_bump)
    save_release_queue(queue)

    logger.info(f"Queued {bump} bump for task {task_id}")


def get_pending_bumps() -> list[PendingBump]:
    """Get all pending bumps from the queue."""
    from village.release.tasks import get_task_type_from_store

    queue = load_release_queue()

    bumps = []
    for item in queue.pending:
        try:
            completed_at = datetime.fromisoformat(item["completed_at"])
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            completed_at = datetime.now(timezone.utc)

        task_id = item.get("task_id", "")
        task_type = get_task_type_from_store(task_id) if task_id else ""

        bumps.append(
            PendingBump(
                task_id=task_id,
                bump=cast(BumpType, item.get("bump", "patch")),
                completed_at=completed_at,
                title=item.get("title", ""),
                task_type=task_type,
            )
        )

    return bumps


def clear_pending_bumps() -> list[str]:
    """Clear all pending bumps and return task IDs."""
    queue = load_release_queue()
    task_ids = [item.get("task_id", "") for item in queue.pending]
    queue.pending = []
    save_release_queue(queue)

    logger.info(f"Cleared {len(task_ids)} pending bumps")
    return task_ids


def record_release(record: ReleaseRecord) -> None:
    """Record a release to history."""
    history_path = get_release_history_path()
    history_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "version": record.version,
        "released_at": record.released_at.isoformat(),
        "aggregate_bump": record.aggregate_bump,
        "tasks": record.tasks,
        "changelog_entry": record.changelog_entry,
    }

    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")

    queue = load_release_queue()
    queue.last_release = {
        "version": record.version,
        "released_at": record.released_at.isoformat(),
        "tasks": record.tasks,
    }
    save_release_queue(queue)

    logger.info(f"Recorded release {record.version}")


def get_release_history(limit: int = 10) -> list[ReleaseRecord]:
    """Get recent release history."""
    history_path = get_release_history_path()

    if not history_path.exists():
        return []

    records = []
    try:
        with open(history_path, encoding="utf-8") as f:
            lines = f.readlines()

        for line in reversed(lines[-limit:]):
            try:
                data = json.loads(line.strip())
                released_at = datetime.fromisoformat(data["released_at"])
                if released_at.tzinfo is None:
                    released_at = released_at.replace(tzinfo=timezone.utc)

                records.append(
                    ReleaseRecord(
                        version=data.get("version", "0.0.0"),
                        released_at=released_at,
                        aggregate_bump=data.get("aggregate_bump", "patch"),
                        tasks=data.get("tasks", []),
                        changelog_entry=data.get("changelog_entry", ""),
                    )
                )
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to parse release history entry: {e}")
                continue

        return records
    except IOError as e:
        logger.warning(f"Failed to read release history: {e}")
        return []
