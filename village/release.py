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

    Queries Beads for all closed tasks and for each bump category, then
    returns the difference (tasks with no bump label at all).

    Gracefully returns an empty list if ``bd`` is unavailable or returns
    non-JSON output.

    Args:
        since_version: Unused currently; reserved for future filtering.
    """
    _ = since_version  # reserved for future use

    def _bd_search(*extra_args: str) -> list[dict[str, str]] | None:
        """Run bd search with given extra args; return list or None on error."""
        try:
            res = subprocess.run(
                ["bd", "search", "--status", "closed", *extra_args, "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return None

        if res.returncode != 0:
            return []

        try:
            data = json.loads(res.stdout)
        except json.JSONDecodeError:
            return []

        if not isinstance(data, list):
            return []

        return [
            {
                "id": str(item.get("id", "")),
                "title": str(item.get("title", "")),
            }
            for item in data
            if isinstance(item, dict)
        ]

    all_closed = _bd_search()
    if all_closed is None:
        # bd not available
        return []

    labeled_ids: set[str] = set()
    for label in ("bump:major", "bump:minor", "bump:patch", "bump:none"):
        labeled = _bd_search("--label", label)
        if labeled is not None:
            for task in labeled:
                labeled_ids.add(task["id"])

    return [t for t in all_closed if t["id"] and t["id"] not in labeled_ids]


def is_no_op_release(bumps: list[BumpType]) -> bool:
    """Return True when the aggregate of bumps results in no version change."""
    return aggregate_bumps(bumps) == "none"


def update_changelog(version: str, pending: list[PendingBump]) -> None:
    """Insert a new changelog section for *version* above existing versioned sections.

    Locates CHANGELOG.md relative to the git repository root.  The new
    section is inserted after the last ``## [Unreleased]`` block (i.e. just
    before the first ``## [X.Y.Z]`` line).  Tasks with bump type "none" are
    excluded from the entry.

    Falls back to appending at the end of the file if the expected structure
    is not found, or creates the file if it doesn't exist.

    The write is performed atomically (temp-file + rename).
    """
    # Find git root
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

    # Build the new section
    section_lines = [f"## [{version}] - {today}", ""]
    non_trivial = [p for p in pending if p.bump != "none"]
    if non_trivial:
        section_lines.append("### Changed")
        for p in non_trivial:
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
