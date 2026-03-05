"""ACP CLI commands for Village.

Provides commands for managing ACP server and client operations:
- village acp --server start/stop/status
- village acp --client list/spawn/test
"""

import json
import logging
from typing import Any

import click

from village.config import get_config

logger = logging.getLogger(__name__)


@click.command(name="acp")
@click.option("--server", "mode", flag_value="server", help="Server mode operations")
@click.option("--client", "mode", flag_value="client", help="Client mode operations")
@click.argument("command", required=False, default="status")
@click.argument("args", required=False)
@click.option("--host", default="localhost", help="Server host (default: localhost)")
@click.option("--port", default=9876, type=int, help="Server port (default: 9876)")
@click.option("--cwd", type=click.Path(), help="Working directory (for spawn)")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def acp_command(
    ctx: click.Context,
    mode: str | None,
    command: str,
    args: str | None,
    host: str,
    port: int,
    cwd: click.Path | None,
    json_output: bool,
) -> None:
    """ACP (Agent Client Protocol) integration commands.
    
    Village can act as either an ACP server (exposing Village to editors)
    or an ACP client (connecting to external agents like Claude Code).
    
    Server operations:
        village acp --server start [--host HOST] [--port PORT]
        village acp --server stop
        village acp --server status
    
    Client operations:
        village acp --client list
        village acp --client spawn <agent-name>
        village acp --client test <agent-name>
    """
    if mode is None:
        # Default: show status
        mode = "server"
        command = "status"
    
    if mode == "server":
        _handle_server_command(ctx, command, host, port, json_output)
    elif mode == "client":
        _handle_client_command(ctx, command, args, cwd, json_output)
    else:
        click.echo(f"Unknown mode: {mode}", err=True)
        raise click.exceptions.Exit(1)


def _handle_server_command(
    ctx: click.Context,
    command: str,
    host: str,
    port: int,
    json_output: bool,
) -> None:
    """Handle ACP server commands."""
    config = get_config()
    
    if command == "start":
        _server_start(config, host, port, json_output)
    elif command == "stop":
        _server_stop(json_output)
    elif command == "status":
        _server_status(config, json_output)
    else:
        click.echo(f"Unknown server command: {command}", err=True)
        click.echo("Available: start, stop, status")
        raise click.exceptions.Exit(1)


def _server_start(config: Any, host: str, port: int, json_output: bool) -> None:
    """Start ACP server."""
    import asyncio
    
    from village.acp.agent import run_village_agent
    
    # Override ACP config if specified
    if host != "localhost":
        config.acp.server_host = host
    if port != 9876:
        config.acp.server_port = port
    
    # Check if ACP is enabled in config
    if not config.acp.enabled:
        if json_output:
            click.echo(json.dumps({
                "status": "disabled",
                "message": "ACP not enabled in configuration. Add [acp] enabled = true to .village/config",
            }))
        else:
            click.echo("ACP server is disabled in configuration")
            click.echo("Enable it by adding to .village/config:")
            click.echo("  [acp]")
            click.echo("  enabled = true")
        return
    
    if json_output:
        click.echo(json.dumps({
            "status": "starting",
            "host": config.acp.server_host,
            "port": config.acp.server_port,
        }))
    else:
        click.echo(f"Starting ACP server on {config.acp.server_host}:{config.acp.server_port}")
    
    try:
        # Run the ACP agent (async)
        asyncio.run(run_village_agent(config))
    except KeyboardInterrupt:
        if json_output:
            click.echo(json.dumps({"status": "stopped"}))
        else:
            click.echo("\nACP server stopped")
    except Exception as e:
        logger.exception(f"Failed to start ACP server: {e}")
        if json_output:
            click.echo(json.dumps({
                "status": "error",
                "error": str(e),
            }))
        else:
            click.echo(f"Error starting ACP server: {e}", err=True)
            raise click.exceptions.Exit(1)


