"""State inspection commands: status, locks, events, state."""

import json
import sys

import click

from village.config import get_config
from village.errors import EXIT_BLOCKED
from village.logging import get_logger
from village.probes.tmux import session_exists
from village.status import collect_full_status, collect_workers

logger = get_logger(__name__)


@click.command()
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


@click.command()
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


@click.command()
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
    all_events = read_events(config.village_dir)

    # Apply filters
    if task_id:
        all_events = [e for e in all_events if e.task_id and task_id in e.task_id]
    if cmd_filter:
        all_events = [e for e in all_events if e.cmd and cmd_filter in e.cmd]

    # Limit
    all_events = all_events[-limit:] if len(all_events) > limit else all_events

    if json_output:
        # JSON output
        output = []
        for event in all_events:
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
        if not all_events:
            click.echo("No events found")
            return

        for event in all_events:
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


@click.command()
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
