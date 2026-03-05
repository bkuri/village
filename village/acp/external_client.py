"""Village ACP Client - Connect to external ACP agents.

Uses official agent-client-protocol SDK to connect to
ACP-compliant agents (Claude Code, Gemini CLI, etc.)
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from acp import spawn_agent_process, text_block
from acp.interfaces import Client

logger = logging.getLogger(__name__)


class VillageACPClient(Client):
    """Village's ACP client for connecting to external agents.
    
    Implements Client interface to handle:
    - Permission requests from agents
    - Session updates from agents
    """
    
    async def request_permission(
        self,
        options: Any,
        session_id: str,
        tool_call: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
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
        return {"outcome": {"outcome": "approved"}}
    
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
    """
    client = VillageACPClient()
    
    # Parse command
    parts = command.split()
    executable = parts[0]
    args = parts[1:] if len(parts) > 1 else []
    
    # Spawn agent process
    conn, proc = await spawn_agent_process(
        client,
        executable,
        *args,
        cwd=str(cwd) if cwd else None,
    )
    
    logger.info(f"Spawned ACP agent: {command}")
    return conn, proc


async def test_acp_agent(command: str) -> bool:
    """Test connection to ACP agent.
    
    Args:
        command: Command to spawn agent
        
    Returns:
        True if agent responds correctly
    """
    try:
        conn, proc = await spawn_acp_agent(command)
        
        # Initialize connection
        await conn.initialize(protocol_version=1)
        
        # Create test session
        session = await conn.new_session(
            cwd=".",
            mcp_servers=[],
        )
        
        # Send test prompt
        response = await conn.prompt(
            session_id=session.session_id,
            prompt=[text_block("Hello from Village!")],
        )
        
        # Cleanup
        await conn.shutdown()
        
        logger.info(f"ACP agent test successful: {command}")
        return True
    except Exception as e:
        logger.error(f"ACP agent test failed: {e}")
        return False
