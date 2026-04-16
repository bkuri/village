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


@click.group(invoke_without_command=True)
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
@click.option(
    "--transport",
    type=click.Choice(["cli", "telegram", "acp", "stdio"]),
    default=None,
    help="Start transport daemon mode",
)
@click.version_option(version=__version__)
@click.pass_context
def village(ctx: click.Context, verbose: bool, transport: str | None) -> None:
    """Village - CLI-native parallel development orchestrator."""
    import asyncio

    setup_logging(verbose=verbose)
    clear_pane_cache()
    signal.signal(signal.SIGINT, _handle_interrupt)
    ctx.ensure_object(dict)

    if ctx.invoked_subcommand is None:
        from village.config import get_config

        config = get_config()
        transport_mode = transport or config.transport.default

        if transport_mode != "cli":
            if transport_mode == "telegram":
                from village.cli.greeter import run_greeter

                asyncio.run(run_greeter(config, "telegram", model=None, no_system_prompt=False))
            elif transport_mode == "acp":
                import sys

                if sys.stdin.isatty():
                    click.echo(
                        "ACP transport requires a client connection.\n"
                        "Pipe stdin or use an ACP-compatible editor/agent:\n"
                        "  village --transport acp < input.json\n"
                        "  opencode --mcp village --transport acp\n"
                        "Or run a specific command: village greeter, village tasks, etc."
                    )
                    return

                from village.chat.transports.acp import ACPTransportAgent
                from village.dispatch import start_command_executor, stop_command_executor

                async def _run_acp() -> None:
                    start_command_executor()
                    try:
                        from acp import run_agent

                        agent = ACPTransportAgent(config)
                        await run_agent(agent)
                    finally:
                        stop_command_executor()

                asyncio.run(_run_acp())
            elif transport_mode == "stdio":
                from village.chat.transports.stdio import run_stdio_transport
                from village.dispatch import start_command_executor, stop_command_executor

                async def _run_stdio() -> None:
                    start_command_executor()
                    try:
                        await run_stdio_transport(config)
                    finally:
                        stop_command_executor()

                asyncio.run(_run_stdio())
            return


from village.cli import (  # noqa: E402
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

# Tasks (top-level)
village.add_command(tasks.tasks, name="tasks")

# Roles
village.add_command(watcher.watcher_group, name="watcher")
village.add_command(builder.builder_group, name="builder")
village.add_command(scribe.scribe_group, name="scribe")
village.add_command(planner.planner_group, name="planner")
village.add_command(council.council_group, name="council")
village.add_command(doctor.doctor_group, name="doctor")
