"""Cleanup operations."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from village.config import Config, get_config
from village.event_log import Event, append_event
from village.locks import Lock, is_active, parse_lock
from village.probes.tmux import refresh_panes

logger = logging.getLogger(__name__)


@dataclass
class CleanupPlan:
    """Cleanup plan for dry-run."""

    stale_locks: list[Lock]
    locks_to_remove: list[Lock]


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
        lock = parse_lock(lock_file)
        if lock:
            locks.append(lock)

    # Evaluate which are stale
    stale = [
        lock for lock in locks if not is_active(lock, session_name, force_refresh=force_refresh)
    ]

    logger.debug(f"Found {len(stale)} stale locks out of {len(locks)} total")
    return stale


def plan_cleanup(session_name: str, *, force_refresh: bool = False) -> CleanupPlan:
    """
    Plan cleanup operation (dry-run).

    Args:
        session_name: Tmux session name
        force_refresh: Force fresh pane check

    Returns:
        CleanupPlan with stale locks to remove
    """
    # Refresh pane cache before evaluation
    refresh_panes(session_name)

    # Find stale locks
    stale_locks = find_stale_locks(session_name, force_refresh=False)

    return CleanupPlan(
        stale_locks=stale_locks,
        locks_to_remove=stale_locks,  # Default: remove only stale
    )


def execute_cleanup(plan: CleanupPlan, config: Optional[Config] = None) -> None:
    """
    Execute cleanup plan (remove stale locks).

    Args:
        plan: CleanupPlan to execute
        config: Optional config (uses default if not provided)
    """
    if config is None:
        config = get_config()

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
