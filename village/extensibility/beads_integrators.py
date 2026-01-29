"""Beads integration hooks for customizing task management."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class BeadSpec:
    """Beads task specification."""

    title: str
    description: str
    issue_type: str  # bug, feature, task, epic, chore
    priority: int  # 0-4
    tags: list[str] = None
    parent_id: Optional[str] = None
    deps: list[str] = None
    metadata: dict[str, Any] = None

    def __post_init__(self) -> None:
        """Initialize optional fields."""
        if self.tags is None:
            self.tags = []
        if self.deps is None:
            self.deps = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class BeadCreated:
    """Result of bead creation."""

    bead_id: str
    parent_id: Optional[str]
    created_at: str
    metadata: dict[str, Any] = None

    def __post_init__(self) -> None:
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}


class BeadsIntegrator(ABC):
    """Base class for beads task management customization.

    Allows domains to create and manage beads tasks with domain-specific
    metadata, links, and hierarchy.

    Example:
        class TradingBeadsIntegrator(BeadsIntegrator):
            async def on_task_created(self, task: Task) -> BeadSpec:
                # Create bead for trading task
                return BeadSpec(
                    title=task.title,
                    description=task.description,
                    issue_type="task",
                    priority=1,
                    metadata={
                        "strategy_path": task.strategy_folder,
                        "risk_style": task.risk_style,
                        "linked_task_id": task.task_id
                    },
                    deps=["discovered-from:parent-task-id"]
                )
    """

    @abstractmethod
    async def should_create_bead(self, context: dict[str, Any]) -> bool:
        """Determine if bead should be created.

        Args:
            context: Context dictionary with task info

        Returns:
            True if bead should be created
        """
        pass

    @abstractmethod
    async def create_bead_spec(self, context: dict[str, Any]) -> BeadSpec:
        """Create bead specification from context.

        Args:
            context: Context dictionary with task info

        Returns:
            BeadSpec for bead creation
        """
        pass

    @abstractmethod
    async def on_bead_created(self, bead: BeadCreated, context: dict[str, Any]) -> None:
        """Handle bead creation.

        Can link bead to domain objects, update metadata, etc.

        Args:
            bead: Created bead
            context: Original context
        """
        pass

    @abstractmethod
    async def on_bead_updated(self, bead_id: str, updates: dict[str, Any]) -> None:
        """Handle bead update.

        Args:
            bead_id: ID of updated bead
            updates: Dictionary of updates
        """
        pass


class DefaultBeadsIntegrator(BeadsIntegrator):
    """Default no-op beads integrator."""

    async def should_create_bead(self, context: dict[str, Any]) -> bool:
        """Never create beads."""
        return False

    async def create_bead_spec(self, context: dict[str, Any]) -> BeadSpec:
        """Return minimal spec."""
        return BeadSpec(
            title="Task",
            description="",
            issue_type="task",
            priority=2,
        )

    async def on_bead_created(self, bead: BeadCreated, context: dict[str, Any]) -> None:
        """Do nothing."""
        pass

    async def on_bead_updated(self, bead_id: str, updates: dict[str, Any]) -> None:
        """Do nothing."""
        pass
