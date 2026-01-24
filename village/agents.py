"""Agent mapping resolution."""

import logging
import shlex
from dataclasses import dataclass

from village.config import Config

logger = logging.getLogger(__name__)


@dataclass
class AgentArgs:
    """Resolved agent invocation arguments."""

    agent: str
    opencode_args: list[str]


def resolve_agent_args(agent: str, config: Config) -> AgentArgs:
    """
    Resolve OpenCode invocation arguments for agent.

    Pure function - no side effects.

    Priority:
    1. Config mapping ([agent.<name>])
    2. Convention fallback (default_agent, empty args)

    Args:
        agent: Agent name (e.g., "build", "test")
        config: Config object

    Returns:
        AgentArgs with resolved arguments
    """
    if agent in config.agents:
        agent_config = config.agents[agent]
        try:
            opencode_args = shlex.split(agent_config.opencode_args)
        except ValueError as e:
            logger.warning(f"Invalid opencode_args for agent '{agent}': {e}")
            opencode_args = []
        return AgentArgs(agent, opencode_args)

    # Convention fallback
    logger.debug(f"No config for agent '{agent}', using convention fallback")
    return AgentArgs(agent, [])
