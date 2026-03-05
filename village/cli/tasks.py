"""Task management commands: queue, resume, pause, resume-task, ready."""

import sys
from datetime import datetime, timezone

import click

from village.config import get_config
from village.errors import EXIT_SUCCESS
from village.logging import get_logger

logger = get_logger(__name__)


@click.group(name="tasks")
def tasks_group() -> None:
    """Task management."""
    pass


# Import implementations from old cli.py during migration
# TODO: Move full implementations here
from village import cli as _old_cli

# Register commands with new group
tasks_group.add_command(_old_cli.queue)
tasks_group.add_command(_old_cli.resume)
tasks_group.add_command(_old_cli.pause)
tasks_group.add_command(_old_cli.resume_task)
tasks_group.add_command(_old_cli.ready)
