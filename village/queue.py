"""Queue scheduler for executing ready tasks from Beads."""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from village.config import Config, get_config
from village.conflict_detection import (
    WorkerInfo,
    detect_file_conflicts,
    render_conflict_report,
)
from village.event_log import is_task_recent, log_task_start, read_events
from village.locks import Lock, parse_lock
from village.probes.beads import beads_available
from village.probes.tools import SubprocessError, run_command_output
from village.resume import ResumeResult, execute_resume
from village.state_machine import TaskState, TaskStateMachine

logger = logging.getLogger(__name__)


@dataclass
class QueueTask:
    """Single task from queue."""

    task_id: str
    agent: str
    agent_metadata: dict[str, str] = field(default_factory=dict)
    skip_reason: Optional[str] = None
    lock_exists: bool = False
    lock_pane_id: Optional[str] = None
    lock_window: Optional[str] = None
    lock_agent: Optional[str] = None
    lock_claimed_at: Optional[str] = None
    worktree_path: Optional[Path] = None


@dataclass
class QueuePlan:
    """Plan for queue execution."""

    ready_tasks: list[QueueTask]
    available_tasks: list[QueueTask]
    blocked_tasks: list[QueueTask]
    slots_available: int
    workers_count: int
    concurrency_limit: int


def extract_agent_from_metadata(output_line: str, config: Config) -> str:
    """
    Extract agent type from task metadata.

    Priority:
    1. Task labels (agent:build, agent=build, agent/build)
    2. Config default agent

    Args:
        output_line: Single line from `bd ready` output
        config: Config object for default agent

    Returns:
        Detected agent type
    """
    # Check for agent label in various formats
    agent_patterns = [
        r"agent:(\w+)",  # agent:build
        r"agent=(\w+)",  # agent=build
        r"agent/(\w+)",  # agent/build
    ]

    for pattern in agent_patterns:
        match = re.search(pattern, output_line, re.IGNORECASE)
        if match:
            return match.group(1).lower()

    # Default to config default_agent
    logger.debug(f"agent={config.default_agent} (reason: no agent label)")
    return config.default_agent


def extract_ready_tasks(config: Config) -> list[QueueTask]:
    """
    Extract ready tasks from Beads.

    Args:
        config: Config object

    Returns:
        List of QueueTask objects (empty if no tasks or beads not available)
    """
    beads_status = beads_available()
    if not (beads_status.command_available and beads_status.repo_initialized):
        logger.debug("Beads not available, no ready tasks")
        return []

    try:
        output = run_command_output(["bd", "ready"])
        if not output.strip():
            return []

        tasks = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            # Extract task_id (first token, typically "bd-xxxx")
            task_id = line.split()[0] if line.split() else line

            # Extract agent from metadata
            agent = extract_agent_from_metadata(line, config)

            tasks.append(QueueTask(task_id=task_id, agent=agent, agent_metadata={}))

        logger.debug(f"Extracted {len(tasks)} ready tasks from Beads")
        return tasks

    except SubprocessError as e:
        logger.warning(f"Failed to extract ready tasks: {e}")
        return []


