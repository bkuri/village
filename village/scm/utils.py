"""Common workspace utilities for SCM backends."""

import re
from pathlib import Path
from typing import Optional


def resolve_task_id(path: Path, workspaces_dir: Path) -> Optional[str]:
    """
    Extract task_id from workspace path (Village-specific).

    Args:
        path: Workspace path
        workspaces_dir: Directory where Village workspaces are stored

    Returns:
        Task ID (e.g., "bd-a3f8") if path is in workspaces_dir,
        None otherwise
    """
    try:
        return path.relative_to(workspaces_dir).name
    except ValueError:
        return None


def generate_window_name(task_id: str, worker_num: int = 1) -> str:
    """
    Generate window name for task.

    Pattern: <agent>-<worker_num>-<task_id>
    Example: build-1-bd-a3f8

    For initial creation, uses worker_num=1 (generic "worker").

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        worker_num: Worker number (defaults to 1)

    Returns:
        Window name
    """
    return f"worker-{worker_num}-{task_id}"


def parse_window_name(window_name: str) -> dict[str, str]:
    """
    Parse window name to extract components.

    Expected pattern: <agent>-<worker_num>-<task_id>
    Example: build-1-bd-a3f8 -> {"agent": "build", "worker_num": "1", "task_id": "bd-a3f8"}

    Args:
        window_name: Window name from tmux

    Returns:
        Dictionary with keys: agent, worker_num, task_id
        Returns empty dict if pattern doesn't match
    """
    match = re.match(r"^(\w+)-(\d+)-(bd-[a-f0-9]+)$", window_name)
    if not match:
        return {}

    return {
        "agent": match.group(1),
        "worker_num": match.group(2),
        "task_id": match.group(3),
    }


def increment_task_id(task_id: str, attempt: int = 2) -> str:
    """
    Generate incremented task ID for workspace collision.

    Args:
        task_id: Original task ID (e.g., "bd-a3f8")
        attempt: Attempt number (2, 3, etc.)

    Returns:
        Incremented task ID (e.g., "bd-a3f8-2")
    """
    return f"{task_id}-{attempt}"
