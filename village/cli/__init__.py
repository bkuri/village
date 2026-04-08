"""Village CLI - modular command structure."""

import signal

import click

from village import __version__
from village.errors import InterruptedResume
from village.logging import get_logger, setup_logging
from village.probes.tmux import clear_pane_cache

logger = get_logger(__name__)


def _handle_interrupt(signum: int, frame: object) -> None:
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
    ctx.ensure_object(dict)


from village import old_cli  # noqa: E402
from village.cli import acp, doctor, elder, lifecycle, state  # noqa: E402

for cmd_name in ["new", "up", "down"]:
    village.add_command(lifecycle.lifecycle_group.commands[cmd_name])

village.add_command(state.state_group)
village.add_command(elder.elder_group, name="elder")
village.add_command(acp.acp_command, name="gate")
village.add_command(acp.acp_command)
village.add_command(doctor.doctor_command)

for cmd in [
    old_cli.queue,
    old_cli.resume,
    old_cli.pause,
    old_cli.resume_task,
    old_cli.ready,
    old_cli.dashboard,
    old_cli.metrics,
    old_cli.cleanup,
    old_cli.unlock,
    old_cli.release,
    old_cli.chat,
    old_cli.drafts,
    old_cli.status,
    old_cli.state,
]:
    village.add_command(cmd)

village.add_command(old_cli.dashboard, name="square")
village.add_command(old_cli.cleanup, name="sweep")
village.add_command(old_cli.chat, name="council")
village.add_command(old_cli.status, name="census")
village.add_command(old_cli.state, name="archives")
