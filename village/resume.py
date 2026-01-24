"""Resume core logic."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from village.config import Config, get_config
from village.contracts import ContractEnvelope, generate_contract
from village.errors import InterruptedResume
from village.event_log import log_task_error, log_task_start, log_task_success
from village.locks import Lock, parse_lock, write_lock
from village.probes.beads import beads_available
from village.probes.tmux import (
    panes,
    send_keys,
)
from village.probes.tools import SubprocessError, run_command
from village.ready import assess_readiness
from village.worktrees import create_worktree, get_worktree_info

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
OPENCODE_COMMAND = "opencode"
OPENCODE_STDIN_INDICATOR = "cat <<'VILLAGE_CONTRACT_EOF'"


@dataclass
class ResumeAction:
    """Action to take for resume."""

    action: str
    reason: str
    blocking: bool
    meta: dict[str, str]


@dataclass
class ResumeResult:
    """Result of resume operation."""

    success: bool
    task_id: str
    agent: str
    worktree_path: Path
    window_name: str
    pane_id: str
    error: Optional[str] = None
    html_output: Optional[str] = None


def plan_resume(
    task_id: Optional[str] = None,
    config: Optional[Config] = None,
) -> ResumeAction:
    """
    Plan resume action using ready engine.

    Args:
        task_id: Optional task ID for explicit resume
        config: Optional config (uses default if not provided)

    Returns:
        ResumeAction with action to take
    """
    if config is None:
        config = get_config()

    # Assess readiness using ready engine
    assessment = assess_readiness(config.tmux_session)

    # Plan based on readiness
    if assessment.error:
        return ResumeAction(
            action="error",
            reason=assessment.error,
            blocking=True,
            meta={"error": assessment.error},
        )

    if not assessment.environment_ready:
        return ResumeAction(
            action="up",
            reason="Village runtime not initialized",
            blocking=True,
            meta={"command": "village up"},
        )

    if not assessment.runtime_ready:
        return ResumeAction(
            action="up",
            reason="Tmux session not running",
            blocking=True,
            meta={"command": "village up"},
        )

    # Check for stale locks
    if assessment.stale_locks_count > 0:
        return ResumeAction(
            action="cleanup",
            reason=f"{assessment.stale_locks_count} stale lock(s) found",
            blocking=False,
            meta={"command": "village cleanup"},
        )

    # If task_id provided, verify it's not already active
    if task_id:
        lock_path = config.locks_dir / f"{task_id}.lock"
        if lock_path.exists():
            lock = parse_lock(lock_path)
            if lock:
                if is_active_lock(lock, config.tmux_session):
                    return ResumeAction(
                        action="status",
                        reason=f"Task {task_id} already has ACTIVE lock",
                        blocking=False,
                        meta={"command": "village status --workers"},
                    )

    # If no task_id provided, suggest queue or status
    if not task_id:
        if assessment.ready_tasks_count and assessment.ready_tasks_count > 0:
            return ResumeAction(
                action="queue",
                reason=f"{assessment.ready_tasks_count} ready task(s) available",
                blocking=False,
                meta={"command": "village queue"},
            )
        else:
            return ResumeAction(
                action="ready",
                reason="No specific task ID provided",
                blocking=False,
                meta={"command": "village ready"},
            )

    return ResumeAction(
        action="resume",
        reason=f"Ready to resume task {task_id}",
        blocking=False,
        meta={"task_id": task_id},
    )


def suggest_next_action(config: Optional[Config] = None) -> ResumeAction:
    """
    Suggest next action when no task_id provided (no-id planner).

    Args:
        config: Optional config (uses default if not provided)

    Returns:
        ResumeAction with suggested action
    """
    return plan_resume(task_id=None, config=config)


def execute_resume(
    task_id: str,
    agent: str,
    detached: bool = False,
    dry_run: bool = False,
    config: Optional[Config] = None,
) -> ResumeResult:
    """
    Execute resume operation.

    Creates worktree, window, lock, and starts OpenCode with contract injection.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        agent: Agent name (e.g., "build", "frontend")
        detached: Run in detached mode (no tmux attach)
        dry_run: Preview mode without making changes
        config: Optional config (uses default if not provided)

    Returns:
        ResumeResult with operation details
    """
    if config is None:
        config = get_config()

    session_name = config.tmux_session
    base_task_id = task_id

    # Log task start
    log_task_start(task_id, "resume", config.village_dir)

    # Resource tracking for cleanup on interrupt
    created_resources: dict[str, object] = {
        "worktree_path": None,
        "window_name": None,
        "lock": None,
    }

    logger.info(f"Executing resume: task_id={task_id}, agent={agent}, detached={detached}")

    try:
        # Phase 1: Ensure worktree exists (with retry on collision)
        worktree_path, window_name, task_id = _ensure_worktree_exists(
            base_task_id, session_name, dry_run, config
        )
        created_resources["worktree_path"] = worktree_path

        if dry_run:
            logger.info("Dry run: would create worktree and window")
            return ResumeResult(
                success=True,
                task_id=task_id,
                agent=agent,
                worktree_path=worktree_path,
                window_name=window_name,
                pane_id="",
                error=None,
            )

        # Phase 2: Create tmux window
        pane_id = _create_resume_window(session_name, window_name, dry_run)
        created_resources["window_name"] = window_name

        if not pane_id:
            raise RuntimeError(f"Failed to create tmux window '{window_name}'")

        # Phase 3: Write lock file
        lock = Lock(
            task_id=task_id,
            pane_id=pane_id,
            window=window_name,
            agent=agent,
            claimed_at=datetime.now(),
        )
        write_lock(lock)
        created_resources["lock"] = lock

        # Phase 4: Generate and inject contract
        contract = generate_contract(task_id, agent, worktree_path, window_name, config)
        _inject_contract(session_name, pane_id, contract, dry_run)

        logger.info(f"Resume complete: task_id={task_id}, pane_id={pane_id}")

        # Log task success
        log_task_success(task_id, "resume", pane_id, config.village_dir)

        return ResumeResult(
            success=True,
            task_id=task_id,
            agent=agent,
            worktree_path=worktree_path,
            window_name=window_name,
            pane_id=pane_id,
        )

    except KeyboardInterrupt:
        logger.warning("Resume interrupted by user")
        logger.info(f"Resources remain for manual cleanup: {created_resources}")
        raise InterruptedResume()

    except Exception as e:
        logger.error(f"Resume failed: {e}")
        worktree_path = (
            created_resources["worktree_path"]
            if isinstance(created_resources["worktree_path"], Path)
            else Path("")
        )
        window_name = (
            created_resources["window_name"]
            if isinstance(created_resources["window_name"], str)
            else ""
        )

        # Log task error
        log_task_error(task_id, "resume", str(e), config.village_dir)

        return ResumeResult(
            success=False,
            task_id=task_id,
            agent=agent,
            worktree_path=worktree_path,
            window_name=window_name,
            pane_id="",
            error=str(e),
        )


def _ensure_worktree_exists(
    base_task_id: str,
    session_name: str,
    dry_run: bool,
    config: Config,
) -> tuple[Path, str, str]:
    """
    Ensure worktree exists with retry on collision.

    Args:
        base_task_id: Original task ID (e.g., "bd-a3f8")
        session_name: Tmux session name
        dry_run: Preview mode
        config: Config object

    Returns:
        Tuple of (worktree_path, window_name, final_task_id)

    Raises:
        RuntimeError: If worktree creation fails after retries
    """
    task_id = base_task_id
    max_retries = MAX_RETRIES

    for attempt in range(max_retries):
        try:
            worktree_path = config.worktrees_dir / task_id

            # Check if worktree already exists
            if worktree_path.exists() or get_worktree_info(task_id, config) is not None:
                logger.debug(f"Worktree already exists: {worktree_path}")
                window_name = _generate_resume_window(task_id, session_name)
                return worktree_path, window_name, task_id

            # Create worktree
            logger.debug(f"Creating worktree attempt {attempt + 1}/{max_retries}: {task_id}")
            worktree_path, window_name = create_worktree(task_id, session_name, config)
            logger.debug(f"Worktree created: {worktree_path}")
            return worktree_path, window_name, task_id

        except SubprocessError as e:
            error_msg = str(e).lower()

            # Check if error is collision-ish (name/path already exists)
            if any(
                keyword in error_msg
                for keyword in [
                    "already exists",
                    "path exists",
                    "worktree already exists",
                ]
            ):
                if attempt < max_retries:
                    # Increment worker number and retry
                    task_id = f"{base_task_id}-{attempt + 2}"
                    logger.debug(f"Worktree collision detected, retrying as: {task_id}")
                    continue
                else:
                    raise RuntimeError(
                        f"Worktree creation failed after {max_retries} attempts: {str(e)}"
                    )
            else:
                # Non-collision error - abort immediately
                raise RuntimeError(f"Worktree creation failed: {e}")

    # This should never be reached, but needed for type checker
    raise RuntimeError(f"Worktree creation failed after {max_retries} attempts")


def _generate_resume_window(task_id: str, session_name: str) -> str:
    """
    Generate resume window name with agent prefix.

    Pattern: <agent>-<worker_num>-<task_id>
    Example: build-1-bd-a3f8

    For initial creation, uses "worker" as agent placeholder.
    Caller can update based on Beads metadata.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        session_name: Tmux session name (not used in pattern)

    Returns:
        Window name
    """
    worker_num = 1
    base = task_id

    # Check if task_id has suffix (e.g., bd-a3f8-2)
    match = re.match(r"^(bd-[a-f0-9]+)(?:-(\d+))?$", task_id)
    if match:
        base = match.group(1)
        suffix = match.group(2)
        if suffix:
            worker_num = int(suffix)

    # Default to "worker" as agent placeholder
    # Caller should update based on actual agent from Beads
    return f"worker-{worker_num}-{base}"


def _create_resume_window(
    session_name: str,
    window_name: str,
    dry_run: bool,
) -> str:
    """
    Create tmux window for resume operation.

    Args:
        session_name: Tmux session name
        window_name: Window name (e.g., "worker-1-bd-a3f8")
        dry_run: Preview mode

    Returns:
        Pane ID (e.g., "%12") or empty string if dry_run

    Raises:
        RuntimeError: If window creation fails
    """
    if dry_run:
        logger.info(f"Dry run: would create window '{window_name}'")
        return ""

    # Create window with empty command (pane stays open)
    cmd = ["tmux", "new-window", "-t", session_name, "-n", window_name, "-d"]
    try:
        run_command(cmd, capture=True)
        logger.debug(f"Created window '{window_name}'")
    except SubprocessError as e:
        raise RuntimeError(f"Failed to create tmux window '{window_name}': {e}")

    # Get pane ID for the new window
    all_panes = panes(session_name, force_refresh=True)
    if not all_panes:
        raise RuntimeError(f"No panes found after creating window '{window_name}'")

    # Return the most recent pane (last in list)
    return list(all_panes)[-1]


def _inject_contract(
    session_name: str,
    pane_id: str,
    contract: ContractEnvelope,
    dry_run: bool,
) -> None:
    """
    Inject contract into OpenCode via stdin.

    Uses heredoc pattern to send JSON to stdin without attaching.

    Args:
        session_name: Tmux session name
        pane_id: Pane ID (e.g., "%12")
        contract: ContractEnvelope to inject
        dry_run: Preview mode
    """
    if dry_run:
        logger.info(f"Dry run: would inject contract to pane {pane_id}")
        return

    # Log warnings if any
    if contract.warnings:
        for warning in contract.warnings:
            logger.warning(f"Contract warning: {warning}")

    # Format contract as JSON
    contract_json = contract.to_json()

    # Build heredoc command: opencode <<'EOF'
    # {contract_json}
    # EOF
    heredoc_command = f"opencode <<'VILLAGE_CONTRACT_EOF'\n{contract_json}\nVILLAGE_CONTRACT_EOF"

    # Send keys to start OpenCode with stdin
    target = f"{session_name}:{pane_id}"
    send_keys(session_name, target, heredoc_command)
    send_keys(session_name, target, "Enter")

    logger.debug(f"Injected contract to pane {pane_id}")


def is_active_lock(lock: Lock, session_name: str, force_refresh: bool = False) -> bool:
    """
    Check if lock is ACTIVE (pane exists).

    Args:
        lock: Lock object to check
        session_name: Tmux session name
        force_refresh: Force fresh pane check

    Returns:
        True if ACTIVE, False if STALE
    """
    all_panes = panes(session_name, force_refresh=force_refresh)
    return lock.pane_id in all_panes


def _get_agent_from_task_id(
    task_id: str,
    default_agent: str | None = None,
) -> str:
    """
    Auto-detect agent from Beads task metadata.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        default_agent: Fallback agent if Beads unavailable

    Returns:
        Agent name (e.g., "build", "frontend")
    """
    # Try to get agent from Beads task metadata
    try:
        status = beads_available()
        if status.command_available and status.repo_initialized:
            # Try to get agent from Beads task info
            # This would require Beads to provide task metadata
            # For now, use default
            pass
    except Exception:
        logger.debug("Beads unavailable for agent detection")

    # Use default agent or fallback to "worker"
    return default_agent if default_agent else "worker"
