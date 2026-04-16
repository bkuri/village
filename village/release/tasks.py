"""Task queries for release management."""

import logging

from village.tasks import TaskStoreError, get_task_store

logger = logging.getLogger(__name__)


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
