"""Git worktree management."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from village.config import Config, get_config
from village.probes.tools import SubprocessError, run_command, run_command_output

logger = logging.getLogger(__name__)


@dataclass
class WorktreeInfo:
    """Git worktree information."""

    task_id: str
    path: Path
    branch: str
    commit: str


def get_worktree_path(task_id: str, config: Optional[Config] = None) -> Path:
    """
    Resolve task_id to worktree path.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        config: Optional config (uses default if not provided)

    Returns:
        Path to worktree directory
    """
    if config is None:
        config = get_config()
    return config.worktrees_dir / task_id


def create_worktree(
    task_id: str,
    session_name: str,
    config: Optional[Config] = None,
) -> tuple[Path, str]:
    """
    Create a git worktree for the given task.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        session_name: Tmux session name (for window naming)
        config: Optional config (uses default if not provided)

    Returns:
        Tuple of (worktree_path, window_name)

    Raises:
        SubprocessError: If git worktree creation fails
        RuntimeError: If git repo is dirty (prevents worktree creation)
    """
    if config is None:
        config = get_config()

    worktree_path = get_worktree_path(task_id, config)
    window_name = _generate_window_name(task_id, session_name)

    logger.debug(f"Creating worktree: {worktree_path}")

    # Check if repo is dirty first (prevents worktree creation)
    _check_git_dirty(config.git_root)

    # Create worktree with a new branch based on current HEAD
    cmd = [
        "git",
        "worktree",
        "add",
        str(worktree_path),
        "-b",
        f"worktree-{task_id}",
    ]

    try:
        result = run_command(cmd, capture=True)
        logger.debug(f"Worktree created: {result.stdout.strip()}")
    except SubprocessError as e:
        # Re-raise with more context
        logger.error(f"Failed to create worktree for {task_id}: {e}")
        raise

    return worktree_path, window_name


def delete_worktree(task_id: str, config: Optional[Config] = None) -> bool:
    """
    Delete a git worktree.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        config: Optional config (uses default if not provided)

    Returns:
        True if worktree was deleted, False if it didn't exist
    """
    if config is None:
        config = get_config()

    worktree_path = get_worktree_path(task_id, config)

    if not worktree_path.exists():
        logger.debug(f"Worktree does not exist: {worktree_path}")
        return False

    logger.debug(f"Deleting worktree: {worktree_path}")

    cmd = ["git", "worktree", "remove", str(worktree_path)]
    try:
        result = run_command(cmd, capture=True)
        logger.debug(f"Worktree removed: {result.stdout.strip()}")
        return True
    except SubprocessError as e:
        logger.error(f"Failed to remove worktree {worktree_path}: {e}")
        raise


def list_worktrees(config: Optional[Config] = None) -> list[WorktreeInfo]:
    """
    List all git worktrees.

    Args:
        config: Optional config (uses default if not provided)

    Returns:
        List of WorktreeInfo objects
    """
    if config is None:
        config = get_config()

    cmd = ["git", "worktree", "list", "--porcelain"]
    result = run_command_output(cmd)

    worktrees: list[WorktreeInfo] = []
    current_info: dict[str, str] = {}

    for line in result.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("worktree "):
            # Parse previous worktree if any
            if current_info:
                info = _parse_worktree_entry(current_info, config)
                if info:
                    worktrees.append(info)
            # Start new worktree entry
            current_info = {"path": line[len("worktree ") :].strip()}
        elif line.startswith("HEAD "):
            current_info["commit"] = line[len("HEAD ") :].strip()
        elif line.startswith("branch "):
            current_info["branch"] = line[len("branch ") :].strip()
        elif line.startswith("detached"):
            current_info["branch"] = "(detached)"

    # Parse last worktree
    if current_info:
        info = _parse_worktree_entry(current_info, config)
        if info:
            worktrees.append(info)

    return worktrees


def get_worktree_info(task_id: str, config: Optional[Config] = None) -> Optional[WorktreeInfo]:
    """
    Get information about a specific worktree.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        config: Optional config (uses default if not provided)

    Returns:
        WorktreeInfo if worktree exists, None otherwise
    """
    worktree_path = get_worktree_path(task_id, config)

    for worktree in list_worktrees(config):
        if worktree.path == worktree_path:
            return worktree

    return None


def _parse_worktree_entry(entry: dict[str, str], config: Config) -> Optional[WorktreeInfo]:
    """Parse a single worktree entry from git worktree list output."""
    path = Path(entry.get("path", ""))
    branch = entry.get("branch", "")
    commit = entry.get("commit", "")

    # Extract task_id from path if it's a village worktree
    try:
        if path.is_relative_to(config.worktrees_dir):
            task_id = path.relative_to(config.worktrees_dir).name
            return WorktreeInfo(
                task_id=task_id,
                path=path,
                branch=branch,
                commit=commit,
            )
    except ValueError:
        # Path is not relative to worktrees_dir
        pass

    return None


def _check_git_dirty(git_root: Path) -> None:
    """
    Check if git repository is dirty.

    Args:
        git_root: Path to git repository root

    Raises:
        RuntimeError: If repository has uncommitted changes
    """
    cmd = ["git", "status", "--porcelain"]
    result = run_command(cmd, capture=True, check=False)

    if result.stdout.strip():
        logger.warning(f"Git repository is dirty: {git_root}")
        raise RuntimeError(
            "Cannot create worktree: repository has uncommitted changes. "
            "Please commit or stash changes first."
        )


def _generate_window_name(task_id: str, session_name: str) -> str:
    """
    Generate window name for task.

    Pattern: <agent>-<worker_num>-<task_id>
    Example: build-1-bd-a3f8

    For initial creation, uses worker_num=1.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        session_name: Tmux session name (not used in pattern, but for consistency)

    Returns:
        Window name
    """
    # For initial creation, we can't determine agent without Beads
    # Default to generic name, caller can update if needed
    return f"worker-1-{task_id}"


def _parse_window_name(window_name: str) -> dict[str, str]:
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


def _increment_worker_num(task_id: str, attempt: int = 2) -> str:
    """
    Generate incremented task ID for worktree collision.

    Args:
        task_id: Original task ID (e.g., "bd-a3f8")
        attempt: Attempt number (2, 3, etc.)

    Returns:
        Incremented task ID (e.g., "bd-a3f8-2")
    """
    return f"{task_id}-{attempt}"