def _server_stop(json_output: bool) -> None:
    """Stop ACP server."""
    # TODO: Implement daemon mode with PID file for background server
    # For now, just use Ctrl+C on the running server
    
    if json_output:
        click.echo(json.dumps({
            "status": "not_implemented",
            "message": "Use Ctrl+C to stop foreground server",
        }))
    else:
        click.echo("ACP server runs in foreground mode")
        click.echo("Use Ctrl+C to stop the running server")
        click.echo("")
        click.echo("Future: daemon mode with 'village acp --server stop' will be supported")


def _server_status(config: Any, json_output: bool) -> None:
    """Show ACP server status."""
    status_data = {
        "enabled": config.acp.enabled,
        "host": config.acp.server_host,
        "port": config.acp.server_port,
        "protocol_version": config.acp.protocol_version,
        "capabilities": [
            {
                "name": cap.name,
                "description": cap.description,
            }
            for cap in config.acp.capabilities
        ],
    }
    
    if json_output:
        click.echo(json.dumps(status_data, indent=2))
    else:
        click.echo("ACP Server Configuration:")
        click.echo(f"  Status: {'enabled' if config.acp.enabled else 'disabled'}")
        click.echo(f"  Host: {config.acp.server_host}")
        click.echo(f"  Port: {config.acp.server_port}")
        click.echo(f"  Protocol Version: {config.acp.protocol_version}")
        
        if config.acp.capabilities:
            click.echo(f"\nCapabilities:")
            for cap in config.acp.capabilities:
                click.echo(f"  - {cap.name}: {cap.description}")
        else:
            click.echo(f"\nCapabilities: (none configured)")


def _handle_client_command(
    ctx: click.Context,
    command: str,
    args: str | None,
    cwd: click.Path | None,
    json_output: bool,
) -> None:
    """Handle ACP client commands."""
    config = get_config()
    
    if command == "list":
        _client_list(config, json_output)
    elif command == "spawn":
        if not args:
            click.echo("Error: agent-name required for spawn", err=True)
            click.echo("Usage: village acp --client spawn <agent-name>")
            raise click.exceptions.Exit(1)
        _client_spawn(config, args, cwd, json_output)
    elif command == "test":
        if not args:
            click.echo("Error: agent-name required for test", err=True)
            click.echo("Usage: village acp --client test <agent-name>")
            raise click.exceptions.Exit(1)
        _client_test(config, args, json_output)
    else:
        click.echo(f"Unknown client command: {command}", err=True)
        click.echo("Available: list, spawn, test")
        raise click.exceptions.Exit(1)


def _client_list(config: Any, json_output: bool) -> None:
    """List configured ACP agents."""
    # Filter ACP agents
    acp_agents = {
        name: agent
        for name, agent in config.agents.items()
        if agent.type == "acp"
    }
    
    agents_data = {
        "agents": [
            {
                "name": name,
                "command": agent.acp_command or "",
                "capabilities": agent.acp_capabilities,
            }
            for name, agent in acp_agents.items()
        ],
        "count": len(acp_agents),
    }
    
    if json_output:
        click.echo(json.dumps(agents_data, indent=2))
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
                    click.echo(f"    Capabilities: (none)")
                click.echo("")


