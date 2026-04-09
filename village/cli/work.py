"""Work management commands: queue, resume, pause, resume_task, ready."""

import os
import sys
from typing import TYPE_CHECKING

import click

from village.config import Config, get_config
from village.errors import EXIT_BLOCKED, EXIT_ERROR, EXIT_PARTIAL, EXIT_SUCCESS
from village.logging import get_logger
from village.queue import (
    execute_queue_plan,
    generate_queue_plan,
    render_queue_plan,
    render_queue_plan_json,
)
from village.resume import execute_resume, plan_resume

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


@click.command()
@click.option("--n", "count", type=int, help="Number of tasks to start")
@click.option("--plan", is_flag=True, help="Generate queue plan")
@click.option("--dry-run", is_flag=True, help="Preview execution")
@click.option("--max-workers", type=int, help="Override concurrency limit")
@click.option("--agent", help="Filter tasks by agent type")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
@click.option("--force", is_flag=True, help="Skip deduplication checks")
@click.option("--approve", "approve_task_id", help="Approve a pending task")
@click.option("--approve-all", is_flag=True, help="Approve all pending tasks")
@click.option("--reject", "reject_task_id", help="Reject a pending task")
def queue(
    count: int,
    plan: bool,
    dry_run: bool,
    max_workers: int,
    agent: str,
    json_output: bool,
    force: bool,
    approve_task_id: str | None,
    approve_all: bool,
    reject_task_id: str | None,
) -> None:
    """
    Queue and execute ready tasks from Beads.

    Default: Show queue plan (no execution).
    Use --n N or just N to start N tasks.

    Flags:
      --plan: Show plan only (default behavior)
      --dry-run: Preview what would happen
      --max-workers N: Override concurrency limit
      --agent TYPE: Filter tasks by agent type
      --json: Full JSON output (with --plan)
      --force: Skip deduplication checks

    Examples:
      village queue                    # Show plan
      village queue --plan --json       # Full JSON plan
      village queue 2                 # Start 2 tasks
      village queue --n 3             # Start 3 tasks
      village queue --agent build        # Start only build tasks
      village queue --dry-run 2        # Preview starting 2 tasks
    """
    import json as _json

    from village.state_machine import TaskState, TaskStateMachine

    config = get_config()

    if approve_task_id:
        state_machine = TaskStateMachine(config)
        current = state_machine.get_state(approve_task_id)
        if current == TaskState.PENDING_APPROVAL:
            transition_result = state_machine.transition(
                task_id=approve_task_id,
                new_state=TaskState.QUEUED,
                context={"reason": "user_approved"},
            )
            if transition_result.success:
                click.echo(f"Approved task {approve_task_id}")
            else:
                click.echo(f"Failed to approve: {transition_result.message}", err=True)
                sys.exit(EXIT_ERROR)
        else:
            click.echo(
                f"Task {approve_task_id} is not pending approval (state: {current.value if current else 'none'})",
                err=True,
            )
            sys.exit(EXIT_BLOCKED)
        return

    if approve_all:
        state_machine = TaskStateMachine(config)
        approved_count = 0
        for lock_file in config.locks_dir.glob("*.lock"):
            task_id = lock_file.stem
            current = state_machine.get_state(task_id)
            if current == TaskState.PENDING_APPROVAL:
                transition_result = state_machine.transition(
                    task_id=task_id,
                    new_state=TaskState.QUEUED,
                    context={"reason": "bulk_approved"},
                )
                if transition_result.success:
                    approved_count += 1
        click.echo(f"Approved {approved_count} task(s)")
        return

    if reject_task_id:
        state_machine = TaskStateMachine(config)
        current = state_machine.get_state(reject_task_id)
        if current == TaskState.PENDING_APPROVAL:
            transition_result = state_machine.transition(
                task_id=reject_task_id,
                new_state=TaskState.FAILED,
                context={"reason": "user_rejected"},
            )
            if transition_result.success:
                click.echo(f"Rejected task {reject_task_id}")
            else:
                click.echo(f"Failed to reject: {transition_result.message}", err=True)
                sys.exit(EXIT_ERROR)
        else:
            click.echo(
                f"Task {reject_task_id} is not pending approval (state: {current.value if current else 'none'})",
                err=True,
            )
            sys.exit(EXIT_BLOCKED)
        return

    # Use config max_workers or override from CLI
    concurrency_limit = max_workers if max_workers else config.max_workers

    # Generate queue plan
    queue_plan = generate_queue_plan(config.tmux_session, concurrency_limit, config, force)

    # Filter by agent if requested
    if agent:
        queue_plan.ready_tasks = [t for t in queue_plan.ready_tasks if t.agent == agent]
        queue_plan.available_tasks = [t for t in queue_plan.available_tasks if t.agent == agent]
        queue_plan.blocked_tasks = [t for t in queue_plan.blocked_tasks if t.agent == agent]

    # Render plan (default or --plan)
    if plan or count is None:
        pending_approval = [t for t in queue_plan.blocked_tasks if t.skip_reason == "pending_approval"]
        ci_mode = os.environ.get("VILLAGE_CI_MODE", "").lower() in ("1", "true", "yes")
        if ci_mode and pending_approval:
            click.echo(f"Error: {len(pending_approval)} task(s) pending approval in CI mode", err=True)
            sys.exit(EXIT_ERROR)

        if json_output:
            click.echo(render_queue_plan_json(queue_plan))
        else:
            click.echo(render_queue_plan(queue_plan))
        return

    # Execution mode (--n N provided)
    # Apply dry-run if requested
    if dry_run:
        click.echo("(dry-run: previewing execution)")
        click.echo(render_queue_plan(queue_plan))
        return

    # Limit tasks to start if count specified
    if count is not None:
        queue_plan.available_tasks = queue_plan.available_tasks[:count]

    # Check if there are tasks to start
    if not queue_plan.available_tasks:
        if json_output:
            click.echo(
                _json.dumps(
                    {
                        "tasks_started": 0,
                        "tasks_failed": 0,
                        "results": [],
                        "message": "No tasks available to start",
                    },
                    indent=2,
                )
            )
        else:
            click.echo("No tasks available to start")
        sys.exit(EXIT_BLOCKED)

    # Execute queue plan
    if not json_output:
        click.echo(f"Starting {len(queue_plan.available_tasks)} task(s)...")
    results = execute_queue_plan(queue_plan, config.tmux_session, config, force)

    # Count successes and failures
    tasks_started = sum(1 for r in results if r.success)
    tasks_failed = sum(1 for r in results if not r.success)

    # Render results
    if not json_output:
        click.echo(f"\nTasks started: {tasks_started}")
        click.echo(f"Tasks failed: {tasks_failed}")

        if tasks_failed > 0:
            click.echo("\nFailed tasks:")
            for result in results:
                if not result.success:
                    click.echo(f"  - {result.task_id}: {result.error or 'Unknown error'}")
    else:
        # JSON output with results
        output = {
            "tasks_started": tasks_started,
            "tasks_failed": tasks_failed,
            "results": [
                {
                    "task_id": r.task_id,
                    "agent": r.agent,
                    "success": r.success,
                    "worktree_path": str(r.worktree_path),
                    "window_name": r.window_name,
                    "pane_id": r.pane_id,
                    "error": r.error,
                }
                for r in results
            ],
        }
        click.echo(_json.dumps(output, indent=2, sort_keys=True))

    # Exit codes:
    # EXIT_SUCCESS (0): All tasks started successfully
    # EXIT_PARTIAL (4): Some tasks started, some failed
    # EXIT_ERROR (1): No tasks started (all failed)
    if tasks_started > 0 and tasks_failed == 0:
        sys.exit(EXIT_SUCCESS)
    elif tasks_started > 0:
        sys.exit(EXIT_PARTIAL)
    else:
        sys.exit(EXIT_ERROR)


