"""Village ACP Agent - Exposes Village via ACP protocol.

Uses official agent-client-protocol SDK to wrap Village core
as an ACP-compliant agent that editors can connect to.
"""

import logging
from typing import Any

from acp.interfaces import Client
from acp.schema import (
    AgentCapabilities,
    AuthenticateResponse,
    CancelNotification,
    ClientCapabilities,
    ForkSessionResponse,
    Implementation,
    InitializeResponse,
    ListSessionsResponse,
    LoadSessionResponse,
    NewSessionResponse,
    PromptResponse,
    ResumeSessionResponse,
    SetSessionConfigOptionResponse,
    SetSessionModeResponse,
    SetSessionModelResponse,
)

from village.acp.bridge import ACPBridge
from village.config import Config, get_config

logger = logging.getLogger(__name__)


class VillageACPAgent:
    """Village as an ACP-compliant agent.

    Implements the Agent protocol to expose Village operations
    to ACP-compatible editors (Zed, JetBrains, etc.)

    Delegates to ACPBridge for actual Village operations.
    """

    def __init__(self, config: Config | None = None):
        """Initialize Village ACP agent.

        Args:
            config: Village config (uses default if not provided)
        """
        self.config = config or get_config()
        self.bridge = ACPBridge(self.config)

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: ClientCapabilities | None = None,
        client_info: Implementation | None = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        """Handle ACP initialize request."""
        logger.info(f"ACP initialize: version={protocol_version}, client={client_info}")

        return InitializeResponse(
            protocol_version=protocol_version,
            agent_capabilities=AgentCapabilities(),
            agent_info=Implementation(
                name="village",
                version="1.0.0",
            ),
        )

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[Any] | None = None,
        **kwargs: Any,
    ) -> NewSessionResponse:
        """Handle ACP session/new request."""
        result = await self.bridge.session_new(kwargs)

        return NewSessionResponse(
            session_id=result["sessionId"],
        )

    async def load_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[Any] | None = None,
        **kwargs: Any,
    ) -> LoadSessionResponse | None:
        """Handle ACP session/load request."""
        result = await self.bridge.session_load({"sessionId": session_id})

        return LoadSessionResponse()

    async def list_sessions(
        self,
        cursor: str | None = None,
        cwd: str | None = None,
        **kwargs: Any,
    ) -> ListSessionsResponse:
        """Handle ACP session/list request."""
        # TODO: Implement session listing
        return ListSessionsResponse(sessions=[])

    async def set_session_mode(
        self,
        mode_id: str,
        session_id: str,
        **kwargs: Any,
    ) -> SetSessionModeResponse | None:
        """Handle ACP session/set_mode request."""
        # Village doesn't support modes yet
        return None

    async def set_session_model(
        self,
        model_id: str,
        session_id: str,
        **kwargs: Any,
    ) -> SetSessionModelResponse | None:
        """Handle ACP session/set_model request."""
        # Village doesn't support model selection yet
        return None

    async def set_config_option(
        self,
        config_id: str,
        session_id: str,
        value: str,
        **kwargs: Any,
    ) -> SetSessionConfigOptionResponse | None:
        """Handle ACP session/set_config_option request."""
        # Village doesn't support config options yet
        return None

    async def authenticate(
        self,
        method_id: str,
        **kwargs: Any,
    ) -> AuthenticateResponse | None:
        """Handle ACP authenticate request."""
        # Village doesn't require authentication
        return None

    async def prompt(
        self,
        prompt: list[Any],
        session_id: str,
        **kwargs: Any,
    ) -> PromptResponse:
        """Handle ACP session/prompt request."""
        # Extract message from prompt blocks
        message = self._extract_text(prompt)

        logger.info(f"ACP prompt for session {session_id}: {message[:100]}")

        # Execute via bridge
        agent = kwargs.get("agent", self.config.default_agent)
        result, _notifications = await self.bridge.session_prompt(
            {
                "sessionId": session_id,
                "message": message,
                "agent": agent,
            }
        )

        # Return response
        # Note: PromptResponse doesn't have content, just metadata
        # Content is sent via notifications
        return PromptResponse(
            stop_reason="end_turn",
        )

    async def fork_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[Any] | None = None,
        **kwargs: Any,
    ) -> ForkSessionResponse:
        """Handle ACP session/fork request."""
        # Village doesn't support session forking yet
        raise NotImplementedError("Session forking not supported")

    async def resume_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[Any] | None = None,
        **kwargs: Any,
    ) -> ResumeSessionResponse:
        """Handle ACP session/resume request."""
        # Load existing session
        result = await self.bridge.session_load({"sessionId": session_id})

        return ResumeSessionResponse()

    async def cancel(
        self,
        session_id: str,
        **kwargs: Any,
    ) -> None:
        """Handle ACP cancel request."""
        await self.bridge.session_cancel({"sessionId": session_id})

    async def ext_method(
        self,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle ACP extension method."""
        logger.warning(f"Unknown extension method: {method}")
        return {}

    async def ext_notification(
        self,
        method: str,
        params: dict[str, Any],
    ) -> None:
        """Handle ACP extension notification."""
        logger.warning(f"Unknown extension notification: {method}")

    def on_connect(self, conn: Client) -> None:
        """Handle ACP client connection."""
        logger.info("ACP client connected")

    def _extract_text(self, prompt: list[Any]) -> str:
        """Extract text from prompt blocks.

        Args:
            prompt: List of content blocks

        Returns:
            Concatenated text
        """
        texts = []
        for block in prompt:
            if hasattr(block, "text"):
                texts.append(block.text)
            elif isinstance(block, dict) and "text" in block:
                texts.append(block["text"])
        return " ".join(texts)


async def run_village_agent(config: Config | None = None) -> None:
    """Run Village as an ACP agent.

    Entry point for: village acp server start

    Args:
        config: Village config (uses default if not provided)
    """
    from acp import run_agent

    agent = VillageACPAgent(config)
    await run_agent(agent)
