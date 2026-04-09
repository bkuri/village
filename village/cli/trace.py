"""Task audit trail commands."""

import json
import sys

import click

from village.config import get_config
from village.errors import EXIT_ERROR
from village.logging import get_logger
from village.trace import TraceReader, format_trace

logger = get_logger(__name__)


@click.group()
def trace_group() -> None:
    """Task audit trail commands."""
    pass


@trace_group.command("show")
@click.argument("task_id")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def show_trace(task_id: str, as_json: bool) -> None:
    """View audit trail for a task."""
    config = get_config()
    reader = TraceReader(config.traces_dir)
    events = reader.read(task_id)

    if not events:
        click.echo(f"No trace events for {task_id}")
        sys.exit(EXIT_ERROR)

    if as_json:
        data = []
        for event in events:
            data.append(
                {
                    "timestamp": event.timestamp,
                    "event_type": event.event_type.value,
                    "task_id": event.task_id,
                    "agent": event.agent,
                    "data": event.data,
                    "sequence": event.sequence,
                }
            )
        click.echo(json.dumps(data, indent=2, sort_keys=True))
    else:
        click.echo(format_trace(events))


@trace_group.command("list")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def list_traces(as_json: bool) -> None:
    """List tasks with traces."""
    config = get_config()
    reader = TraceReader(config.traces_dir)
    task_ids = reader.list_traced_tasks()

    if not task_ids:
        click.echo("No traces found")
        return

    if as_json:
        click.echo(json.dumps(task_ids, indent=2))
    else:
        for task_id in task_ids:
            click.echo(task_id)