def _client_spawn(config: Any, agent_name: str, cwd: click.Path | None, json_output: bool) -> None:
    """Spawn an ACP agent."""
    import asyncio
    
    from village.acp.external_client import spawn_acp_agent
    from village.errors import EXIT_ERROR
    
    # Check agent exists
    if agent_name not in config.agents:
        if json_output:
            click.echo(json.dumps({
                "status": "error",
                "error": f"Agent '{agent_name}' not found",
                "available_agents": list(config.agents.keys()),
            }))
        else:
            click.echo(f"Error: Agent '{agent_name}' not found", err=True)
            click.echo(f"Available agents: {', '.join(config.agents.keys()) or '(none)'}")
        raise click.exceptions.Exit(EXIT_ERROR)
    
    agent_config = config.agents[agent_name]
    
    # Check it's an ACP agent
    if agent_config.type != "acp":
        if json_output:
            click.echo(json.dumps({
                "status": "error",
                "error": f"Agent '{agent_name}' is not an ACP agent (type={agent_config.type})",
            }))
        else:
            click.echo(f"Error: Agent '{agent_name}' is not an ACP agent", err=True)
            click.echo(f"Agent type: {agent_config.type}")
        raise click.exceptions.Exit(EXIT_ERROR)
    
    # Check command is configured
    if not agent_config.acp_command:
        if json_output:
            click.echo(json.dumps({
                "status": "error",
                "error": f"Agent '{agent_name}' missing acp_command configuration",
            }))
        else:
            click.echo(f"Error: Agent '{agent_name}' missing acp_command", err=True)
        raise click.exceptions.Exit(EXIT_ERROR)
    
    if json_output:
        click.echo(json.dumps({
            "status": "spawning",
            "agent": agent_name,
            "command": agent_config.acp_command,
        }))
    else:
        click.echo(f"Spawning ACP agent: {agent_name}")
        click.echo(f"  Command: {agent_config.acp_command}")
        if cwd:
            click.echo(f"  Working directory: {cwd}")
    
    try:
        # Spawn the agent
        conn, proc = asyncio.run(spawn_acp_agent(
            agent_config.acp_command,
            cwd=cwd,
        ))
        
        if json_output:
            click.echo(json.dumps({
                "status": "spawned",
                "agent": agent_name,
                "connection": str(type(conn)),
                "process": str(type(proc)),
            }))
        else:
            click.echo(f"✓ Agent spawned successfully")
            click.echo(f"  Connection: {type(conn).__name__}")
            click.echo(f"  Process: {type(proc).__name__}")
            click.echo("")
            click.echo("Note: Agent is running. Use the connection object to interact.")
            
    except Exception as e:
        logger.exception(f"Failed to spawn agent: {e}")
        if json_output:
            click.echo(json.dumps({
                "status": "error",
                "error": str(e),
            }))
        else:
            click.echo(f"Error spawning agent: {e}", err=True)
        raise click.exceptions.Exit(EXIT_ERROR)


def _client_test(config: Any, agent_name: str, json_output: bool) -> None:
    """Test connection to an ACP agent."""
    import asyncio
    
    from village.acp.external_client import test_acp_agent
    from village.errors import EXIT_ERROR
    
    # Check agent exists
    if agent_name not in config.agents:
        if json_output:
            click.echo(json.dumps({
                "status": "error",
                "error": f"Agent '{agent_name}' not found",
            }))
        else:
            click.echo(f"Error: Agent '{agent_name}' not found", err=True)
        raise click.exceptions.Exit(EXIT_ERROR)
    
    agent_config = config.agents[agent_name]
    
    # Check it's an ACP agent
    if agent_config.type != "acp" or not agent_config.acp_command:
        if json_output:
            click.echo(json.dumps({
                "status": "error",
                "error": f"Agent '{agent_name}' is not a valid ACP agent",
            }))
        else:
            click.echo(f"Error: Agent '{agent_name}' is not a valid ACP agent", err=True)
        raise click.exceptions.Exit(EXIT_ERROR)
    
    if json_output:
        click.echo(json.dumps({
            "status": "testing",
            "agent": agent_name,
        }))
    else:
        click.echo(f"Testing ACP agent: {agent_name}...")
    
    try:
        # Test the agent
        success = asyncio.run(test_acp_agent(agent_config.acp_command))
        
        if json_output:
            click.echo(json.dumps({
                "status": "success" if success else "failed",
                "agent": agent_name,
            }))
        else:
            if success:
                click.echo(f"✓ Agent test successful")
            else:
                click.echo(f"✗ Agent test failed", err=True)
                raise click.exceptions.Exit(EXIT_ERROR)
                
    except Exception as e:
        logger.exception(f"Agent test failed: {e}")
        if json_output:
            click.echo(json.dumps({
                "status": "error",
                "error": str(e),
            }))
        else:
            click.echo(f"Error testing agent: {e}", err=True)
        raise click.exceptions.Exit(EXIT_ERROR)
