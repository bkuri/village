"""ACP commands: server and client management."""

import click

from village.config import get_config
from village.logging import get_logger

logger = get_logger(__name__)


@click.group(name="acp")
def acp_group() -> None:
    """ACP (Agent Client Protocol) management."""
    pass


# === Server Commands ===


@acp_group.group("server")
def server_group() -> None:
    """ACP server management."""
    pass


@server_group.command("start")
@click.option("--host", default=None, help="Server host (default: from config)")
@click.option("--port", default=None, type=int, help="Server port (default: from config)")
@click.option("--daemon", is_flag=True, help="Run as daemon")
def server_start(host: str | None, port: int | None, daemon: bool) -> None:
    """
    Start ACP server.

    Launches Village as an ACP-compliant agent server that editors
    can connect to.

    Examples:
      village acp server start
      village acp server start --host 0.0.0.0 --port 9999
      village acp server start --daemon
    """
    from village.acp.agent import run_village_agent

    config = get_config()

    # Use config defaults if not specified
    server_host = host or config.acp.server_host
    server_port = port or config.acp.server_port

    if not config.acp.enabled:
        click.echo("Warning: ACP is disabled in config. Set [acp] enabled = true to enable.")

    click.echo(f"Starting ACP server on {server_host}:{server_port}")

    if daemon:
        click.echo("Daemon mode not yet implemented")
        return

    # Run the agent server
    try:
        run_village_agent(config)
    except KeyboardInterrupt:
        click.echo("\nServer stopped")


@server_group.command("stop")
def server_stop() -> None:
    """
    Stop ACP server.

    Gracefully shuts down the running ACP server.

    Examples:
      village acp server stop
    """
    # TODO: Implement server stop (need PID tracking)
    click.echo("Server stop not yet implemented")


@server_group.command("status")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def server_status(json_output: bool) -> None:
    """
    Show ACP server status.

    Examples:
      village acp server status
      village acp server status --json
    """
    import json

    config = get_config()

    status_data = {
        "enabled": config.acp.enabled,
        "host": config.acp.server_host,
        "port": config.acp.server_port,
        "protocol_version": config.acp.protocol_version,
        "capabilities": [{"name": cap.name, "description": cap.description} for cap in config.acp.capabilities],
        "running": False,  # TODO: Check if server is actually running
    }

    if json_output:
        click.echo(json.dumps(status_data, indent=2))
    else:
        click.echo(f"ACP Server Status:")
        click.echo(f"  Enabled: {status_data['enabled']}")
        click.echo(f"  Host: {status_data['host']}")
        click.echo(f"  Port: {status_data['port']}")
        click.echo(f"  Protocol Version: {status_data['protocol_version']}")
        click.echo(f"  Running: {status_data['running']}")
        if status_data["capabilities"]:
            click.echo(f"  Capabilities:")
            for cap in status_data["capabilities"]:
                click.echo(f"    - {cap['name']}: {cap['description']}")


# === Client Commands ===


@acp_group.group("client")
def client_group() -> None:
    """ACP client management."""
    pass


@client_group.command("list")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def client_list(json_output: bool) -> None:
    """
    List configured ACP agents.

    Shows all agents with type=acp from configuration.

    Examples:
      village acp client list
      village acp client list --json
    """
    import json

    config = get_config()

    # Filter ACP agents
    acp_agents = {name: agent for name, agent in config.agents.items() if agent.type == "acp"}

    if json_output:
        agents_data = {}
        for name, agent in acp_agents.items():
            agents_data[name] = {
                "type": agent.type,
                "command": agent.acp_command,
                "capabilities": agent.acp_capabilities,
            }
        click.echo(json.dumps(agents_data, indent=2))
    else:
        if not acp_agents:
            click.echo("No ACP agents configured")
            click.echo("\nTo add an ACP agent, add to .village/config:")
            click.echo("  [agent.claude]")
            click.echo("  type = acp")
            click.echo("  acp_command = claude-code")
            click.echo("  acp_capabilities = filesystem,terminal")
            return

        click.echo(f"Configured ACP Agents ({len(acp_agents)}):\n")
        for name, agent in acp_agents.items():
            click.echo(f"  {name}:")
            click.echo(f"    Command: {agent.acp_command}")
            click.echo(f"    Capabilities: {', '.join(agent.acp_capabilities)}")


@client_group.command("spawn")
@click.argument("agent_name")
@click.option("--test", is_flag=True, help="Test connection after spawn")
def client_spawn(agent_name: str, test: bool) -> None:
    """
    Spawn an ACP agent.

    Starts a specific ACP agent by name from configuration.

    Examples:
      village acp client spawn claude
      village acp client spawn claude --test
    """
    import asyncio

    from village.acp.external_client import spawn_acp_agent, test_acp_agent

    config = get_config()

    # Check agent exists and is ACP type
    if agent_name not in config.agents:
        raise click.ClickException(f"Agent not found: {agent_name}")

    agent_config = config.agents[agent_name]
    if agent_config.type != "acp":
        raise click.ClickException(f"Agent '{agent_name}' is not an ACP agent (type={agent_config.type})")

    if not agent_config.acp_command:
        raise click.ClickException(f"Agent '{agent_name}' has no acp_command configured")

    click.echo(f"Spawning ACP agent: {agent_name}")
    click.echo(f"  Command: {agent_config.acp_command}")

    if test:
        click.echo("\nTesting connection...")

        async def run_test():
            success = await test_acp_agent(agent_config.acp_command or "")
            return success

        success = asyncio.run(run_test())

        if success:
            click.echo("✓ Agent test successful")
        else:
            click.echo("✗ Agent test failed", err=True)
            raise click.ClickException("Agent test failed")
    else:
        click.echo("\nNote: Use --test to verify agent connection")
        click.echo("Actual spawning not yet implemented (requires session context)")
