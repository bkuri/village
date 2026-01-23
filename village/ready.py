"""Readiness assessment and decision tree."""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from village.config import get_config
from village.probes.beads import beads_available
from village.probes.tmux import session_exists
from village.probes.tools import SubprocessError, run_command_output
from village.status import collect_full_status

logger = logging.getLogger(__name__)


class ReadyState:
    """Readiness state constants."""

    NOT_READY = "not_ready"
    READY = "ready"
    READY_WITH_ACTIONS = "ready_with_actions"
    READY_NO_WORK = "ready_no_work"
    UNKNOWN = "unknown"


@dataclass
class SuggestedAction:
    """Suggested action with priority and reason."""

    action: str
    reason: str
    blocking: bool
    meta: dict[str, str] = field(default_factory=dict)


@dataclass
class ReadyAssessment:
    """Complete readiness assessment."""

    overall: str
    environment_ready: bool
    runtime_ready: bool
    work_available: str
    orphans_count: int
    stale_locks_count: int
    untracked_worktrees_count: int
    active_workers_count: int
    ready_tasks_count: Optional[int]
    suggested_actions: list[SuggestedAction]
    error: Optional[str] = None


def check_environment_ready(config: Any) -> tuple[bool, Optional[str]]:
    """
    Check if environment is ready (git repo + config exist).

    Args:
        config: Config object (to allow mocking in tests)

    Returns:
        (True, None) if ready
        (False, error_message) if not ready
    """
    if not config.config_exists():
        return False, "Village runtime not initialized"

    return True, None


def check_runtime_ready(session_name: str) -> tuple[bool, Optional[str]]:
    """
    Check if runtime is ready (tmux session exists).

    Returns:
        (True, None) if ready
        (False, error_message) if not ready
    """
    if not session_exists(session_name):
        return False, f"Tmux session '{session_name}' not running"

    return True, None


def check_work_available(beads_capable: bool) -> tuple[str, Optional[int]]:
    """
    Check if ready work is available via Beads.

    Args:
        beads_capable: True if beads is available and repo initialized

    Returns:
        ("available", count) if work found
        ("not_available", None) if no work
        ("unknown", None) if can't determine
    """
    if not beads_capable:
        return "unknown", None

    try:
        output = run_command_output(["bd", "ready"])
        if not output.strip():
            return "not_available", None

        # Count lines (each line is a ready task)
        ready_count = len([line for line in output.splitlines() if line.strip()])
        return "available", ready_count
    except SubprocessError as e:
        logger.debug(f"bd ready command failed: {e}")
        return "unknown", None


def collect_readiness_data(session_name: str, config: Any) -> dict:
    """
    Gather all data needed for readiness assessment.

    Args:
        session_name: Tmux session name
        config: Config object (to allow mocking in tests)

    Returns:
        Dict with all readiness data points
    """
    # Environment and runtime checks
    env_ready, env_error = check_environment_ready(config)
    runtime_ready, runtime_error = check_runtime_ready(session_name)

    # Beads capability
    beads_status = beads_available()
    beads_capable = beads_status.command_available and beads_status.repo_initialized

    # Work availability
    work_status, ready_count = check_work_available(beads_capable)

    # Orphans and workers (from status system)
    full_status = collect_full_status(session_name)
    orphans_count = full_status.summary.orphans_count
    active_workers_count = full_status.summary.locks_active

    # Break down orphans
    stale_locks = [o for o in full_status.orphans if o.type == "STALE_LOCK"]
    untracked_worktrees = [o for o in full_status.orphans if o.type == "UNTRACKED_WORKTREE"]
    stale_locks_count = len(stale_locks)
    untracked_worktrees_count = len(untracked_worktrees)

    return {
        "environment_ready": env_ready,
        "environment_error": env_error,
        "runtime_ready": runtime_ready,
        "runtime_error": runtime_error,
        "work_available": work_status,
        "ready_tasks_count": ready_count,
        "beads_capable": beads_capable,
        "orphans_count": orphans_count,
        "stale_locks_count": stale_locks_count,
        "untracked_worktrees_count": untracked_worktrees_count,
        "active_workers_count": active_workers_count,
    }


