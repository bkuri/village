"""Chat commands: chat, drafts."""

import sys

import click

from village.config import get_config
from village.logging import get_logger

logger = get_logger(__name__)


@click.group(name="chat")
def chat_group() -> None:
    """Interactive chat interface."""
    pass


# Import implementations from old cli.py during migration
from village import cli as _old_cli

chat_group.add_command(_old_cli.chat)
chat_group.add_command(_old_cli.drafts)
