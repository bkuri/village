"""Village ACP Client - Connect to external ACP agents.

Uses official agent-client-protocol SDK to connect to
ACP-compliant agents (Claude Code, Gemini CLI, etc.)
"""

import logging
from pathlib import Path
from typing import Any

from acp import spawn_agent_process, text_block
from acp.interfaces import Agent, Client
from acp.schema import (
    AllowedOutcome,
    CreateTerminalResponse,
    KillTerminalCommandResponse,
    ReadTextFileResponse,
    ReleaseTerminalResponse,
    RequestPermissionResponse,
    TerminalOutputResponse,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
)

logger = logging.getLogger(__name__)


class VillageACPClient(Client):
    """Village's ACP client for connecting to external agents.

    Implements Client interface to handle:
    - Permission requests from agents
    - Session updates from agents
    - File system operations
    - Terminal operations
    """

    async def request_permission(
        self,
        options: Any,
        session_id: str,
        tool_call: Any,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        """Handle permission request from agent.

        Args:
            options: Permission options
            session_id: Session ID
            tool_call: Tool call requesting permission
            **kwargs: Additional parameters

        Returns:
            Permission response
        """
        # For now, auto-approve (can be configured later)
        logger.info(f"Auto-approving permission for {tool_call}")
        return RequestPermissionResponse(
            outcome=AllowedOutcome(
                option_id="default",
                outcome="selected",
            ),
        )

    async def session_update(
        self,
        session_id: str,
        update: Any,
        **kwargs: Any,
    ) -> None:
        """Handle session update from agent.

        Args:
            session_id: Session ID
            update: Session update notification
            **kwargs: Additional parameters
        """
        logger.debug(f"Session {session_id} update: {update}")

    async def write_text_file(
        self,
        content: str,
        path: str,
        session_id: str,
        **kwargs: Any,
    ) -> WriteTextFileResponse | None:
        # Village doesn't allow agents to write files directly
        logger.warning(f"Agent requested to write file {path} - denied")
        raise PermissionError("File writes not allowed from external agents")

    async def read_text_file(
        self,
        path: str,
        session_id: str,
        limit: int | None = None,
        line: int | None = None,
        **kwargs: Any,
    ) -> ReadTextFileResponse:
        # Village doesn't allow agents to read files directly
        logger.warning(f"Agent requested to read file {path} - denied")
        raise PermissionError("File reads not allowed from external agents")

    async def create_terminal(
        self,
        command: str,
        session_id: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: list[Any] | None = None,
        output_byte_limit: int | None = None,
        **kwargs: Any,
    ) -> CreateTerminalResponse:
        # Village doesn't allow agents to create terminals directly
        logger.warning("Agent requested to create terminal - denied")
        raise PermissionError("Terminal creation not allowed from external agents")

    async def terminal_output(
        self,
        session_id: str,
        terminal_id: str,
        **kwargs: Any,
    ) -> TerminalOutputResponse:
        """Handle terminal_output request from agent."""
        logger.warning(f"Agent requested terminal output {terminal_id} - denied")
        raise PermissionError("Terminal access not allowed from external agents")

    async def release_terminal(
        self,
        session_id: str,
        terminal_id: str,
        **kwargs: Any,
    ) -> ReleaseTerminalResponse:
        """Handle release_terminal request from agent."""
        logger.warning(f"Agent requested to release terminal {terminal_id} - denied")
        raise PermissionError("Terminal operations not allowed from external agents")

    async def wait_for_terminal_exit(
        self,
        session_id: str,
        terminal_id: str,
        **kwargs: Any,
    ) -> WaitForTerminalExitResponse:
        """Handle wait_for_terminal_exit request from agent."""
        logger.warning(f"Agent requested to wait for terminal {terminal_id} - denied")
        raise PermissionError("Terminal operations not allowed from external agents")

    async def kill_terminal(
        self,
        session_id: str,
        terminal_id: str,
        **kwargs: Any,
    ) -> KillTerminalCommandResponse:
        """Handle kill_terminal request from agent."""
        logger.warning(f"Agent requested to kill terminal {terminal_id} - denied")
        raise PermissionError("Terminal operations not allowed from external agents")

    async def ext_method(
        self,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle extension method from agent."""
        logger.warning(f"Unknown extension method from agent: {method}")
        return {}

    async def ext_notification(
        self,
        method: str,
        params: dict[str, Any],
    ) -> None:
        """Handle extension notification from agent."""
        logger.warning(f"Unknown extension notification from agent: {method}")

    def on_connect(self, conn: Agent) -> None:
        """Handle agent connection."""
        logger.info("External ACP agent connected")


async def spawn_acp_agent(
    command: str,
    cwd: Path | None = None,
) -> tuple[Any, Any]:
    """Spawn an ACP-compliant agent.

    Args:
        command: Command to spawn agent
        cwd: Working directory

    Returns:
        Tuple of (connection, process)

    Note:
        This returns immediately. The connection is managed via async context manager
        internally by spawn_agent_process.
    """
    client = VillageACPClient()

    # Parse command
    parts = command.split()
    executable = parts[0]
    args = parts[1:] if len(parts) > 1 else []

    # Spawn agent process
    # Note: spawn_agent_process returns an async context manager
    # We need to use it properly
    cm = spawn_agent_process(
        client,
        executable,
        *args,
        cwd=str(cwd) if cwd else None,
    )

    # Enter the context manager
    conn, proc = await cm.__aenter__()

    logger.info(f"Spawned ACP agent: {command}")

    # Return connection and a wrapper that will clean up on close
    # The caller is responsible for calling shutdown
    return conn, proc


async def test_acp_agent(command: str) -> bool:
    """Test connection to ACP agent.

    Args:
        command: Command to spawn agent

    Returns:
        True if agent responds correctly
    """
    try:
        client = VillageACPClient()

        # Parse command
        parts = command.split()
        executable = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        # Spawn agent process with context manager
        async with spawn_agent_process(
            client,
            executable,
            *args,
            cwd=".",
        ) as (conn, proc):
            # Initialize connection
            await conn.initialize(protocol_version=1)

            # Create test session
            session = await conn.new_session(
                cwd=".",
                mcp_servers=[],
            )

            # Send test prompt
            await conn.prompt(
                session_id=session.session_id,
                prompt=[text_block("Hello from Village!")],
            )

            # Cleanup happens automatically via context manager
            logger.info(f"ACP agent test successful: {command}")
            return True
    except Exception as e:
        logger.error(f"ACP agent test failed: {e}")
        return False