def generate_suggested_actions(
    environment_ready: bool,
    runtime_ready: bool,
    environment_error: Optional[str],
    runtime_error: Optional[str],
    work_available: str,
    ready_count: Optional[int],
    orphans_data: dict,
    active_workers: int,
) -> list[SuggestedAction]:
    """
    Generate suggested actions based on assessment state.

    Priority:
      1. "village up" (blocking - if environment/runtime not ready)
      2. "village cleanup" (if orphans exist)
      3. "village status --workers" (secondary - if active workers)
      4. "village queue --n N" (if work available)

    Returns:
        List of SuggestedAction in priority order
    """
    actions = []

    # 1. Blocking: environment not ready
    if not environment_ready:
        actions.append(
            SuggestedAction(
                action="village up",
                reason=environment_error or "Initialize village runtime",
                blocking=True,
            )
        )
        return actions

    # 2. Blocking: runtime not ready
    if not runtime_ready:
        actions.append(
            SuggestedAction(
                action="village up",
                reason=runtime_error or "Initialize village runtime",
                blocking=True,
            )
        )
        return actions

    # 3. Cleanup: orphans exist
    if orphans_data["orphans_count"] > 0:
        parts = []
        if orphans_data["stale_locks_count"] > 0:
            parts.append(f"{orphans_data['stale_locks_count']} stale locks")
        if orphans_data["untracked_worktrees_count"] > 0:
            parts.append(f"{orphans_data['untracked_worktrees_count']} untracked worktrees")

        actions.append(
            SuggestedAction(
                action="village cleanup",
                reason=f"Remove {', '.join(parts)}",
                blocking=True,
                meta={
                    "stale_locks": str(orphans_data["stale_locks_count"]),
                    "untracked_worktrees": str(orphans_data["untracked_worktrees_count"]),
                },
            )
        )

    # 4. Queue: work available
    if work_available == "available" and ready_count is not None:
        actions.append(
            SuggestedAction(
                action=f"village queue --n {ready_count}",
                reason=f"Queue {ready_count} ready tasks to workers",
                blocking=False,
                meta={"ready_tasks": str(ready_count)},
            )
        )

    # 5. Status: secondary (always show if workers exist)
    if active_workers > 0:
        actions.append(
            SuggestedAction(
                action="village status --workers",
                reason=f"View {active_workers} active workers",
                blocking=False,
                meta={"active_workers": str(active_workers)},
            )
        )

    return actions


def assess_readiness(session_name: str) -> ReadyAssessment:
    """
    Assess village readiness using decision tree.

    Decision logic:
      1. If not environment_ready: return NOT_READY with "village up"
      2. If not runtime_ready: return NOT_READY with "village up"
      3. Check for orphans
      4. Check work availability
      5. Determine overall state
      6. Generate suggested actions

    Args:
        session_name: Tmux session name

    Returns:
        ReadyAssessment with full assessment data
    """
    try:
        # Get config
        config = get_config()

        # Collect all data
        data = collect_readiness_data(session_name, config)

        # Generate suggested actions
        suggested_actions = generate_suggested_actions(
            environment_ready=data["environment_ready"],
            runtime_ready=data["runtime_ready"],
            environment_error=data["environment_error"],
            runtime_error=data["runtime_error"],
            work_available=data["work_available"],
            ready_count=data["ready_tasks_count"],
            orphans_data={
                "orphans_count": data["orphans_count"],
                "stale_locks_count": data["stale_locks_count"],
                "untracked_worktrees_count": data["untracked_worktrees_count"],
            },
            active_workers=data["active_workers_count"],
        )

        # Determine overall state
        overall_state = ReadyState.UNKNOWN

        if not data["environment_ready"] or not data["runtime_ready"]:
            overall_state = ReadyState.NOT_READY
        elif data["work_available"] == "available":
            if data["orphans_count"] > 0:
                overall_state = ReadyState.READY_WITH_ACTIONS
            else:
                overall_state = ReadyState.READY
        elif data["work_available"] == "not_available":
            overall_state = ReadyState.READY_NO_WORK
        elif data["orphans_count"] > 0:
            overall_state = ReadyState.READY_WITH_ACTIONS
        else:
            overall_state = ReadyState.UNKNOWN

        return ReadyAssessment(
            overall=overall_state,
            environment_ready=data["environment_ready"],
            runtime_ready=data["runtime_ready"],
            work_available=data["work_available"],
            orphans_count=data["orphans_count"],
            stale_locks_count=data["stale_locks_count"],
            untracked_worktrees_count=data["untracked_worktrees_count"],
            active_workers_count=data["active_workers_count"],
            ready_tasks_count=data["ready_tasks_count"],
            suggested_actions=suggested_actions,
            error=None,
        )
    except Exception as e:
        logger.error(f"Readiness assessment failed: {e}")
        return ReadyAssessment(
            overall=ReadyState.UNKNOWN,
            environment_ready=False,
            runtime_ready=False,
            work_available="unknown",
            orphans_count=0,
            stale_locks_count=0,
            untracked_worktrees_count=0,
            active_workers_count=0,
            ready_tasks_count=None,
            suggested_actions=[],
            error=str(e),
        )
