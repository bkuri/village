"""State inspection commands: status, locks, events, state."""

import json

import click

from village.config import get_config
from village.logging import get_logger
from village.probes.tmux import session_exists
from village.status import collect_full_status, collect_workers

logger = get_logger(__name__)


@click.group(name="state")
def state_group() -> None:
    """Inspect village state."""
    pass


@state_group.command()
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


@state_group.command()
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


@state_group.command()
@click.option("--task", "task_id", help="Filter by task ID")
@click.option("--cmd", "cmd_filter", help="Filter by command")
@click.option("--limit", "limit", default=20, help="Number of events to show")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def events(
    task_id: str | None,
    cmd_filter: str | None,
    limit: int,
    json_output: bool,
) -> None:
    """
    Show recent events.

    Non-mutating. Reads from event log.

    Examples:
      village events
      village events --task bd-4uv
      village events --cmd resume --limit 50
      village events --json
    """
    from village.event_log import read_events

    config = get_config()

    # Read all events
    events = read_events(config.village_dir)

    # Apply filters
    if task_id:
        events = [e for e in events if e.task_id and task_id in e.task_id]
    if cmd_filter:
        events = [e for e in events if e.cmd and cmd_filter in e.cmd]

    # Limit
    events = events[-limit:] if len(events) > limit else events

    if json_output:
        # JSON output
        output = []
        for event in events:
            output.append(
                {
                    "ts": event.ts,
                    "cmd": event.cmd,
                    "task_id": event.task_id,
                    "pane": event.pane,
                    "result": event.result,
                    "error": event.error,
                }
            )
        click.echo(json.dumps(output, indent=2))
    else:
        # Text output
        if not events:
            click.echo("No events found")
            return

        for event in events:
            parts = [event.ts, event.cmd]
            if event.task_id:
                parts.append(event.task_id)
            if event.pane:
                parts.append(f"pane={event.pane}")
            if event.result:
                parts.append(f"result={event.result}")
            if event.error:
                parts.append(f"error={event.error}")
            click.echo(" ".join(parts))


@state_group.command()
@click.argument("task_id")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def state(task_id: str, json_output: bool) -> None:
    """
    Show task state machine state.

    Non-mutating. Reads from state file.

    Examples:
      village state bd-4uv
      village state bd-4uv --json
    """
    from village.state_machine import TaskStateMachine

    config = get_config()
    state_machine = TaskStateMachine(config)

    current_state = state_machine.get_state(task_id)

    if not current_state:
        raise click.ClickException(f"Task not found: {task_id}")

    if json_output:
        click.echo(json.dumps({"task_id": task_id, "state": current_state.value}))
    else:
        click.echo(f"Task {task_id}: {current_state.value}")
