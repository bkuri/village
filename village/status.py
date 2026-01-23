"""Status data collection (non-mutating)."""

import logging
from dataclasses import dataclass
from typing import Optional

from village.config import get_config
from village.locks import evaluate_locks, parse_lock
from village.probes.tmux import session_exists

logger = logging.getLogger(__name__)


@dataclass
class Worker:
    """Worker status data."""

    task_id: str
    pane_id: str
    window: str
    agent: str
    claimed_at: str
    status: str


@dataclass
class Orphan:
    """Orphaned resource data."""

    type: str
    task_id: Optional[str]
    path: Optional[str]
    reason: str


@dataclass
class StatusSummary:
    """High-level status summary."""

    tmux_running: bool
    tmux_session: str
    locks_count: int
    locks_active: int
    locks_stale: int
    worktrees_count: int
    worktrees_tracked: int
    worktrees_untracked: int
    config_exists: bool
    orphans_count: int


@dataclass
class FullStatus:
    """Complete status data."""

    summary: StatusSummary
    workers: list[Worker]
    orphans: list[Orphan]


def collect_workers(session_name: str) -> list[Worker]:
    """
    Collect all workers from lock files.

    Args:
        session_name: Tmux session name

    Returns:
        List of Worker objects with ACTIVE/STALE status
    """
    config = get_config()

    if not config.locks_dir.exists():
        return []

    lock_files = list(config.locks_dir.glob("*.lock"))
    locks = []

    for lock_file in lock_files:
        lock = parse_lock(lock_file)
        if lock:
            locks.append(lock)

    if not locks:
        return []

    status_map = evaluate_locks(locks, session_name)

    workers = []
    for lock in locks:
        is_active_lock = status_map[lock.task_id]
        status = "ACTIVE" if is_active_lock else "STALE"

        worker = Worker(
            task_id=lock.task_id,
            pane_id=lock.pane_id,
            window=lock.window,
            agent=lock.agent,
            claimed_at=lock.claimed_at.isoformat(),
            status=status,
        )
        workers.append(worker)

    logger.debug(f"Collected {len(workers)} workers")
    return workers


def collect_orphans(session_name: str, workers: list[Worker]) -> list[Orphan]:
    """
    Collect all orphans (stale locks + untracked worktrees).

    Args:
        session_name: Tmux session name
        workers: List of all workers (for stale lock detection)

    Returns:
        List of Orphan objects
    """
    config = get_config()
    orphans = []

    stale_workers = [w for w in workers if w.status == "STALE"]
    for worker in stale_workers:
        orphan = Orphan(
            type="STALE_LOCK",
            task_id=worker.task_id,
            path=str(config.locks_dir / f"{worker.task_id}.lock"),
            reason="pane_not_found",
        )
        orphans.append(orphan)

    if config.worktrees_dir.exists():
        worktree_dirs = [d for d in config.worktrees_dir.iterdir() if d.is_dir()]
        tracked_task_ids = {w.task_id for w in workers}

        for worktree_dir in worktree_dirs:
            task_id = worktree_dir.name
            if task_id not in tracked_task_ids:
                orphan = Orphan(
                    type="UNTRACKED_WORKTREE",
                    task_id=None,
                    path=str(worktree_dir),
                    reason="no_matching_lock",
                )
                orphans.append(orphan)

    logger.debug(f"Collected {len(orphans)} orphans")
    return orphans


def collect_summary(
    session_name: str, workers: list[Worker], orphans: list[Orphan]
) -> StatusSummary:
    """
    Collect high-level summary.

    Args:
        session_name: Tmux session name
        workers: List of all workers
        orphans: List of all orphans

    Returns:
        StatusSummary object
    """
    config = get_config()

    tmux_running = session_exists(session_name)
    locks_count = len(workers)
    locks_active = sum(1 for w in workers if w.status == "ACTIVE")
    locks_stale = sum(1 for w in workers if w.status == "STALE")

    tracked_task_ids = {w.task_id for w in workers}

    if config.worktrees_dir.exists():
        worktree_dirs = [d for d in config.worktrees_dir.iterdir() if d.is_dir()]
        worktrees_count = len(worktree_dirs)
        worktrees_tracked = sum(
            1 for tid in tracked_task_ids if tid in {d.name for d in worktree_dirs}
        )
        worktrees_untracked = worktrees_count - worktrees_tracked
    else:
        worktrees_count = 0
        worktrees_tracked = 0
        worktrees_untracked = 0

    config_exists = config.config_exists()
    orphans_count = len(orphans)

    return StatusSummary(
        tmux_running=tmux_running,
        tmux_session=session_name,
        locks_count=locks_count,
        locks_active=locks_active,
        locks_stale=locks_stale,
        worktrees_count=worktrees_count,
        worktrees_tracked=worktrees_tracked,
        worktrees_untracked=worktrees_untracked,
        config_exists=config_exists,
        orphans_count=orphans_count,
    )


def collect_full_status(session_name: str) -> FullStatus:
    """
    Collect complete status data.

    Args:
        session_name: Tmux session name

    Returns:
        FullStatus object with summary, workers, and orphans
    """
    workers = collect_workers(session_name)
    orphans = collect_orphans(session_name, workers)
    summary = collect_summary(session_name, workers, orphans)

    return FullStatus(
        summary=summary,
        workers=workers,
        orphans=orphans,
    )
