"""Task hooks for customizing task management."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class TaskHookSpec:
    """Task hook specification."""

    title: str
    description: str
    issue_type: str  # bug, feature, task, epic, chore
    priority: int  # 0-4
    tags: list[str] | None = None
    parent_id: Optional[str] = None
    deps: list[str] | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []
        if self.deps is None:
            self.deps = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TaskCreated:
    """Result of task creation."""

    task_id: str
    parent_id: Optional[str]
    created_at: str
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


class TaskHooks(ABC):
    """Base class for task management customization.

    Allows domains to create and manage tasks with domain-specific
    metadata, links, and hierarchy.

    Example:
        class TradingTaskHooks(TaskHooks):
            async def on_task_created(self, task: Task) -> TaskHookSpec:
                return TaskHookSpec(
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
    async def should_create_task_hook(self, context: dict[str, Any]) -> bool:
        """Determine if task hook should fire.

        Args:
            context: Context dictionary with task info

        Returns:
            True if hook should fire
        """
        pass

    @abstractmethod
    async def create_hook_spec(self, context: dict[str, Any]) -> TaskHookSpec:
        """Create hook specification from context.

        Args:
            context: Context dictionary with task info

        Returns:
            TaskHookSpec for task creation
        """
        pass

    @abstractmethod
    async def on_task_created(self, created_task: TaskCreated, context: dict[str, Any]) -> None:
        """Handle task creation.

        Can link task to domain objects, update metadata, etc.

        Args:
            created_task: Created task
            context: Original context
        """
        pass

    @abstractmethod
    async def on_task_updated(self, task_id: str, updates: dict[str, Any]) -> None:
        """Handle task update.

        Args:
            task_id: ID of updated task
            updates: Dictionary of updates
        """
        pass


class DefaultTaskHooks(TaskHooks):
    """Default no-op task hooks."""

    async def should_create_task_hook(self, context: dict[str, Any]) -> bool:
        return False

    async def create_hook_spec(self, context: dict[str, Any]) -> TaskHookSpec:
        return TaskHookSpec(
            title="Task",
            description="",
            issue_type="task",
            priority=2,
        )

    async def on_task_created(self, created_task: TaskCreated, context: dict[str, Any]) -> None:
        pass

    async def on_task_updated(self, task_id: str, updates: dict[str, Any]) -> None:
        pass
