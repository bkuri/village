"""Abstract base class for task stores."""

from abc import ABC, abstractmethod
from typing import Optional

from village.tasks.models import (
    DependencyInfo,
    SearchResult,
    Task,
    TaskCreate,
    TaskUpdate,
)


class TaskStore(ABC):
    """Abstract interface for task persistence.

    Implementations provide concrete storage backends (JSONL file,
    external CLI, database, etc.).
    """

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the store (create files, schemas, etc.)."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the store is operational."""
        pass

    @abstractmethod
    def create_task(self, spec: TaskCreate) -> Task:
        """Create a new task.

        Args:
            spec: Task creation specification

        Returns:
            The created Task with generated ID and timestamps

        Raises:
            TaskStoreError: On creation failure
        """
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a single task by ID.

        Args:
            task_id: Task ID to look up

        Returns:
            Task object or None if not found
        """
        pass

    @abstractmethod
    def list_tasks(
        self,
        status: str | None = None,
        issue_type: str | None = None,
        label: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        """List tasks with optional filters.

        Args:
            status: Filter by status (None = all)
            issue_type: Filter by issue type (None = all)
            label: Filter by label (must match exactly, None = all)
            limit: Maximum tasks to return
            offset: Skip first N tasks

        Returns:
            List of matching tasks
        """
        pass

    @abstractmethod
    def search_tasks(
        self,
        query: str,
        status: str | None = None,
        limit: int = 20,
    ) -> SearchResult:
        """Search tasks by keyword.

        Args:
            query: Search query string
            status: Optional status filter
            limit: Maximum results

        Returns:
            SearchResult with matching tasks and total count
        """
        pass

    @abstractmethod
    def update_task(self, task_id: str, updates: TaskUpdate) -> Task:
        """Update an existing task.

        Args:
            task_id: Task ID to update
            updates: Partial update specification

        Returns:
            Updated Task

        Raises:
            TaskNotFoundError: If task does not exist
            TaskStoreError: On update failure
        """
        pass

    @abstractmethod
    def delete_task(self, task_id: str) -> None:
        """Delete a task.

        Args:
            task_id: Task ID to delete

        Raises:
            TaskNotFoundError: If task does not exist
            TaskStoreError: On deletion failure
        """
        pass

    @abstractmethod
    def get_ready_tasks(self) -> list[Task]:
        """Get tasks that are ready to work on.

        A task is ready if:
        - status is 'open' or 'draft'
        - all tasks in depends_on have status 'done' or 'closed'

        Returns:
            List of ready tasks, sorted by priority
        """
        pass

    @abstractmethod
    def get_dependencies(self, task_id: str) -> DependencyInfo:
        """Get dependency information for a task.

        Args:
            task_id: Task ID to query

        Returns:
            DependencyInfo with blocks/blocked_by task lists

        Raises:
            TaskNotFoundError: If task does not exist
        """
        pass

    @abstractmethod
    def add_dependency(
        self,
        task_id: str,
        depends_on_id: str,
        dep_type: str = "blocks",
    ) -> None:
        """Add a dependency relationship.

        Args:
            task_id: Source task ID
            depends_on_id: Target task ID
            dep_type: Type of dependency

        Raises:
            TaskNotFoundError: If either task does not exist
            TaskStoreError: On failure
        """
        pass

    @abstractmethod
    def add_label(self, task_id: str, label: str) -> None:
        """Add a label to a task.

        Args:
            task_id: Task ID
            label: Label to add

        Raises:
            TaskNotFoundError: If task does not exist
        """
        pass

    @abstractmethod
    def get_prime_context(self) -> str:
        """Get AI-optimized workflow context summary.

        Returns a concise summary of the project state suitable
        for injecting into LLM context (~50 tokens).

        Returns:
            Multi-line context string
        """
        pass

    @abstractmethod
    def count_tasks(self, status: str | None = None) -> int:
        """Count tasks with optional status filter.

        Args:
            status: Status to filter by (None = all)

        Returns:
            Task count
        """
        pass


class TaskStoreError(Exception):
    """Base exception for task store operations."""

    pass


class TaskNotFoundError(TaskStoreError):
    """Raised when a task is not found."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task not found: {task_id}")