@click.command()
@click.argument("task_id", default=None, required=False, type=str)
@click.option(
    "--agent",
    type=str,
    help="Agent name (auto-detect from Beads if not provided)",
)
@click.option(
    "--detached",
    is_flag=True,
    help="Run in detached mode (no tmux attach)",
)
@click.option(
    "--html",
    is_flag=True,
    help="Output HTML with JSON metadata",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview mode without making changes",
)
@click.option(
    "--select",
    "select_mode",
    is_flag=True,
    help="Select from ready tasks interactively",
)
def resume(
    task_id: str | None,
    agent: str | None,
    detached: bool,
    html: bool,
    dry_run: bool,
    select_mode: bool,
) -> None:
    """
    Resume a task (explicit or planner).

    If task_id provided: Explicit resume of specific task
    If no task_id: Use planner to suggest next action
    If --select: Select from ready tasks interactively

    Agent Selection:
      - If --agent provided: Use specified agent
      - If no --agent: Auto-detect from Beads
      - If Beads unavailable: Use config.default_agent (falls back to "worker")

    Flags:
      --detached: Run without attaching to tmux pane
      --html: Output HTML with embedded JSON metadata
      --dry-run: Preview mode (no mutations)
      --select: Select from ready tasks interactively

    Planning Logic (when no task_id):
      1. Ensure runtime via 'village up'
      2. Attach if active workers exist
      3. Cleanup if stale locks exist
      4. Queue ready tasks if available
      5. Otherwise show 'village ready'

    Examples:
      village resume bd-a3f8              # Explicit resume
      village resume --agent build       # Use specific agent
      village resume bd-a3f8 --detached # Detached mode
      village resume                    # Use planner
      village resume --select           # Interactive selection
      village resume --html            # HTML output
      village resume --dry-run          # Preview mode
    """
    from village.interactive import select_from_list
    from village.status import collect_workers

    config = get_config()

    if select_mode and task_id is None:
        from village.state_machine import TaskState, TaskStateMachine

        workers = collect_workers(config.tmux_session)
        state_machine = TaskStateMachine(config)

        in_progress = [w for w in workers if state_machine.get_state(w.task_id) == TaskState.IN_PROGRESS]

        queue_plan = generate_queue_plan(config.tmux_session, config.max_workers, config)

        ready_tasks = queue_plan.ready_tasks

        if not in_progress and not ready_tasks:
            click.echo("No tasks to resume")
            sys.exit(0)

        choices = []
        for w in in_progress:
            choices.append((w.task_id, w.status, "in_progress"))
        for t in ready_tasks:
            choices.append((t.task_id, "READY", t.agent))

        if not choices:
            click.echo("No tasks to resume")
            sys.exit(0)

        selected = select_from_list(
            choices,
            "Select task to resume:",
            formatter=lambda c: f"{c[0]} ({c[1]})",
        )
        if selected is None:
            click.echo("Canceled")
            sys.exit(0)
        task_id = selected[0]

    if task_id is None:
        action = plan_resume(config=config)

        # Render suggested action
        if action.action == "resume":
            click.echo(f"Ready to resume task: {action.meta.get('task_id')}")
        elif action.action == "up":
            click.echo(f"Action: village {action.action}")
            click.echo(f"Reason: {action.reason}")
            click.echo(f"Run: {action.meta.get('command', 'village up')}")
        elif action.action == "status":
            click.echo(f"Action: village {action.action}")
            click.echo(f"Reason: {action.reason}")
            click.echo(f"Run: {action.meta.get('command', 'village status --workers')}")
        elif action.action == "cleanup":
            click.echo(f"Action: village {action.action}")
            click.echo(f"Reason: {action.reason}")
            click.echo(f"Run: {action.meta.get('command', 'village cleanup')}")
        elif action.action == "queue":
            click.echo(f"Action: village {action.action}")
            click.echo(f"Reason: {action.reason}")
            click.echo(f"Run: {action.meta.get('command', 'village queue')}")
        elif action.action == "ready":
            click.echo(f"Action: village {action.action}")
            click.echo(f"Reason: {action.reason}")
            click.echo(f"Run: {action.meta.get('command', 'village ready')}")
        else:
            click.echo(f"Action: {action.action}")
            click.echo(f"Reason: {action.reason}")

        return

    # Validate agent selection
    if agent is None:
        # Use config default as fallback (Beads auto-detect in resume module)
        agent = config.default_agent

    # Execute resume
    result = execute_resume(
        task_id=task_id,
        agent=agent,
        detached=detached,
        dry_run=dry_run,
        config=config,
    )

    # Render result
    if result.success:
        click.echo(f"✓ Resume successful: {result.task_id}")
        click.echo(f"  Window: {result.window_name}")
        click.echo(f"  Pane: {result.pane_id}")
        click.echo(f"  Worktree: {result.worktree_path}")
    else:
        click.echo(f"✗ Resume failed: {result.task_id}")
        if result.error:
            click.echo(f"  Error: {result.error}")

    # HTML output if requested
    if html and result.success:
        from village.contracts import generate_contract
        from village.render.html import render_resume_html

        contract = generate_contract(result.task_id, result.agent, result.worktree_path, result.window_name, config)

        click.echo(render_resume_html(contract))


