"""ACP CLI commands for Village.

Provides stdio-first ACP agent interface:
- village acp                    # Run stdio agent (for editors)
- village acp --list-agents      # List configured ACP agents
- village acp --test <agent>     # Test connection to agent
"""

import asyncio
import json
import logging

import click

from village.config import get_config
from village.errors import EXIT_ERROR

logger = logging.getLogger(__name__)


@click.command(name="acp")
@click.option("--list-agents", is_flag=True, help="List configured ACP agents")
@click.option("--test", "test_agent", metavar="<agent>", help="Test connection to ACP agent")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def acp_command(
    ctx: click.Context,
    list_agents: bool,
    test_agent: str | None,
    json_output: bool,
) -> None:
    """ACP (Agent Client Protocol) stdio agent.

    By default, runs Village as an ACP agent over stdio for editors.
    Editors like Zed spawn 'village acp' and communicate via JSON-RPC.

    \b
    Examples:
        village acp                    # Run stdio agent (for editors)
        village acp --list-agents      # List configured ACP agents
        village acp --test claude      # Test connection to claude agent
        village acp --json             # JSON output
    """
    if list_agents:
        _list_agents(json_output)
    elif test_agent:
        _test_agent(test_agent, json_output)
    else:
        _run_stdio_agent(json_output)


def _run_stdio_agent(json_output: bool) -> None:
    """Run Village as stdio ACP agent."""
    from village.acp.agent import run_village_agent

    config = get_config()

    if not config.acp.enabled:
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "status": "disabled",
                        "message": "ACP not enabled. Add [acp] enabled = true to .village/config",
                    }
                )
            )
        else:
            click.echo("ACP is disabled in configuration", err=True)
            click.echo("Enable it by adding to .village/config:", err=True)
            click.echo("  [acp]", err=True)
            click.echo("  enabled = true", err=True)
        raise click.exceptions.Exit(EXIT_ERROR)

    try:
        asyncio.run(run_village_agent(config))
    except KeyboardInterrupt:
        if json_output:
            click.echo(json.dumps({"status": "stopped"}))
        else:
            logger.info("ACP agent stopped")
    except Exception as e:
        logger.exception(f"ACP agent error: {e}")
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "status": "error",
                        "error": str(e),
                    }
                )
            )
        else:
            click.echo(f"Error: {e}", err=True)
        raise click.exceptions.Exit(EXIT_ERROR)


def _list_agents(json_output: bool) -> None:
    """List configured ACP agents."""
    config = get_config()

    acp_agents = {name: agent for name, agent in config.agents.items() if agent.type == "acp"}

    if json_output:
        click.echo(
            json.dumps(
                {
                    "agents": [
                        {
                            "name": name,
                            "command": agent.acp_command or "",
                            "capabilities": agent.acp_capabilities,
                        }
                        for name, agent in acp_agents.items()
                    ],
                    "count": len(acp_agents),
                },
                indent=2,
            )
        )
    else:
        if not acp_agents:
            click.echo("No ACP agents configured")
            click.echo("")
            click.echo("Add an ACP agent to .village/config:")
            click.echo("  [agent.claude]")
            click.echo("  type = acp")
            click.echo("  acp_command = claude-code")
            click.echo("  acp_capabilities = filesystem,terminal")
        else:
            click.echo(f"Configured ACP Agents ({len(acp_agents)}):")
            click.echo("")
            for name, agent in acp_agents.items():
                click.echo(f"  {name}:")
                click.echo(f"    Command: {agent.acp_command or '(not set)'}")
                if agent.acp_capabilities:
                    click.echo(f"    Capabilities: {', '.join(agent.acp_capabilities)}")
                else:
                    click.echo("    Capabilities: (none)")
                click.echo("")


def _test_agent(agent_name: str, json_output: bool) -> None:
    """Test connection to an ACP agent."""
    from village.acp.external_client import verify_acp_agent

    config = get_config()

    if agent_name not in config.agents:
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "status": "error",
                        "error": f"Agent '{agent_name}' not found",
                        "available_agents": list(config.agents.keys()),
                    }
                )
            )
        else:
            click.echo(f"Error: Agent '{agent_name}' not found", err=True)
            click.echo(f"Available: {', '.join(config.agents.keys()) or '(none)'}", err=True)
        raise click.exceptions.Exit(EXIT_ERROR)

    agent_config = config.agents[agent_name]

    if agent_config.type != "acp" or not agent_config.acp_command:
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "status": "error",
                        "error": f"Agent '{agent_name}' is not a valid ACP agent",
                    }
                )
            )
        else:
            click.echo(f"Error: '{agent_name}' is not a valid ACP agent", err=True)
        raise click.exceptions.Exit(EXIT_ERROR)

    if json_output:
        click.echo(
            json.dumps(
                {
                    "status": "testing",
                    "agent": agent_name,
                }
            )
        )

    try:
        success = asyncio.run(verify_acp_agent(agent_config.acp_command))

        if json_output:
            click.echo(
                json.dumps(
                    {
                        "status": "success" if success else "failed",
                        "agent": agent_name,
                    }
                )
            )
        else:
            if success:
                click.echo(f"✓ Agent '{agent_name}' test successful")
            else:
                click.echo(f"✗ Agent '{agent_name}' test failed", err=True)
                raise click.exceptions.Exit(EXIT_ERROR)

    except Exception as e:
        logger.exception(f"Agent test failed: {e}")
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "status": "error",
                        "error": str(e),
                    }
                )
            )
        else:
            click.echo(f"Error: {e}", err=True)
        raise click.exceptions.Exit(EXIT_ERROR)
