"""Workspace management via SCM abstraction."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from village.config import Config, get_config
from village.scm import JJSCM, SCM, GitSCM, resolve_task_id

logger = logging.getLogger(__name__)  # type: ignore


@dataclass
class WorktreeInfo:
    """Workspace information with Village task metadata."""

    task_id: str
    path: Path
    branch: str
    commit: str


def get_scm(config: Optional[Config] = None) -> SCM:
    """
    Get SCM backend based on configuration.

    Args:
        config: Optional config (uses default if not provided)

    Returns:
        SCM backend instance

    Raises:
        ValueError: If scm_kind is not supported
    """
    if config is None:
        config = get_config()

    if config.scm_kind == "git":
        return GitSCM()
    elif config.scm_kind == "jj":
        return JJSCM()
    else:
        raise ValueError(f"Unsupported SCM kind: {config.scm_kind}")


def get_worktree_path(task_id: str, config: Optional[Config] = None) -> Path:
    """
    Resolve task_id to workspace path.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        config: Optional config (uses default if not provided)

    Returns:
        Path to workspace directory
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
    Create a workspace for the given task.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        session_name: Tmux session name (for window naming)
        config: Optional config (uses default if not provided)

    Returns:
        Tuple of (worktree_path, window_name)

    Raises:
        RuntimeError: If repository is dirty or workspace creation fails
    """
    from village.scm import generate_window_name

    if config is None:
        config = get_config()

    scm = get_scm(config)
    worktree_path = get_worktree_path(task_id, config)
    window_name = generate_window_name(task_id, 1)

    logger.debug(f"Creating workspace: {worktree_path}")

    if not scm.check_clean(config.git_root):
        logger.warning(f"Git repository is dirty: {config.git_root}")
        raise RuntimeError(
            "Cannot create workspace: repository has uncommitted changes. "
            "Please commit or stash changes first."
        )

    branch_name = f"worktree-{task_id}"
    scm.ensure_workspace(config.git_root, worktree_path, branch_name)

    return worktree_path, window_name


def delete_worktree(task_id: str, config: Optional[Config] = None) -> bool:
    """
    Delete a workspace.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        config: Optional config (uses default if not provided)

    Returns:
        True if workspace was deleted, False if it didn't exist
    """
    if config is None:
        config = get_config()

    scm = get_scm(config)
    worktree_path = get_worktree_path(task_id, config)

    logger.debug(f"Deleting workspace: {worktree_path}")

    return scm.remove_workspace(worktree_path)


def list_worktrees(config: Optional[Config] = None) -> list[WorktreeInfo]:
    """
    List all workspaces.

    Args:
        config: Optional config (uses default if not provided)

    Returns:
        List of WorktreeInfo objects
    """
    if config is None:
        config = get_config()

    scm = get_scm(config)
    workspaces = scm.list_workspaces(config.git_root)

    worktrees: list[WorktreeInfo] = []
    for ws in workspaces:
        task_id = resolve_task_id(ws.path, config.worktrees_dir)
        if task_id:
            worktrees.append(
                WorktreeInfo(
                    task_id=task_id,
                    path=ws.path,
                    branch=ws.branch,
                    commit=ws.commit,
                )
            )

    return worktrees


def get_worktree_info(task_id: str, config: Optional[Config] = None) -> Optional[WorktreeInfo]:
    """
    Get information about a specific workspace.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        config: Optional config (uses default if not provided)

    Returns:
        WorktreeInfo if workspace exists, None otherwise
    """
    worktree_path = get_worktree_path(task_id, config)

    for worktree in list_worktrees(config):
        if worktree.path == worktree_path:
            return worktree

    return None


def reset_worktree(task_id: str, config: Optional[Config] = None) -> None:
    """
    Reset workspace to clean state (discard all modifications).

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        config: Optional config (uses default if not provided)

    Raises:
        RuntimeError: If workspace reset fails
    """
    if config is None:
        config = get_config()

    scm = get_scm(config)
    worktree_path = get_worktree_path(task_id, config)

    logger.debug(f"Resetting workspace: {worktree_path}")
    scm.reset_workspace(worktree_path)
    logger.debug(f"Workspace reset complete: {worktree_path}")
