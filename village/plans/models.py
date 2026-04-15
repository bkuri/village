"""Plan data models."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PlanState(str, Enum):
    """Plan lifecycle states."""

    DRAFT = "draft"
    APPROVED = "approved"
    LANDED = "landed"
    ABORTED = "aborted"
    PURGED = "purged"


@dataclass
class Plan:
    """A plan represents a unit of work with an objective, tasks, and lifecycle."""

    slug: str
    objective: str
    state: PlanState = PlanState.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    task_ids: list[str] = field(default_factory=list)
    worktree_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "objective": self.objective,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "task_ids": self.task_ids,
            "worktree_path": self.worktree_path,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Serialize plan to JSON string with indentation."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        return cls(
            slug=data["slug"],
            objective=data["objective"],
            state=PlanState(data["state"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            task_ids=data.get("task_ids", []),
            worktree_path=data.get("worktree_path"),
            metadata=data.get("metadata", {}),
        )
