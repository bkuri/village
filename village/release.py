"""Release queue management for automated versioning."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, cast

from village.config import get_config

logger = logging.getLogger(__name__)

BumpType = Literal["major", "minor", "patch", "none"]
BUMP_PRIORITY = {"major": 3, "minor": 2, "patch": 1, "none": 0}
SCOPE_TO_BUMP: dict[str, BumpType] = {
    "fix": "patch",
    "feature": "minor",
    "config": "patch",
    "docs": "none",
    "test": "none",
    "refactor": "none",
}


@dataclass
class PendingBump:
    """A pending version bump from a completed task."""

    task_id: str
    bump: BumpType
    completed_at: datetime
    title: str = ""


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
    queue = load_release_queue()

    bumps = []
    for item in queue.pending:
        try:
            completed_at = datetime.fromisoformat(item["completed_at"])
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            completed_at = datetime.now(timezone.utc)

        bumps.append(
            PendingBump(
                task_id=item.get("task_id", ""),
                bump=cast(BumpType, item.get("bump", "patch")),
                completed_at=completed_at,
                title=item.get("title", ""),
            )
        )

    return bumps


def aggregate_bumps(bumps: list[BumpType]) -> BumpType:
    """Aggregate multiple bump types (highest wins)."""
    if not bumps:
        return "none"

    highest: BumpType = "none"
    for bump in bumps:
        if BUMP_PRIORITY.get(bump, 0) > BUMP_PRIORITY.get(highest, 0):
            highest = bump

    return highest


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


def get_open_bump_tasks() -> list[dict[str, str]]:
    """Query Beads for open tasks with bump labels."""
    import subprocess

    bump_labels = ["bump:major", "bump:minor", "bump:patch"]

    tasks = []
    for label in bump_labels:
        try:
            result = subprocess.run(
                ["bd", "search", "--status", "open", "--label", label, "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    if isinstance(data, list):
                        for task in data:
                            task_bump = label.replace("bump:", "")
                            tasks.append(
                                {
                                    "task_id": task.get("id", ""),
                                    "title": task.get("title", ""),
                                    "bump": task_bump,
                                    "status": task.get("status", "open"),
                                }
                            )
                except json.JSONDecodeError:
                    continue
        except FileNotFoundError:
            logger.warning("Beads CLI not found, skipping open task query")
            break

    seen = set()
    unique_tasks = []
    for task in tasks:
        if task["task_id"] not in seen:
            seen.add(task["task_id"])
            unique_tasks.append(task)

    return unique_tasks


def scope_to_bump(scope: str) -> BumpType:
    """Convert task scope to bump type."""
    result = SCOPE_TO_BUMP.get(scope, "none")
    return result


def format_release_dashboard(
    history: list[ReleaseRecord],
    pending: list[PendingBump],
    open_tasks: list[dict[str, str]],
) -> str:
    """Format release dashboard for display."""
    lines = ["# Release Status\n"]

    if history:
        lines.append("## Last Releases")
        lines.append("| Version | Date       | Bump  | Tasks |")
        lines.append("|---------|------------|-------|-------|")
        for record in history[:5]:
            date_str = record.released_at.strftime("%Y-%m-%d")
            lines.append(f"| {record.version:<7} | {date_str} | {record.aggregate_bump:<5} | {len(record.tasks)}     |")
        lines.append("")

    if pending:
        aggregate = aggregate_bumps([b.bump for b in pending])
        lines.append("## Pending Release")
        lines.append(f"Aggregate: **{aggregate}** ({len(pending)} tasks)")
        lines.append("| Task    | Bump  | Completed     |")
        lines.append("|---------|-------|---------------|")
        for bump in pending:
            ago = _format_time_ago(bump.completed_at)
            lines.append(f"| {bump.task_id:<7} | {bump.bump:<5} | {ago:<13} |")
        lines.append("")

    if open_tasks:
        lines.append("## Open Tasks with Bump Labels")
        lines.append("| Task    | Title              | Bump  | Status      |")
        lines.append("|---------|--------------------|-------|-------------|")
        for task in open_tasks[:10]:
            title = task.get("title", "")[:18]
            task_id = task.get("task_id", "")
            bump_type = task.get("bump", "")
            status = task.get("status", "")
            lines.append(f"| {task_id:<7} | {title:<18} | {bump_type:<5} | {status:<11} |")
        lines.append("")

    if not pending and not open_tasks and not history:
        lines.append("No pending releases or bump-labeled tasks.")

    lines.append("\nRun `village release --dry-run` to preview, `village release` to apply.")

    return "\n".join(lines)


def _format_time_ago(dt: datetime) -> str:
    """Format datetime as relative time."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    diff = now - dt

    if diff.days > 0:
        return f"{diff.days}d ago"
    seconds = int(diff.total_seconds())
    if seconds >= 3600:
        hours = seconds // 3600
        return f"{hours}h ago"
    if seconds >= 60:
        mins = seconds // 60
        return f"{mins}m ago"
    return "just now"