@click.command()
@click.argument("task_id", default=None, required=False, type=str)
@click.option("--force", is_flag=True, help="Force pause without validation")
@click.option("--select", "select_mode", is_flag=True, help="Select from list interactively")
def pause(task_id: str | None, force: bool, select_mode: bool) -> None:
    """
    Pause an in-progress task.

    Pauses a task that is currently in progress. Only valid from IN_PROGRESS state.

    \b
    Mutating. Updates lock file with PAUSED state.

    Examples:
        village pause bd-a3f8
        village pause bd-a3f8 --force
        village pause --select

    Options:
        --force: Skip state validation (bypass IN_PROGRESS check)
        --select: Select from in-progress tasks interactively

    Exit codes:
        0: Task paused successfully
        4: Task not in IN_PROGRESS state
        5: Task not found
    """
    from village.interactive import select_from_list
    from village.state_machine import TaskState, TaskStateMachine
    from village.status import collect_workers

    config = get_config()

    if task_id is None or select_mode:
        workers = collect_workers(config.tmux_session)
        state_machine = TaskStateMachine(config)

        in_progress = [w for w in workers if state_machine.get_state(w.task_id) == TaskState.IN_PROGRESS]
        if not in_progress:
            click.echo("No in-progress tasks found")
            if task_id is None:
                sys.exit(0)
            return

        selected = select_from_list(
            in_progress,
            "Select task to pause:",
            formatter=lambda w: f"{w.task_id} ({w.status})",
        )
        if selected is None:
            click.echo("Canceled")
            sys.exit(0)
        task_id = selected.task_id

    state_machine = TaskStateMachine(config)

    current_state = state_machine.get_state(task_id)

    if current_state is None:
        click.echo(f"Task {task_id} not found (no lock file)", err=True)
        sys.exit(EXIT_BLOCKED)

    if not force and current_state != TaskState.IN_PROGRESS:
        click.echo(f"Task {task_id} is not IN_PROGRESS (current: {current_state.value})", err=True)
        sys.exit(EXIT_BLOCKED)

    result = state_machine.transition(
        task_id,
        TaskState.PAUSED,
        context={"reason": "user_paused"},
    )

    if result.success:
        click.echo(f"Paused task {task_id}")
    else:
        click.echo(f"Failed to pause: {result.message}", err=True)
        sys.exit(EXIT_ERROR)


