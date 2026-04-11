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
    dashboard,
    doctor,
    elder,
    greeter,
    ledger,
    lifecycle,
    maintenance,
    planner,
    release,
    state,
    tasks,
    work,
)

# Lifecycle commands
for cmd_name in ["new", "up", "down"]:
    village.add_command(lifecycle.lifecycle_group.commands[cmd_name])

village.add_command(lifecycle.lifecycle_group.commands["up"], name="onboard")

# State inspection commands
village.add_command(state.status)
village.add_command(state.locks)
village.add_command(state.events)
village.add_command(state.state)

# Work management commands
village.add_command(work.queue)
village.add_command(work.resume)
village.add_command(work.pause)
village.add_command(work.resume_task)
village.add_command(work.ready)

# Maintenance commands
village.add_command(maintenance.cleanup)
village.add_command(maintenance.unlock)

# Dashboard and metrics
village.add_command(dashboard.dashboard)
village.add_command(dashboard.metrics)

# Release
village.add_command(release.release)

# Greeter and drafts
village.add_command(greeter.greeter, name="greeter")
village.add_command(greeter.drafts)

# Elder
village.add_command(elder.elder_group, name="elder")

# ACP
village.add_command(acp.acp_command, name="gate")
village.add_command(acp.acp_command)

# Doctor
village.add_command(doctor.doctor_command)

# Planner (workflow design)
village.add_command(planner.planner_group, name="planner")

# Builder (workflow execution)
village.add_command(builder.builder_group, name="builder")

# Council
village.add_command(council.council_group, name="council")

# Ledger (audit trail)
village.add_command(ledger.ledger_group, name="ledger")

# Tasks (built-in task store)
village.add_command(tasks.tasks, name="tasks")

# Backward-compatible aliases
village.add_command(planner.planner_group, name="workflow")
village.add_command(ledger.ledger_group, name="trace")
village.add_command(greeter.greeter, name="help")
village.add_command(greeter.greeter, name="chat")
village.add_command(tasks.tasks, name="bd")

# Other aliases
village.add_command(dashboard.dashboard, name="square")
village.add_command(maintenance.cleanup, name="sweep")
village.add_command(state.status, name="census")
village.add_command(state.state, name="archives")