def arbitrate_locks(
    tasks: list[QueueTask],
    session_name: str,
    max_workers: int,
    config: Config,
    force: bool = False,
) -> QueuePlan:
    """
    Arbitrate locks and apply concurrency limits.

    Args:
        tasks: Ready tasks from Beads
        session_name: Tmux session name
        max_workers: Maximum concurrent workers
        config: Config object
        force: Skip deduplication checks

    Returns:
        QueuePlan with available and blocked tasks (with lock details)
    """
    from village.status import collect_workers

    # Collect active workers (locks with ACTIVE panes)
    workers = collect_workers(session_name)
    active_workers_count = len(workers)

    # Convert status workers to WorkerInfo for conflict detection
    active_worker_infos: list[WorkerInfo] = []
    for worker in workers:
        worktree_path = config.worktrees_dir / worker.task_id
        active_worker_infos.append(
            WorkerInfo(
                task_id=worker.task_id,
                worktree_path=worktree_path,
                pane_id=worker.pane_id,
                window_id=worker.window,
            )
        )

    # Calculate available slots
    slots_available = max(0, max_workers - active_workers_count)

    # Identify tasks with existing locks
    active_task_ids = {worker.task_id for worker in workers}

    # Pre-collect all lock files for lookup
    all_locks: dict[str, Lock] = {}
    for lock_file in config.locks_dir.glob("*.lock"):
        lock = parse_lock(lock_file)
        if lock:
            all_locks[lock.task_id] = lock

    available_tasks: list[QueueTask] = []
    blocked_tasks: list[QueueTask] = []

    for task in tasks:
        # Add lock info to task
        if task.task_id in all_locks:
            lock = all_locks[task.task_id]
            task.lock_exists = True
            task.lock_pane_id = lock.pane_id
            task.lock_window = lock.window
            task.lock_agent = lock.agent
            if lock.claimed_at:
                task.lock_claimed_at = lock.claimed_at.isoformat()

        # Add workspace path
        worktree_path = config.worktrees_dir / task.task_id
        if worktree_path.exists():
            task.worktree_path = worktree_path

        # Deduplication check (skip if forced)
        if not force:
            events = read_events(config.village_dir)
            is_recent, last_event = is_task_recent(events, task.task_id, config.queue_ttl_minutes)
            if is_recent:
                task.skip_reason = "recently_executed"
                blocked_tasks.append(task)
                continue

        # Check if task already has an active lock
        if task.task_id in active_task_ids:
            task.skip_reason = "active_lock"
            blocked_tasks.append(task)
            continue

        # Check if we have available slots
        if len(available_tasks) >= slots_available:
            task.skip_reason = "concurrency_limit"
            blocked_tasks.append(task)
            continue

        # Conflict detection (if enabled and not forced)
        if config.conflict.enabled and not force:
            worktree_path = config.worktrees_dir / task.task_id
            if worktree_path.exists():
                hypothetical_worker = WorkerInfo(
                    task_id=task.task_id,
                    worktree_path=worktree_path,
                    pane_id="hypothetical",
                    window_id="hypothetical",
                )
                workers_with_hypothetical = active_worker_infos + [hypothetical_worker]
                conflict_report = detect_file_conflicts(workers_with_hypothetical, config)

                if conflict_report.has_conflicts:
                    if conflict_report.blocked:
                        task.skip_reason = "conflict_blocked"
                        blocked_tasks.append(task)
                        logger.warning(f"Task {task.task_id} blocked due to file conflicts")
                        continue
                    else:
                        logger.warning(
                            f"Task {task.task_id} has potential conflicts: "
                            f"{render_conflict_report(conflict_report)}"
                        )

        # Task is available
        available_tasks.append(task)

    return QueuePlan(
        ready_tasks=tasks,
        available_tasks=available_tasks,
        blocked_tasks=blocked_tasks,
        slots_available=slots_available,
        workers_count=active_workers_count,
        concurrency_limit=max_workers,
    )


def generate_queue_plan(
    session_name: str,
    max_workers: int,
    config: Optional[Config] = None,
    force: bool = False,
) -> QueuePlan:
    """
    Generate complete queue plan.

    Args:
        session_name: Tmux session name
        max_workers: Maximum concurrent workers
        config: Optional config (uses default if not provided)
        force: Skip deduplication checks

    Returns:
        QueuePlan with ready, available, and blocked tasks
    """
    if config is None:
        config = get_config()

    # Extract ready tasks from Beads
    tasks = extract_ready_tasks(config)

    # Arbitrate locks and apply concurrency limits
    return arbitrate_locks(tasks, session_name, max_workers, config, force)


