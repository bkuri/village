"""Village CLI entrypoint."""

import click

from village.config import get_config
from village.logging import get_logger, setup_logging
from village.probes.tmux import clear_pane_cache, session_exists
from village.render.text import render_initialization_plan
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
