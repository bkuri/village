"""Maintenance commands: cleanup, unlock, release."""


import click

from village.logging import get_logger

logger = get_logger(__name__)


@click.group(name="maintenance")
def maintenance_group() -> None:
    """System maintenance."""
    pass


# Import implementations from old cli.py during migration
from village import cli as _old_cli

maintenance_group.add_command(_old_cli.cleanup)
maintenance_group.add_command(_old_cli.unlock)
maintenance_group.add_command(_old_cli.release)
