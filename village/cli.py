"""Village CLI entrypoint."""

import sys

import click

from village.config import get_config
from village.logging import get_logger, setup_logging
from village.probes.tmux import clear_pane_cache, session_exists
from village.queue import (
    execute_queue_plan,
    generate_queue_plan,
    render_queue_plan,
    render_queue_plan_json,
)
from village.render.text import render_initialization_plan
from village.resume import execute_resume, plan_resume
from village.runtime import collect_runtime_state
from village.status import collect_workers

logger = get_logger(__name__)


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
@click.version_option()
def village(verbose: bool) -> None:
    """Village - CLI-native parallel development orchestrator."""
    setup_logging(verbose=verbose)
    clear_pane_cache()


@village.command()
@click.option("--short", is_flag=True, help="Short output")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
@click.option("--workers", is_flag=True, help="Show workers view")
@click.option("--locks", is_flag=True, help="Show locks view")
@click.option("--orphans", is_flag=True, help="Show orphans view")
def status(
    short: bool,
    json_output: bool,
    workers: bool,
    locks: bool,
    orphans: bool,
) -> None:
    """
    Show village status.

    Non-mutating. Probes actual state, doesn't create directories.

    Flags:
      --short: Minimal status (tmux + locks count)
      --workers: Tabular workers view
      --locks: Detailed locks view
      --orphans: Orphans with suggested actions
      --json: Full status as JSON (no suggested actions)

    Default: Summary only (use flags for details)
    """
    from village.render.json import render_status_json
    from village.render.text import render_full_status
    from village.status import collect_full_status

    config = get_config()

    if json_output:
        full_status = collect_full_status(config.tmux_session)
        click.echo(render_status_json(full_status))
    elif short:
        tmux_running = session_exists(config.tmux_session)
        lock_files = list(config.locks_dir.glob("*.lock")) if config.locks_dir.exists() else []
        parts = []
        if tmux_running:
            parts.append(f"tmux:{config.tmux_session}")
        else:
            parts.append("tmux:none")

        if config.locks_dir.exists():
            parts.append(f"locks:{len(lock_files)}")
        else:
            parts.append("locks:none")

        click.echo(" ".join(parts))
    else:
        full_status = collect_full_status(config.tmux_session)
        flags_dict = {
            "workers": workers,
            "locks": locks,
            "orphans": orphans,
        }
        output = render_full_status(full_status, flags_dict)
        click.echo(output)


@village.command()
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--plan", is_flag=True, help="Alias for --dry-run")
@click.option(
    "--dashboard/--no-dashboard", "dashboard", default=True, help="Create dashboard window"
)
def up(dry_run: bool, plan: bool, dashboard: bool) -> None:
    """
    Initialize village runtime (idempotent).

    Brings system to desired state:
      - Creates .village/ directories
      - Creates .village/config (with defaults)
      - Initializes Beads (if needed)
      - Creates tmux session (if missing)
      - Creates dashboard window (if enabled)

    Skips components that already exist.
    Does not start workers.

    Supports: --dry-run, --plan (preview mode)
    """
    from village.runtime import execute_initialization, plan_initialization

    config = get_config()

    if dry_run or plan:
        # Show plan, don't execute
        state = collect_runtime_state(config.tmux_session)
        init_plan = plan_initialization(state)
        plan_mode = True
        if not dashboard:
            click.echo("Note: Dashboard creation disabled (--no-dashboard)")
        click.echo(render_initialization_plan(init_plan, plan_mode=plan_mode))
        return

    # Execute initialization
    state = collect_runtime_state(config.tmux_session)
    init_plan = plan_initialization(state)
    success = execute_initialization(
        init_plan,
        dry_run=False,
        dashboard=dashboard,
    )

    if success:
        click.echo("Runtime initialized")
    else:
        raise click.ClickException("Failed to initialize runtime")


@village.command()
def locks() -> None:
    """List all locks with ACTIVE/STALE status."""
    from village.render.text import render_worker_table

    config = get_config()
    workers = collect_workers(config.tmux_session)

    if not workers:
        click.echo("No locks found")
        return

    output = render_worker_table(workers)
    click.echo(output)


@village.command()
@click.option("--dry-run", is_flag=True, help="Show what would be removed")
@click.option("--plan", is_flag=True, help="Generate cleanup plan")
def cleanup(dry_run: bool, plan: bool) -> None:
    """
    Remove stale locks.

    Default: Execute mode (delete stale locks).
    Use --plan or --dry-run to preview.
    """
    from village.cleanup import execute_cleanup, plan_cleanup

    config = get_config()

    # Generate plan
    cleanup_plan = plan_cleanup(config.tmux_session)

    if cleanup_plan.stale_locks:
        click.echo(f"Found {len(cleanup_plan.stale_locks)} stale locks:")
        for lock in cleanup_plan.stale_locks:
            click.echo(f"  - {lock.task_id} (pane: {lock.pane_id})")
    else:
        click.echo("No stale locks found")
        return

    # Preview vs Execute
    if dry_run or plan:
        click.echo("(preview: nothing removed)")
    else:
        execute_cleanup(cleanup_plan)
        click.echo("Cleanup complete")


