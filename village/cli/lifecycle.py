"""Lifecycle commands: new, up, down."""

from datetime import datetime, timezone

import click

from village.config import get_config
from village.event_log import Event, append_event
from village.logging import get_logger
from village.probes.tmux import session_exists
from village.render.text import render_initialization_plan
from village.runtime import collect_runtime_state, execute_initialization, plan_initialization

logger = get_logger(__name__)


@click.group(name="lifecycle")
def lifecycle_group() -> None:
    """Project lifecycle management."""
    pass


@lifecycle_group.command("new")
@click.argument("name")
@click.option("--path", "path", type=click.Path(), default=".", help="Parent directory (default: current directory)")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--plan", is_flag=True, help="Alias for --dry-run")
@click.option("--dashboard/--no-dashboard", "dashboard", default=True, help="Create dashboard window")
def new(name: str, path: str, dry_run: bool, plan: bool, dashboard: bool) -> None:
    """
    Create a new project with village support.

    Creates a new project directory with:
      - git init
      - .gitignore (with .village/, .worktrees/, .beads/ entries)
      - README.md stub
      - AGENTS.md template
      - .village/config with commented defaults
      - bd init (if beads available)
      - tmux session + dashboard window

    Errors if already inside a git repository (use `village up` instead).

    Examples:
      village new myproject
      village new myproject --path ~/projects
      village new myproject --dry-run
    """
    from pathlib import Path

    from village.scaffold import (
        execute_scaffold,
        is_inside_git_repo,
        plan_scaffold,
    )

    if dry_run or plan:
        parent_dir = Path(path).resolve()
        scaffold_plan = plan_scaffold(name, parent_dir)
        click.echo(f"Would create project: {scaffold_plan.project_dir}")
        click.echo("\nSteps:")
        for step in scaffold_plan.steps:
            click.echo(f"  - {step}")
        return

    if is_inside_git_repo():
        raise click.ClickException("Already inside a git repository. Use `village up` instead.")

    parent_dir = Path(path).resolve()
    result = execute_scaffold(name, parent_dir, dashboard=dashboard)

    if result.success:
        click.echo(f"Created project: {result.project_dir}")
        click.echo("\nCreated:")
        for item in result.created:
            click.echo(f"  - {item}")
        click.echo("\nNext steps:")
        click.echo(f"  cd {name}")
        click.echo("  village chat   # create your first task")
    else:
        click.echo(f"Failed to create project: {result.error}", err=True)
        raise click.ClickException(result.error or "Unknown error")


@lifecycle_group.command("up")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--plan", is_flag=True, help="Alias for --dry-run")
@click.option("--dashboard/--no-dashboard", "dashboard", default=True, help="Create dashboard window")
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


@lifecycle_group.command("down")
@click.option("--dry-run", is_flag=True, help="Show what would be killed")
@click.option("--plan", is_flag=True, help="Alias for --dry-run")
def down(dry_run: bool, plan: bool) -> None:
    """
    Stop village runtime.

    Kills tmux session only (doesn't delete work data).
    Safe to run while workers are active (they'll be detached).

    Supports: --dry-run, --plan (preview mode)
    """
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
