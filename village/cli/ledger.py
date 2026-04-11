import json
import sys

import click

from village.config import get_config
from village.errors import EXIT_ERROR
from village.logging import get_logger
from village.roles import run_role_chat
from village.trace import TraceReader, format_trace

logger = get_logger(__name__)


@click.group(invoke_without_command=True)
@click.pass_context
def ledger_group(ctx: click.Context) -> None:
    """Task audit ledger commands."""
    if ctx.invoked_subcommand is not None:
        return
    run_role_chat("ledger")


@ledger_group.command("show")
@click.argument("task_id", required=False)
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def show_ledger(task_id: str | None, as_json: bool) -> None:
    """View audit ledger for a task."""
    config = get_config()
    reader = TraceReader(config.traces_dir)

    if task_id is None:
        task_ids = reader.list_traced_tasks()
        if not task_ids:
            click.echo("No ledgers found.")
            return
        click.echo("Traced tasks:")
        for i, tid in enumerate(task_ids, 1):
            click.echo(f"  {i}. {tid}")
        choice = click.prompt("Which task?", type=int)
        if choice < 1 or choice > len(task_ids):
            raise click.ClickException("Invalid selection")
        task_id = task_ids[choice - 1]

    assert task_id is not None
    events = reader.read(task_id)

    if not events:
        click.echo(f"No ledger events for {task_id}")
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


@ledger_group.command("list")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def list_ledgers(as_json: bool) -> None:
    """List tasks with audit ledgers."""
    config = get_config()
    reader = TraceReader(config.traces_dir)
    task_ids = reader.list_traced_tasks()

    if not task_ids:
        click.echo("No ledgers found")
        return

    if as_json:
        click.echo(json.dumps(task_ids, indent=2))
    else:
        for task_id in task_ids:
            click.echo(task_id)
