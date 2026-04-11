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


from village.cli import (  # noqa: E402
    acp,
    builder,
    council,
    doctor,
    goals,
    greeter,
    lifecycle,
    planner,
    scribe,
    tasks,
    watcher,
)

# Lifecycle commands (top-level)
for cmd_name in ["new", "up", "down"]:
    village.add_command(lifecycle.lifecycle_group.commands[cmd_name])

# Goals (top-level)
village.add_command(goals.goals, name="goals")

# Greeter and aliases
village.add_command(greeter.greeter, name="greeter")
village.add_command(greeter.greeter, name="welcome")
village.add_command(greeter.greeter, name="chat")
village.add_command(greeter.greeter, name="help")

# ACP (top-level)
village.add_command(acp.acp_command, name="acp")

# Tasks (top-level)
village.add_command(tasks.tasks, name="tasks")

# Roles
village.add_command(watcher.watcher_group, name="watcher")
village.add_command(builder.builder_group, name="builder")
village.add_command(scribe.scribe_group, name="scribe")
village.add_command(planner.planner_group, name="planner")
village.add_command(council.council_group, name="council")
village.add_command(doctor.doctor_group, name="doctor")
