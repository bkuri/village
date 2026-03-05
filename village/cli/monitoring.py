"""Monitoring commands: dashboard, metrics."""

import sys
from datetime import datetime, timedelta, timezone

import click

from village.config import get_config
from village.logging import get_logger

logger = get_logger(__name__)


@click.group(name="monitoring")
def monitoring_group() -> None:
    """Runtime monitoring."""
    pass


# Import implementations from old cli.py during migration
from village import cli as _old_cli

monitoring_group.add_command(_old_cli.dashboard)
monitoring_group.add_command(_old_cli.metrics)
