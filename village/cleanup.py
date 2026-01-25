"""Cleanup operations."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from village.config import Config, get_config
from village.event_log import Event, append_event
from village.locks import Lock, is_active, parse_lock
from village.probes.tmux import refresh_panes
from village.status import collect_workers

logger = logging.getLogger(__name__)


def parse_lock_safe(lock_path: Path) -> Optional[Lock]:
    """
    Safely parse lock file with error handling.

    Args:
        lock_path: Path to lock file

    Returns:
        Lock object or None if corrupted
    """
    try:
        return parse_lock(lock_path)
    except Exception as e:
        logger.warning(f"Failed to parse lock {lock_path}: {e}")
        return None


@dataclass
class CleanupPlan:
    """Cleanup plan for dry-run."""

    stale_locks: list[Lock]
    locks_to_remove: list[Lock]
    orphan_worktrees: list[Path] = field(default_factory=list)
    stale_worktrees: list[Path] = field(default_factory=list)


def find_stale_locks(session_name: str, *, force_refresh: bool = False) -> list[Lock]:
    """
    Find all stale locks (panes that no longer exist).

    Args:
        session_name: Tmux session name
        force_refresh: Force fresh pane check

    Returns:
        List of STALE Lock objects
    """
    config = get_config()

    # Get all lock files
    lock_files = list(config.locks_dir.glob("*.lock"))
    locks = []

    for lock_file in lock_files:
        lock = parse_lock_safe(lock_file)
        if lock:
            locks.append(lock)

    # Evaluate which are stale
    stale = [
        lock for lock in locks if not is_active(lock, session_name, force_refresh=force_refresh)
    ]

    logger.debug(f"Found {len(stale)} stale locks out of {len(locks)} total")
    return stale


def find_orphan_worktrees(session_name: str, config: Config) -> list[Path]:
    """
    Find orphan worktrees (no matching lock).

    Args:
        session_name: Tmux session name
        config: Config object

    Returns:
        List of orphan worktree paths
    """
    from village.status import collect_workers

    # Get all active workers
    workers = collect_workers(session_name)
    active_task_ids = {worker.task_id for worker in workers}

    # Get all worktree directories
    orphan_worktrees: list[Path] = []

    if config.worktrees_dir.exists():
        worktree_dirs = [d for d in config.worktrees_dir.iterdir() if d.is_dir()]

        for worktree_dir in worktree_dirs:
            # Extract task ID from directory name
            task_id = worktree_dir.name

            # Check if task has active lock
            if task_id not in active_task_ids:
                orphan_worktrees.append(worktree_dir)
                logger.debug(f"Orphan worktree: {worktree_dir}")

    return orphan_worktrees


def plan_cleanup(
    session_name: str,
    *,
    force_refresh: bool = False,
    apply: bool = False,
) -> CleanupPlan:
    """
    Plan cleanup operation (dry-run).

    Args:
        session_name: Tmux session name
        force_refresh: Force fresh pane check
        apply: Include orphan and stale worktrees for removal

    Returns:
        CleanupPlan with stale locks and worktrees to remove
    """
    # Refresh pane cache before evaluation
    refresh_panes(session_name)

    # Find stale locks
    stale_locks = find_stale_locks(session_name, force_refresh=False)

    # Find orphan and stale worktrees (if applying)
    orphan_worktrees: list[Path] = []
    stale_worktrees: list[Path] = []

    if apply:
        config = get_config()

        orphan_worktrees = find_orphan_worktrees(session_name, config)

        # Also identify stale worktrees (have lock but no active worker)
        workers = collect_workers(session_name)
        active_task_ids = {worker.task_id for worker in workers}

        if config.worktrees_dir.exists():
            for lock in stale_locks:
                worktree_path = config.worktrees_dir / lock.task_id
                if worktree_path.exists():
                    if lock.task_id not in active_task_ids:
                        stale_worktrees.append(worktree_path)

    # Determine what to remove
    # - Orphan worktrees (if applying)
    # - Stale locks (existing behavior)
    # - Stale worktrees (if applying)

    return CleanupPlan(
        stale_locks=stale_locks,
        locks_to_remove=stale_locks,  # Default: remove only stale locks
        orphan_worktrees=orphan_worktrees,
        stale_worktrees=stale_worktrees,
    )


def execute_cleanup(
    plan: CleanupPlan,
    config: Optional[Config] = None,
) -> None:
    """
    Execute cleanup plan (remove stale locks and worktrees).

    Args:
        plan: CleanupPlan to execute
        config: Optional config (uses default if not provided)
    """
    from village.worktrees import delete_worktree

    if config is None:
        config = get_config()

    # Remove stale locks
    for lock in plan.locks_to_remove:
        lock.path.unlink()
        logger.debug(f"Removed lock: {lock.task_id}")

        # Log cleanup event
        event = Event(
            ts=datetime.now(timezone.utc).isoformat(),
            cmd="cleanup",
            task_id=lock.task_id,
            pane=lock.pane_id,
            result="ok",
        )
        append_event(event, config.village_dir)

    # Remove orphan worktrees
    for worktree_path in plan.orphan_worktrees:
        task_id = worktree_path.name
        delete_worktree(task_id, config)
        logger.debug(f"Removed orphan worktree: {worktree_path}")

    # Remove stale worktrees
    for worktree_path in plan.stale_worktrees:
        task_id = worktree_path.name
        delete_worktree(task_id, config)
        logger.debug(f"Removed stale worktree: {worktree_path}")
