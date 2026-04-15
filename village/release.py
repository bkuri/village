"""Release queue management for automated versioning."""

import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, cast

from village.config import get_config
from village.tasks import TaskStoreError, get_task_store

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

ChangelogCategory = Literal["Added", "Changed", "Fixed", "Breaking"]
TASK_TYPE_TO_CATEGORY: dict[str, ChangelogCategory] = {
    "bug": "Fixed",
    "feature": "Added",
    "task": "Changed",
    "chore": "Changed",
    "epic": "Changed",
}


def get_changelog_category(task_type: str, bump: BumpType) -> ChangelogCategory:
    """Map task type and bump to changelog category.

    Breaking changes (bump:major) always go to Breaking section.
    Otherwise, use task type mapping.
    """
    if bump == "major":
        return "Breaking"
    return TASK_TYPE_TO_CATEGORY.get(task_type, "Changed")


def get_task_type_from_store(task_id: str) -> str:
    """Fetch task type from the task store.

    Returns empty string if store unavailable or task not found.
    """
    try:
        store = get_task_store()
        task = store.get_task(task_id)
        if task is None:
            return ""
        return task.issue_type
    except TaskStoreError:
        return ""


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
    """Query the task store for open tasks with bump labels."""
    bump_labels = ["bump:major", "bump:minor", "bump:patch"]

    try:
        store = get_task_store()
        all_tasks = store.list_tasks(limit=10000)
    except TaskStoreError:
        logger.warning("Task store not available, skipping open task query")
        return []

    matching: list[dict[str, str]] = []
    for store_task in all_tasks:
        if store_task.status not in ("open", "draft", "in_progress"):
            continue
        for label in store_task.labels:
            if label in bump_labels:
                task_bump = label.replace("bump:", "")
                matching.append(
                    {
                        "task_id": store_task.id,
                        "title": store_task.title,
                        "bump": task_bump,
                        "status": store_task.status,
                    }
                )
                break

    seen: set[str] = set()
    unique_tasks: list[dict[str, str]] = []
    for item in matching:
        if item["task_id"] not in seen:
            seen.add(item["task_id"])
            unique_tasks.append(item)

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

    lines.append("\nRun `village builder arrange --dry-run` to preview, `village builder arrange` to apply.")

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


def compute_next_version(bump: BumpType) -> str:
    """Compute next version string by applying bump to latest git tag.

    Runs ``git describe --tags --abbrev=0`` to find the current version tag,
    strips the leading "v", parses major.minor.patch and applies the bump.

    Returns the new version WITHOUT a "v" prefix (e.g. "1.2.0").

    Raises:
        ValueError: If git describe fails for an unexpected reason.
    """
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        # No tags at all — start from scratch
        if "No names found" in stderr or "No tags can describe" in stderr or "fatal: No names" in stderr:
            defaults: dict[BumpType, str] = {
                "major": "1.0.0",
                "minor": "0.1.0",
                "patch": "0.0.1",
                "none": "0.0.0",
            }
            return defaults[bump]
        # Some other git error
        raise ValueError(f"git describe failed (rc={result.returncode}): {stderr}")

    tag = result.stdout.strip().lstrip("v")
    parts = tag.split(".")
    if len(parts) != 3:
        raise ValueError(f"Cannot parse version from tag '{result.stdout.strip()}': expected vMAJOR.MINOR.PATCH")

    try:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError as exc:
        raise ValueError(f"Non-integer version component in tag '{result.stdout.strip()}': {exc}") from exc

    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    # "none" — return current version unchanged
    return f"{major}.{minor}.{patch}"


def get_unlabeled_closed_tasks(since_version: str | None = None) -> list[dict[str, str]]:
    """Return closed tasks that have no bump:* label.

    Queries the task store for all closed tasks and returns those
    without any bump:major/minor/patch/none label.

    Gracefully returns an empty list if the store is unavailable.

    Args:
        since_version: Unused currently; reserved for future filtering.
    """
    _ = since_version

    try:
        store = get_task_store()
        all_closed = store.list_tasks(status="closed", limit=10000)
    except TaskStoreError:
        return []

    result = []
    for task in all_closed:
        has_bump = any(lbl.startswith("bump:") for lbl in task.labels)
        if not has_bump:
            result.append(
                {
                    "id": task.id,
                    "title": task.title,
                }
            )

    return result


def is_no_op_release(bumps: list[BumpType]) -> bool:
    """Return True when the aggregate of bumps results in no version change."""
    return aggregate_bumps(bumps) == "none"


def update_changelog(version: str, pending: list[PendingBump]) -> None:
    """Insert a new changelog section for *version* with categorized entries.

    Locates CHANGELOG.md relative to the git repository root.  The new
    section is inserted after the last ``## [Unreleased]`` block (i.e. just
    before the first ``## [X.Y.Z]`` line).  Tasks with bump type "none" are
    excluded from the entry.

    Entries are categorized into:
    - Added: New features
    - Changed: Enhancements, refactors
    - Fixed: Bug fixes
    - Breaking: Breaking changes (bump:major)

    Falls back to appending at the end of the file if the expected structure
    is not found, or creates the file if it doesn't exist.

    The write is performed atomically (temp-file + rename).
    """
    git_root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if git_root_result.returncode == 0:
        git_root = Path(git_root_result.stdout.strip())
    else:
        git_root = Path.cwd()

    changelog_path = git_root / "CHANGELOG.md"

    today = datetime.now().strftime("%Y-%m-%d")

    # Filter out bump:none and categorize
    non_trivial = [p for p in pending if p.bump != "none"]

    if not non_trivial:
        logger.info(f"No non-trivial changes for version {version}, skipping changelog update")
        return

    # Group by category
    categories: dict[ChangelogCategory, list[PendingBump]] = {
        "Breaking": [],
        "Added": [],
        "Changed": [],
        "Fixed": [],
    }

    for p in non_trivial:
        category = get_changelog_category(p.task_type, p.bump)
        categories[category].append(p)

    # Build the new section
    section_lines = [f"## [{version}] - {today}", ""]

    category_order: list[ChangelogCategory] = ["Breaking", "Added", "Changed", "Fixed"]
    for category in category_order:
        items = categories[category]
        if items:
            section_lines.append(f"### {category}")
            for p in items:
                title = p.title or p.task_id
                section_lines.append(f"- {title} (`{p.task_id}`)")
            section_lines.append("")

    new_section = "\n".join(section_lines) + "\n"

    if not changelog_path.exists():
        changelog_path.write_text(new_section, encoding="utf-8")
        logger.info(f"Created {changelog_path} with version {version}")
        return

    content = changelog_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    # Find the first versioned section header (## [X.Y.Z]) — insert before it
    insert_at: int | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## [") and not stripped.startswith("## [Unreleased"):
            insert_at = i
            break

    if insert_at is not None:
        lines.insert(insert_at, new_section + "\n")
    else:
        # Append at the end
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append("\n" + new_section)

    new_content = "".join(lines)

    # Atomic write via temp file + rename
    dir_ = changelog_path.parent
    with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False, suffix=".tmp", encoding="utf-8") as tmp:
        tmp.write(new_content)
        tmp_path = Path(tmp.name)

    tmp_path.replace(changelog_path)
    logger.info(f"Updated {changelog_path} with version {version}")