@village.command()
@click.argument("task_id")
@click.option("--force", is_flag=True, help="Force unlock even if pane is active")
def unlock(task_id: str, force: bool) -> None:
    """
    Unlock a task (remove lock file).

    Raises:
        click.ClickException: If lock is ACTIVE and --force not provided
    """
    from village.locks import is_active, parse_lock

    config = get_config()
    lock_path = config.locks_dir / f"{task_id}.lock"

    if not lock_path.exists():
        click.echo(f"Lock not found: {task_id}")
        raise click.ClickException(f"No such lock: {task_id}")

    lock = parse_lock(lock_path)
    if not lock:
        click.echo(f"Invalid lock file: {task_id}")
        raise click.ClickException(f"Failed to parse lock: {task_id}")

    # Safety check: verify pane status
    if is_active(lock, config.tmux_session):
        if not force:
            click.echo(f"Lock is ACTIVE (pane {lock.pane_id} exists)")
            click.echo("Use --force to unlock anyway")
            raise click.ClickException(f"Lock {task_id} is active")

    # Remove lock
    lock_path.unlink()
    click.echo(f"Unlocked: {task_id}")


@village.command()
@click.option("--dry-run", is_flag=True, help="Show what would be killed")
@click.option("--plan", is_flag=True, help="Alias for --dry-run")
def down(dry_run: bool, plan: bool) -> None:
    """
    Stop village runtime.

    Kills tmux session only (doesn't delete work data).
    Safe to run while workers are active (they'll be detached).

    Supports: --dry-run, --plan (preview mode)
    """
    from village.config import get_config
    from village.runtime import shutdown_runtime

    config = get_config()

    if dry_run or plan:
        if session_exists(config.tmux_session):
            click.echo(f"Would kill session '{config.tmux_session}'")
        else:
            click.echo("No session to stop")
        return

    # Execute shutdown
    success = shutdown_runtime(config.tmux_session)

    if success:
        click.echo(f"Runtime stopped (session '{config.tmux_session}' terminated)")
    else:
        raise click.ClickException("Failed to stop runtime")


@village.command()
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


@village.command()
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
def resume(
    task_id: str | None,
    agent: str | None,
    detached: bool,
    html: bool,
    dry_run: bool,
) -> None:
    """
    Resume a task (explicit or planner).

    If task_id provided: Explicit resume of specific task
    If no task_id: Use planner to suggest next action

    Agent Selection:
      - If --agent provided: Use specified agent
      - If no --agent: Auto-detect from Beads
      - If Beads unavailable: Use config.default_agent (falls back to "worker")

    Flags:
      --detached: Run without attaching to tmux pane
      --html: Output HTML with embedded JSON metadata
      --dry-run: Preview mode (no mutations)

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
      village resume --html            # HTML output
      village resume --dry-run          # Preview mode
    """
    config = get_config()

    # If no task_id provided, use planner
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

        contract = generate_contract(
            result.task_id, result.agent, result.worktree_path, result.window_name, config
        )
        from village.render.html import render_resume_html

        click.echo(render_resume_html(contract))


@village.command()
@click.option("--n", "count", type=int, help="Number of tasks to start")
@click.option("--plan", is_flag=True, help="Generate queue plan")
@click.option("--dry-run", is_flag=True, help="Preview execution")
@click.option("--max-workers", type=int, help="Override concurrency limit")
@click.option("--agent", help="Filter tasks by agent type")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def queue(
    count: int, plan: bool, dry_run: bool, max_workers: int, agent: str, json_output: bool
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

    Examples:
      village queue                    # Show plan
      village queue --plan --json       # Full JSON plan
      village queue 2                 # Start 2 tasks
      village queue --n 3             # Start 3 tasks
      village queue --agent build        # Start only build tasks
      village queue --dry-run 2        # Preview starting 2 tasks
    """
    config = get_config()

    # Use config max_workers or override from CLI
    concurrency_limit = max_workers if max_workers else config.max_workers

    # Generate queue plan
    queue_plan = generate_queue_plan(config.tmux_session, concurrency_limit, config)

    # Filter by agent if requested
    if agent:
        queue_plan.ready_tasks = [t for t in queue_plan.ready_tasks if t.agent == agent]
        queue_plan.available_tasks = [t for t in queue_plan.available_tasks if t.agent == agent]
        queue_plan.blocked_tasks = [t for t in queue_plan.blocked_tasks if t.agent == agent]

    # Render plan (default or --plan)
    if plan or count is None:
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
            import json

            click.echo(
                json.dumps(
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
        sys.exit(1)

    # Execute queue plan
    click.echo(f"Starting {len(queue_plan.available_tasks)} task(s)...")
    results = execute_queue_plan(queue_plan, config.tmux_session, config)

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
        import json

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
        click.echo(json.dumps(output, indent=2, sort_keys=True))

    # Exit codes:
    # 0: All tasks started successfully
    # 4: Some tasks started, some failed (partial success)
    # 1: No tasks started (all failed)
    if tasks_started > 0 and tasks_failed == 0:
        sys.exit(0)
    elif tasks_started > 0:
        sys.exit(4)
    else:
        sys.exit(1)
