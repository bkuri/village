"""Task data models for the built-in task store."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class TaskStatus(str, Enum):
    """Task lifecycle statuses."""

    OPEN = "open"
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CLOSED = "closed"
    DEFERRED = "deferred"


class TaskType(str, Enum):
    """Task types."""

    BUG = "bug"
    FEATURE = "feature"
    TASK = "task"
    EPIC = "epic"
    CHORE = "chore"


class DepType(str, Enum):
    """Dependency relationship types."""

    BLOCKS = "blocks"
    BLOCKED_BY = "blocked_by"
    DISCOVERED_FROM = "discovered-from"
    PARENT_CHILD = "parent-child"


TASK_FILE = "tasks.jsonl"
VERSION = 1


@dataclass
class TaskDependency:
    """A dependency relationship between two tasks."""

    task_id: str
    depends_on_id: str
    dep_type: str
    created_at: str = ""
    created_by: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class Task:
    """A single task record."""

    id: str
    title: str
    status: str = TaskStatus.OPEN.value
    priority: int = 2
    issue_type: str = TaskType.TASK.value
    description: str = ""
    estimate: int = 0
    labels: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    owner: str = ""
    created_at: str = ""
    updated_at: str = ""
    closed_at: str = ""
    closed_reason: str = ""
    created_by: str = ""

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "issue_type": self.issue_type,
            "description": self.description,
            "estimate": self.estimate,
            "labels": self.labels,
            "depends_on": self.depends_on,
            "blocks": self.blocks,
            "owner": self.owner,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "closed_at": self.closed_at,
            "closed_reason": self.closed_reason,
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """Deserialize from dict, filling defaults for missing fields."""
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            status=data.get("status", TaskStatus.OPEN.value),
            priority=data.get("priority", 2),
            issue_type=data.get("issue_type", TaskType.TASK.value),
            description=data.get("description", ""),
            estimate=data.get("estimate", 0),
            labels=data.get("labels", []),
            depends_on=data.get("depends_on", []),
            blocks=data.get("blocks", []),
            owner=data.get("owner", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            closed_at=data.get("closed_at", ""),
            closed_reason=data.get("closed_reason", ""),
            created_by=data.get("created_by", ""),
        )


@dataclass
class TaskCreate:
    """Specification for creating a new task."""

    title: str
    description: str = ""
    issue_type: str = TaskType.TASK.value
    priority: int = 2
    estimate: int = 0
    labels: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    owner: str = ""
    created_by: str = ""
    parent_id: Optional[str] = None


@dataclass
class TaskUpdate:
    """Partial update specification for a task."""

    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    issue_type: Optional[str] = None
    estimate: Optional[int] = None
    add_labels: list[str] = field(default_factory=list)
    remove_labels: list[str] = field(default_factory=list)
    add_depends_on: list[str] = field(default_factory=list)
    add_blocks: list[str] = field(default_factory=list)
    remove_depends_on: list[str] = field(default_factory=list)
    remove_blocks: list[str] = field(default_factory=list)
    closed_reason: Optional[str] = None
    owner: Optional[str] = None

    def has_changes(self) -> bool:
        """Check if any updates are specified."""
        return any(
            [
                self.title is not None,
                self.description is not None,
                self.status is not None,
                self.priority is not None,
                self.issue_type is not None,
                self.estimate is not None,
                bool(self.add_labels),
                bool(self.remove_labels),
                bool(self.add_depends_on),
                bool(self.add_blocks),
                bool(self.remove_depends_on),
                bool(self.remove_blocks),
                self.closed_reason is not None,
                self.owner is not None,
            ]
        )

    def apply(self, task: Task) -> Task:
        """Apply updates to a task, returning the modified task."""
        if self.title is not None:
            task.title = self.title
        if self.description is not None:
            task.description = self.description
        if self.status is not None:
            task.status = self.status
        if self.priority is not None:
            task.priority = self.priority
        if self.issue_type is not None:
            task.issue_type = self.issue_type
        if self.estimate is not None:
            task.estimate = self.estimate
        if self.owner is not None:
            task.owner = self.owner
        if self.closed_reason is not None:
            task.closed_reason = self.closed_reason

        for label in self.add_labels:
            if label not in task.labels:
                task.labels.append(label)
        for label in self.remove_labels:
            task.labels = [lbl for lbl in task.labels if lbl != label]

        for dep in self.add_depends_on:
            if dep not in task.depends_on:
                task.depends_on.append(dep)
        for dep in self.remove_depends_on:
            task.depends_on = [d for d in task.depends_on if d != dep]

        for blk in self.add_blocks:
            if blk not in task.blocks:
                task.blocks.append(blk)
        for blk in self.remove_blocks:
            task.blocks = [b for b in task.blocks if b != blk]

        if self.status in (TaskStatus.DONE.value, TaskStatus.CLOSED.value) and not task.closed_at:
            task.closed_at = datetime.now(timezone.utc).isoformat()

        task.updated_at = datetime.now(timezone.utc).isoformat()
        return task


@dataclass
class DependencyInfo:
    """Dependency information for a task."""

    task_id: str
    blocks: list[Task] = field(default_factory=list)
    blocked_by: list[Task] = field(default_factory=list)


@dataclass
class SearchResult:
    """Result of a task search operation."""

    tasks: list[Task]
    total: int
