"""Maintenance commands: cleanup, unlock."""

import sys

import click

from village.config import get_config
from village.logging import get_logger

logger = get_logger(__name__)


@click.command()
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
            items_to_remove += len(cleanup_plan.orphan_worktrees) + len(cleanup_plan.stale_worktrees)
        click.echo(f"(preview: would remove {items_to_remove} item(s))")
        return

    # Execute cleanup
    execute_cleanup(cleanup_plan, config)

    removed_count = len(cleanup_plan.stale_locks)
    if apply:
        removed_count += len(cleanup_plan.orphan_worktrees) + len(cleanup_plan.stale_worktrees)

    click.echo("Cleanup complete")


@click.command()
@click.argument("task_id", default=None, required=False, type=str)
@click.option("--force", is_flag=True, help="Force unlock even if pane is active")
@click.option("--select", "select_mode", is_flag=True, help="Select from list interactively")
def unlock(task_id: str | None, force: bool, select_mode: bool) -> None:
    """
    Unlock a task (remove lock file).

    Raises:
        click.ClickException: If lock is ACTIVE and --force not provided
    """
    from village.interactive import select_from_list
    from village.locks import is_active, parse_lock
    from village.status import collect_workers

    config = get_config()

    if task_id is None or select_mode:
        workers = collect_workers(config.tmux_session)
        if not workers:
            click.echo("No locks found")
            if task_id is None:
                sys.exit(0)
            return

        selected = select_from_list(
            workers,
            "Select task to unlock:",
            formatter=lambda w: f"{w.task_id} ({w.status})",
        )
        if selected is None:
            click.echo("Canceled")
            sys.exit(0)
        task_id = selected.task_id

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