@click.command("resume-task")
@click.argument("task_id", default=None, required=False, type=str)
@click.option("--force", is_flag=True, help="Force resume without validation")
@click.option("--select", "select_mode", is_flag=True, help="Select from list interactively")
def resume_task(task_id: str | None, force: bool, select_mode: bool) -> None:
    """
    Resume a paused task.

    Resumes a task that is currently paused. Only valid from PAUSED state.

    \b
    Mutating. Updates lock file with IN_PROGRESS state.

    Note: This command manages task state only. To execute a task,
    use the resume module workflow instead.

    Examples:
        village resume-task bd-a3f8
        village resume-task bd-a3f8 --force
        village resume-task --select

    Options:
        --force: Skip state validation (bypass PAUSED check)
        --select: Select from paused tasks interactively

    Exit codes:
        0: Task resumed successfully
        4: Task not in PAUSED state
        5: Task not found
    """
    from village.interactive import select_from_list
    from village.state_machine import TaskState, TaskStateMachine
    from village.status import collect_workers

    config = get_config()

    if task_id is None or select_mode:
        workers = collect_workers(config.tmux_session)
        state_machine = TaskStateMachine(config)

        paused = [w for w in workers if state_machine.get_state(w.task_id) == TaskState.PAUSED]
        if not paused:
            click.echo("No paused tasks found")
            if task_id is None:
                sys.exit(0)
            return

        selected = select_from_list(
            paused,
            "Select task to resume:",
            formatter=lambda w: f"{w.task_id} ({w.status})",
        )
        if selected is None:
            click.echo("Canceled")
            sys.exit(0)
        task_id = selected.task_id

    state_machine = TaskStateMachine(config)

    current_state = state_machine.get_state(task_id)

    if current_state is None:
        click.echo(f"Task {task_id} not found (no lock file)", err=True)
        sys.exit(EXIT_BLOCKED)

    if not force and current_state != TaskState.PAUSED:
        click.echo(
            f"Task {task_id} is not PAUSED (current: {current_state.value})",
            err=True,
        )
        sys.exit(EXIT_BLOCKED)

    result = state_machine.transition(
        task_id,
        TaskState.IN_PROGRESS,
        context={"reason": "user_resumed"},
    )

    if result.success:
        click.echo(f"Resumed task {task_id}")
    else:
        click.echo(f"Failed to resume: {result.message}", err=True)
        sys.exit(EXIT_ERROR)


@click.command()
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def ready(json_output: bool) -> None:
    """
    Check if village is ready for work.

    Non-mutating. Assesses environment, runtime, and work availability.

    Flags:
      --json: Full assessment as JSON (no suggested actions)

    Default: Text output with suggested actions
    """
    from village.ready import assess_readiness
    from village.render.json import render_ready_json
    from village.render.text import render_ready_text

    config = get_config()
    assessment = assess_readiness(config.tmux_session)

    if json_output:
        click.echo(render_ready_json(assessment))
    else:
        click.echo(render_ready_text(assessment))
        _show_objective_coverage(config)


def _show_objective_coverage(config: "Config") -> None:
    """Append objective coverage summary after readiness text."""
    from village.goals import get_objective_coverage_from_file, parse_goals

    goals_path = config.git_root / "GOALS.md"
    all_goals = parse_goals(goals_path)
    if not all_goals:
        return

    coverage = get_objective_coverage_from_file(goals_path)
    total_completed = 0
    total_objectives = 0
    for goal_id, (completed, total, _ratio) in coverage.items():
        total_completed += completed
        total_objectives += total

    if total_objectives > 0:
        pct = round(total_completed / total_objectives * 100, 1)
        click.echo(f"Objectives: {total_completed}/{total_objectives} completed ({pct}%)")