def render_queue_plan(plan: QueuePlan, verbose: bool = False) -> str:
    """
    Render queue plan as human-readable text.

    Args:
        plan: QueuePlan to render
        verbose: Show detailed task list

    Returns:
        Formatted text output
    """
    lines = []

    # Summary
    lines.append(f"Ready tasks: {len(plan.ready_tasks)}")
    lines.append(f"Available tasks: {len(plan.available_tasks)}")
    lines.append(f"Blocked tasks: {len(plan.blocked_tasks)}")
    lines.append(f"Slots available: {plan.slots_available}")
    lines.append(f"Active workers: {plan.workers_count}")
    lines.append(f"Concurrency limit: {plan.concurrency_limit}")
    lines.append("")

    # Show available tasks
    if plan.available_tasks:
        lines.append("Available tasks (will start):")
        for task in plan.available_tasks:
            lines.append(f"  - {task.task_id} (agent: {task.agent})")
        lines.append("")
    else:
        lines.append("No tasks available to start")
        lines.append("")

    # Show blocked tasks (with reasons)
    if plan.blocked_tasks:
        lines.append("Blocked tasks:")
        for task in plan.blocked_tasks:
            lines.append(f"  - {task.task_id} (agent: {task.agent}) - {task.skip_reason}")
        lines.append("")

    return "\n".join(lines)


def render_queue_plan_json(plan: QueuePlan) -> str:
    """
    Render queue plan as JSON.

    Args:
        plan: QueuePlan to render

    Returns:
        JSON string with full detail
    """
    import json

    def task_to_dict(task: QueueTask) -> dict[str, object]:
        return {
            "task_id": task.task_id,
            "agent": task.agent,
            "skip_reason": task.skip_reason,
            "agent_metadata": task.agent_metadata,
            "lock_exists": task.lock_exists,
            "lock_pane_id": task.lock_pane_id,
            "lock_window": task.lock_window,
            "lock_agent": task.lock_agent,
            "lock_claimed_at": task.lock_claimed_at,
            "worktree_path": str(task.worktree_path) if task.worktree_path else None,
        }

    plan_dict: dict[str, object] = {
        "ready_tasks": [task_to_dict(t) for t in plan.ready_tasks],
        "available_tasks": [task_to_dict(t) for t in plan.available_tasks],
        "blocked_tasks": [task_to_dict(t) for t in plan.blocked_tasks],
        "slots_available": plan.slots_available,
        "workers_count": plan.workers_count,
        "concurrency_limit": plan.concurrency_limit,
    }

    return json.dumps(plan_dict, indent=2, sort_keys=True)


def execute_queue_plan(
    plan: QueuePlan,
    session_name: str,
    config: Optional[Config] = None,
    force: bool = False,
) -> list[ResumeResult]:
    """
    Execute queue plan by starting available tasks.

    Args:
        plan: QueuePlan to execute
        session_name: Tmux session name
        config: Optional config (uses default if not provided)
        force: Skip deduplication checks (for consistency with planning)

    Returns:
        List of ResumeResult for each started task
    """
    if config is None:
        config = get_config()

    results: list[ResumeResult] = []

    for task in plan.available_tasks:
        logger.info(f"Starting task: {task.task_id} (agent: {task.agent})")

        # Log queue task start
        log_task_start(task.task_id, "queue", config.village_dir)

        try:
            result = execute_resume(
                task_id=task.task_id,
                agent=task.agent,
                detached=False,
                dry_run=False,
                config=config,
            )
            results.append(result)

            if result.success:
                logger.info(f"Task started successfully: {task.task_id}")

                # Transition state to CLAIMED after successful claim
                state_machine = TaskStateMachine(config)
                transition_result = state_machine.transition(
                    task_id=task.task_id,
                    new_state=TaskState.CLAIMED,
                    context={"pane_id": result.pane_id, "window": result.window_name},
                )

                if not transition_result.success:
                    logger.warning(
                        f"Failed to transition task {task.task_id} to CLAIMED: "
                        f"{transition_result.message}"
                    )
            else:
                logger.warning(f"Task failed to start: {task.task_id} - {result.error}")

        except Exception as e:
            logger.error(f"Exception starting task {task.task_id}: {e}")
            results.append(
                ResumeResult(
                    success=False,
                    task_id=task.task_id,
                    agent=task.agent,
                    worktree_path=config.worktrees_dir / task.task_id,
                    window_name="",
                    pane_id="",
                    error=str(e),
                )
            )

    return results
