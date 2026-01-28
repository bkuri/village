"""Village CLI entrypoint."""

import json
import signal
import sys
from datetime import datetime, timedelta, timezone

import click

from village.chat.beads_client import BeadsClient, BeadsError
from village.chat.llm_chat import LLMChat
from village.config import get_config
from village.errors import (
    EXIT_BLOCKED,
    EXIT_ERROR,
    EXIT_PARTIAL,
    EXIT_SUCCESS,
    InterruptedResume,
)
from village.event_log import Event, append_event
from village.llm.factory import get_llm_client
from village.logging import get_logger, setup_logging
from village.probes.tmux import (
    clear_pane_cache,
    load_village_config,
    session_exists,
    set_window_indicator,
    update_status_border_colour,
    update_status_draft_count,
    update_status_mode,
)
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


def _handle_interrupt(signum: int, frame: object) -> None:
    """Handle SIGINT (Ctrl+C)."""
    logger.info("Interrupted by user")
    raise InterruptedResume()


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
@click.version_option()
def village(verbose: bool) -> None:
    """Village - CLI-native parallel development orchestrator."""
    setup_logging(verbose=verbose)
    clear_pane_cache()
    signal.signal(signal.SIGINT, _handle_interrupt)


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
        click.echo(render_initialization_plan(init_plan, config.tmux_session, plan_mode=plan_mode))
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
        event = Event(
            ts=datetime.now(timezone.utc).isoformat(),
            cmd="up",
            task_id=None,
            pane=None,
            result="ok",
        )
        append_event(event, config.village_dir)
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
@click.option("--apply", is_flag=True, help="Include orphan and stale worktrees")
def cleanup(dry_run: bool, plan: bool, apply: bool) -> None:
    """
    Remove stale locks and optionally remove orphan/stale worktrees.

    Default: Execute mode (remove stale locks only).
    Use --plan or --dry-run to preview.
    Use --apply to include orphan and stale worktrees for removal.

    Examples:
      village cleanup                    # Remove stale locks only
      village cleanup --apply            # Remove stale locks + orphan/stale worktrees
      village cleanup --plan --apply      # Preview apply plan
      village cleanup --dry-run --apply   # Preview apply execution
    """
    from village.cleanup import execute_cleanup, plan_cleanup

    config = get_config()

    # Generate plan
    cleanup_plan = plan_cleanup(config.tmux_session, apply=apply)

    # Show worktree info if applying
    if apply:
        if cleanup_plan.orphan_worktrees:
            click.echo(f"Found {len(cleanup_plan.orphan_worktrees)} orphan worktrees:")
            for worktree in cleanup_plan.orphan_worktrees:
                click.echo(f"  - {worktree}")
        else:
            click.echo("No orphan worktrees found")

        if cleanup_plan.stale_worktrees:
            click.echo(f"Found {len(cleanup_plan.stale_worktrees)} stale worktrees:")
            for worktree in cleanup_plan.stale_worktrees:
                click.echo(f"  - {worktree}")
        else:
            click.echo("No stale worktrees found")

    if cleanup_plan.stale_locks:
        click.echo(f"Found {len(cleanup_plan.stale_locks)} stale locks:")
        for lock in cleanup_plan.stale_locks:
            click.echo(f"  - {lock.task_id} (pane: {lock.pane_id})")
    else:
        click.echo("No stale locks found")
        return

    # Preview vs Execute
    if dry_run or plan:
        items_to_remove = len(cleanup_plan.stale_locks)
        if apply:
            items_to_remove += len(cleanup_plan.orphan_worktrees) + len(
                cleanup_plan.stale_worktrees
            )
        click.echo(f"(preview: would remove {items_to_remove} item(s))")
        return

    # Execute cleanup
    execute_cleanup(cleanup_plan, config)

    removed_count = len(cleanup_plan.stale_locks)
    if apply:
        removed_count += len(cleanup_plan.orphan_worktrees) + len(cleanup_plan.stale_worktrees)

    if apply:
        click.echo("Cleanup complete")
    else:
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
        event = Event(
            ts=datetime.now(timezone.utc).isoformat(),
            cmd="down",
            task_id=None,
            pane=None,
            result="ok",
        )
        append_event(event, config.village_dir)
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
@click.option("--force", is_flag=True, help="Skip deduplication checks")
def queue(
    count: int,
    plan: bool,
    dry_run: bool,
    max_workers: int,
    agent: str,
    json_output: bool,
    force: bool,
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
    config = get_config()

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
    # EXIT_SUCCESS (0): All tasks started successfully
    # EXIT_PARTIAL (4): Some tasks started, some failed
    # EXIT_ERROR (1): No tasks started (all failed)
    if tasks_started > 0 and tasks_failed == 0:
        sys.exit(EXIT_SUCCESS)
    elif tasks_started > 0:
        sys.exit(EXIT_PARTIAL)
    else:
        sys.exit(EXIT_ERROR)


@village.command()
@click.option("--scope", type=str, help="Filter by scope (feature|fix|investigation|refactoring)")
@click.option("--total", is_flag=True, help="Return draft count (for statusbar)")
def drafts(scope: str | None, total: bool) -> None:
    """
    List or count draft tasks.

    Default: Show 2-column table (ID, Title)

    Examples:
      village drafts
      village drafts --scope feature
      village drafts --total

    Flags:
      --scope: Filter by scope
      --total: Return count only (machine-readable)
    """
    from village.chat.drafts import list_drafts
    from village.config import get_config
    from village.render.text import render_drafts_table

    config = get_config()
    all_drafts = list_drafts(config)

    if total:
        click.echo(str(len(all_drafts)))
        return

    if scope:
        all_drafts = [d for d in all_drafts if d.scope == scope]

    output = render_drafts_table(all_drafts)
    click.echo(output)


@village.command()
def chat() -> None:
    """
    Start LLM-native conversational interface for task creation.

    LLM-based chat with simple slash commands:
      - /create <title>: Create new task specification
      - /refine <clarification>: Revise current task
      - /revise <clarification>: Alias for /refine
      - /undo: Undo last refinement
      - /confirm: Create task in Beads
      - /discard: Discard current task
      - /tasks, /task <id>, /ready, /status, /history, /help

    Non-mutating by default. Creates tasks only on /confirm.

    Type /help for command reference.
    """
    import asyncio
    from pathlib import Path

    config = get_config()

    try:
        beads_client = BeadsClient()
    except Exception:
        beads_client = None

    llm_client = get_llm_client(config)

    prompt_path = Path(__file__).parent.parent / "prompts" / "chat" / "ppc_task_spec.md"
    try:
        with open(prompt_path, encoding="utf-8") as f:
            system_prompt = f.read()
    except FileNotFoundError:
        system_prompt = None

    chat = LLMChat(llm_client, system_prompt=system_prompt)

    async def setup_beads_client() -> None:
        if beads_client:
            await chat.set_beads_client(beads_client)

    try:
        asyncio.run(setup_beads_client())
    except Exception:
        pass

    click.echo("LLM Chat - Type /help for commands, /exit or /quit to quit\n")

    try:
        while True:
            user_input = click.prompt("", prompt_suffix="> ")

            if user_input.lower() in ["/exit", "/quit", "/bye"]:
                break

            try:
                response = asyncio.run(chat.handle_message(user_input))
                click.echo("\n" + response + "\n")
            except BeadsError as e:
                click.echo(f"\n❌ Beads error: {e}\n")
            except Exception as e:
                click.echo(f"\n❌ Error: {e}\n")
    except click.exceptions.Abort:
        click.echo("\nExiting...")
    except KeyboardInterrupt:
        click.echo("\nExiting...")


@village.command()
@click.option("--watch", is_flag=True, help="Auto-refresh mode")
@click.option(
    "--refresh-interval",
    type=int,
    default=None,
    help="Refresh interval in seconds (default: from config)",
)
def dashboard(watch: bool, refresh_interval: int | None) -> None:
    """
    Show real-time dashboard of Village state.

    Displays active workers, task queue, lock status, and orphans.
    Auto-refreshes every 2 seconds by default (configurable).

    \b
    Non-mutating. Probes actual state, doesn't create directories.

    Examples:
        village dashboard
        village dashboard --watch
        village dashboard --watch --refresh-interval 5
        village dashboard --refresh-interval 10
    \b

    Flags:
        --watch: Enable auto-refresh mode
        --refresh-interval: Set refresh interval in seconds

    Default: Static dashboard view (no auto-refresh)
    """
    from village.dashboard import VillageDashboard

    config = get_config()

    interval = refresh_interval or config.dashboard.refresh_interval_seconds
    enabled = config.dashboard.enabled

    if not enabled:
        click.echo("Dashboard is disabled. Enable with DASHBOARD_ENABLED=true")
        sys.exit(EXIT_ERROR)

    if watch:
        dashboard = VillageDashboard(config.tmux_session)
        dashboard.start_watch_mode(interval)
    else:
        from village.dashboard import render_dashboard_static

        output = render_dashboard_static(config.tmux_session)
        click.echo(output)


def parse_duration(duration: str) -> timedelta:
    """
    Parse duration string to timedelta.

    Supports formats:
    - 1h, 2h30m
    - 30m, 45m
    - 1d, 2d12h
    - 1h30m, 2d

    Args:
        duration: Duration string (e.g., "1h", "30m", "1d12h30m")

    Returns:
        timedelta object

    Raises:
        ValueError: If duration format is invalid
    """
    total_seconds = 0
    i = 0
    while i < len(duration):
        num_str = ""
        while i < len(duration) and duration[i].isdigit():
            num_str += duration[i]
            i += 1

        if not num_str:
            raise ValueError(f"Invalid duration format: {duration}")

        if i >= len(duration):
            raise ValueError(f"Invalid duration format: {duration} (missing unit)")

        unit = duration[i]
        i += 1

        num = int(num_str)

        if unit == "s":
            total_seconds += num
        elif unit == "m":
            total_seconds += num * 60
        elif unit == "h":
            total_seconds += num * 3600
        elif unit == "d":
            total_seconds += num * 86400
        else:
            raise ValueError(f"Invalid duration unit: {unit} (use s, m, h, or d)")

    return timedelta(seconds=total_seconds)


@village.command()
@click.option("--task", "task_id", help="Filter by task ID")
@click.option("--status", "status", help="Filter by result status (ok, error, etc.)")
@click.option("--since", "since", help="Filter events since ISO datetime (YYYY-MM-DDTHH:MM:SS)")
@click.option("--last", "last", help="Filter events from last duration (e.g., 1h, 30m, 2d)")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def events(
    task_id: str | None,
    status: str | None,
    since: str | None,
    last: str | None,
    json_output: bool,
) -> None:
    """
    Query and display events from the event log.

    Filters events from the village event log. Can filter by task ID,
    status, time range, or show all events.

    \b
    Non-mutating. Reads from events.log.

    Examples:
        village events
        village events --task bd-a3f8
        village events --status ok
        village events --last 1h
        village events --since "2026-01-01T00:00:00"
        village events --json

    Options:
        --task: Filter by task ID
        --status: Filter by result status
        --since: Show events since this ISO datetime
        --last: Show events from last duration (1h, 30m, 2d)
        --json: Output as JSON instead of table

    Exit codes:
        0: Events displayed successfully
        2: Invalid filter values
    """
    from datetime import datetime, timezone

    from village.event_query import EventFilters, query_events, query_result_to_json

    config = get_config()

    filters = EventFilters(
        task_id=task_id,
        status=status,
    )

    if since:
        try:
            filters.since = datetime.fromisoformat(since)
            if filters.since.tzinfo is None:
                filters.since = filters.since.replace(tzinfo=timezone.utc)
        except ValueError:
            click.echo(f"Invalid datetime format: {since}", err=True)
            click.echo("Expected ISO format: YYYY-MM-DDTHH:MM:SS", err=True)
            sys.exit(EXIT_ERROR)

    if last:
        try:
            filters.last = parse_duration(last)
        except ValueError as e:
            click.echo(f"Invalid duration format: {e}", err=True)
            sys.exit(EXIT_ERROR)

    if json_output:
        result = query_events(filters, "json", config.village_dir)
        if isinstance(result, str):
            click.echo(result)
        else:
            click.echo(query_result_to_json(result))
    else:
        result = query_events(filters, "table", config.village_dir)
        click.echo(result)


@village.command()
@click.argument("task_id")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def state(task_id: str, json_output: bool) -> None:
    """
    Show task state and history.

    Displays the current state and state transition history for a task.

    \b
    Non-mutating. Reads state from lock file.

    Examples:
        village state bd-a3f8
        village state bd-a3f8 --json

    Options:
        --json: Output as JSON instead of human-readable table

    Exit codes:
        0: State found and displayed
        4: Task not found (no lock file)
    """
    from village.state_machine import TaskStateMachine

    config = get_config()
    state_machine = TaskStateMachine(config)

    current_state = state_machine.get_state(task_id)
    history = state_machine.get_state_history(task_id)

    if current_state is None and not history:
        click.echo(f"Task {task_id} not found (no lock file)", err=True)
        sys.exit(EXIT_BLOCKED)

    if json_output:
        output = {
            "task_id": task_id,
            "current_state": current_state.value if current_state else None,
            "history": [
                {
                    "ts": h.ts,
                    "from_state": h.from_state.value if h.from_state else None,
                    "to_state": h.to_state.value,
                    "context": h.context,
                }
                for h in history
            ],
        }
        click.echo(json.dumps(output, sort_keys=True, indent=2))
    else:
        click.echo(f"Task: {task_id}")
        click.echo(f"Current State: {current_state.value if current_state else 'None'}")

        if history:
            click.echo("\nState History:")
            for h in history:
                from_str = h.from_state.value if h.from_state else "initial"
                click.echo(f"  {h.ts}: {from_str} → {h.to_state.value}")
                if h.context:
                    for key, value in h.context.items():
                        click.echo(f"    {key}: {value}")
        else:
            click.echo("\nNo state history available")


@village.command()
@click.argument("task_id")
@click.option("--force", is_flag=True, help="Force pause without validation")
def pause(task_id: str, force: bool) -> None:
    """
    Pause an in-progress task.

    Pauses a task that is currently in progress. Only valid from IN_PROGRESS state.

    \b
    Mutating. Updates lock file with PAUSED state.

    Examples:
        village pause bd-a3f8
        village pause bd-a3f8 --force

    Options:
        --force: Skip state validation (bypass IN_PROGRESS check)

    Exit codes:
        0: Task paused successfully
        4: Task not in IN_PROGRESS state
        5: Task not found
    """
    from village.state_machine import TaskState, TaskStateMachine

    config = get_config()
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


@village.command("resume-task")
@click.argument("task_id")
@click.option("--force", is_flag=True, help="Force resume without validation")
def resume_task(task_id: str, force: bool) -> None:
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

    Options:
        --force: Skip state validation (bypass PAUSED check)

    Exit codes:
        0: Task resumed successfully
        4: Task not in PAUSED state
        5: Task not found
    """
    from village.state_machine import TaskState, TaskStateMachine

    config = get_config()
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


@village.command()
@click.option("--backend", type=click.Choice(["prometheus", "statsd"]), help="Metrics backend")
@click.option("--port", type=int, help="Port for metrics export")
@click.option("--interval", type=int, help="Export interval in seconds")
@click.option("--reset", is_flag=True, help="Reset all metrics counters to 0")
def metrics(backend: str, port: int | None, interval: int | None, reset: bool) -> None:
    """
    Export Village metrics.

    Exports metrics to Prometheus (HTTP) or StatsD (UDP).
    Metrics include workers, queue length, locks, orphans.

    \b
    Non-mutating. Collects metrics from Village state.

    Examples:
        village metrics                           # Export with config defaults
        village metrics --backend prometheus --port 9090
        village metrics --backend statsd
        village metrics --reset                      # Reset counters (future)

    Backend options:
        --backend prometheus: Prometheus HTTP endpoint
        --backend statsd: StatsD UDP socket

    Other options:
        --port: Port for Prometheus server (default: from config)
        --interval: Export interval in seconds (default: from config)
        --reset: Reset all metrics counters to 0 (for testing)

    Default: One-time export using configured backend
    """
    if reset and backend:
        click.echo(
            "Error: --reset and --backend are mutually exclusive. "
            "Use --reset to clear counters, or --backend to export metrics.",
            err=True,
        )
        sys.exit(EXIT_ERROR)

    from village.metrics import MetricsCollector

    config = get_config()

    if reset:
        collector = MetricsCollector(config, session_name=None)
        collector.reset_all()

        click.echo("Metrics counters reset to 0")
        return

    backend_choice = backend or config.metrics.backend

    collector = MetricsCollector(config)

    if backend_choice == "prometheus":
        prometheus_metrics = collector.export_prometheus()
        click.echo(f"Prometheus metrics:\n{prometheus_metrics}")
    elif backend_choice == "statsd":
        statsd_metrics = collector.export_statsd()
        click.echo(f"StatsD metrics:\n{statsd_metrics}")
    else:
        click.echo(f"Unknown backend: {backend_choice}")
        sys.exit(EXIT_ERROR)
