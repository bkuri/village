"""Built-in task store for Village.

Self-contained task management system backed by JSONL files
in .village/tasks.jsonl.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from village.tasks.file_store import FileTaskStore
from village.tasks.ids import (
    extract_task_id_from_output,
    generate_task_id,
    validate_task_id,
)
from village.tasks.models import (
    DependencyInfo,
    DepType,
    SearchResult,
    Task,
    TaskCreate,
    TaskStatus,
    TaskType,
    TaskUpdate,
)
from village.tasks.store import (
    TaskNotFoundError,
    TaskStore,
    TaskStoreError,
)

if TYPE_CHECKING:
    from village.config import Config

__all__ = [
    "FileTaskStore",
    "Task",
    "TaskCreate",
    "TaskUpdate",
    "TaskStatus",
    "TaskType",
    "TaskStore",
    "TaskStoreError",
    "TaskNotFoundError",
    "DependencyInfo",
    "DepType",
    "SearchResult",
    "generate_task_id",
    "validate_task_id",
    "extract_task_id_from_output",
    "get_task_store",
]


def get_task_store(
    tasks_file: Path | None = None,
    config: "Config | None" = None,
) -> FileTaskStore:
    """Get the default task store for the current project."""
    from village.config import get_config

    if tasks_file is None:
        cfg = config or get_config()
        tasks_file = cfg.village_dir / "tasks.jsonl"

    return FileTaskStore(tasks_file)
