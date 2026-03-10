"""Village CLI - modular command structure."""

import signal

import click

from village import __version__
from village.errors import InterruptedResume
from village.logging import get_logger, setup_logging
from village.probes.tmux import clear_pane_cache

logger = get_logger(__name__)


def _handle_interrupt(signum: int, frame: object) -> None:
    """Handle SIGINT (Ctrl+C)."""
    logger.info("Interrupted by user")
    raise InterruptedResume()


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
@click.version_option(version=__version__)
@click.pass_context
def village(ctx: click.Context, verbose: bool) -> None:
    """Village - CLI-native parallel development orchestrator."""
    setup_logging(verbose=verbose)
    clear_pane_cache()
    signal.signal(signal.SIGINT, _handle_interrupt)

    # Store common imports in context for subcommands
    ctx.ensure_object(dict)


# Import command groups
from village.cli import acp, doctor, lifecycle, state

# Register lifecycle commands directly (more intuitive: village up vs village lifecycle up)
for cmd_name in ["new", "up", "down"]:
    village.add_command(lifecycle.lifecycle_group.commands[cmd_name])

# Register other command groups
village.add_command(state.state_group)

# Register acp with village-themed alias 'gate'
village.add_command(acp.acp_command, name="gate")
village.add_command(acp.acp_command)

# Register doctor command
village.add_command(doctor.doctor_command)

# TODO: Migrate remaining commands from old cli.py:
# - tasks (queue, resume, pause, resume-task, ready)
# - monitoring (dashboard, metrics)
# - maintenance (cleanup, unlock, release)
# - chat (chat, drafts)

# Temporarily import old commands during migration
from village import old_cli

village.add_command(old_cli.queue)
village.add_command(old_cli.resume)
village.add_command(old_cli.pause)
village.add_command(old_cli.resume_task)
village.add_command(old_cli.ready)

# Register dashboard with village-themed alias 'square'
village.add_command(old_cli.dashboard, name="square")
village.add_command(old_cli.dashboard)

village.add_command(old_cli.metrics)

# Register cleanup with village-themed alias 'sweep'
village.add_command(old_cli.cleanup, name="sweep")
village.add_command(old_cli.cleanup)

village.add_command(old_cli.unlock)
village.add_command(old_cli.release)

# Register chat with village-themed alias 'council'
village.add_command(old_cli.chat, name="council")
village.add_command(old_cli.chat)

village.add_command(old_cli.drafts)

# Register status with village-themed alias 'census'
village.add_command(old_cli.status, name="census")
village.add_command(old_cli.status)

# Register state with village-themed alias 'archives'
village.add_command(old_cli.state, name="archives")
village.add_command(old_cli.state)
