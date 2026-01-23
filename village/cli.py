"""Village CLI entrypoint."""

import click

from village.config import get_config
from village.logging import get_logger, setup_logging
from village.probes.tmux import clear_pane_cache, session_exists

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
def status(short: bool, json_output: bool) -> None:
    """
    Show village status.

    Non-mutating. Probes actual state, doesn't create directories.
    """
    config = get_config()

    # Probe tmux session
    tmux_running = session_exists(config.tmux_session)

    # Probe lock directory (non-mutating)
    lock_files = list(config.locks_dir.glob("*.lock")) if config.locks_dir.exists() else []

    # Probe config file existence
    config_exists = config.config_exists()

    if json_output:
        import json

        output = {
            "command": "status",
            "version": 1,
            "tmux": {
                "session": config.tmux_session,
                "running": tmux_running,
            },
            "config": {
                "exists": config_exists,
                "path": str(config.config_path),
            },
            "locks": {
                "directory": str(config.locks_dir),
                "exists": config.locks_dir.exists(),
                "count": len(lock_files),
            },
            "worktrees": {
                "directory": str(config.worktrees_dir),
                "exists": config.worktrees_dir.exists(),
            },
        }
        click.echo(json.dumps(output, sort_keys=True))
    elif short:
        # Minimal status: tmux + locks only
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
        # Full status (placeholder for Phase 4)
        click.echo(f"Village directory: {config.village_dir}")
        click.echo(
            f"TMUX session: {config.tmux_session} {'running' if tmux_running else 'not running'}"
        )
        click.echo(f"Lock files: {len(lock_files)}")
        click.echo(f"Config file: {'exists' if config_exists else 'not created'}")


@village.command()
def up() -> None:
    """
    Initialize village runtime.

    Mutating. Creates directories and config.

    NOTE: Full implementation in Phase 6.
    """
    config = get_config()
    config.ensure_exists()
    click.echo(f"Runtime initialized at {config.village_dir}")


@village.command()
def locks() -> None:
    """List all locks with ACTIVE/STALE status."""
    from village.locks import evaluate_locks, parse_lock

    config = get_config()
    lock_files = list(config.locks_dir.glob("*.lock"))

    if not lock_files:
        click.echo("No locks found")
        return

    parsed_locks = []
    for lock_file in lock_files:
        lock = parse_lock(lock_file)
        if lock:
            parsed_locks.append(lock)

    # Evaluate status
    status_map = evaluate_locks(parsed_locks, config.tmux_session)

    # Display
    for lock in parsed_locks:
        status = "ACTIVE" if status_map[lock.task_id] else "STALE"
        click.echo(f"{lock.task_id}: {status} (pane: {lock.pane_id})")


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
