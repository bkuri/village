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
    command_args: list[str]
    agent_type: str = "opencode"

    @property
    def opencode_args(self) -> list[str]:
        """Backward compat alias for command_args."""
        return self.command_args


def resolve_agent_args(agent: str, config: Config) -> AgentArgs:
    """Resolve agent invocation arguments from config."""
    if agent in config.agents:
        agent_config = config.agents[agent]
        agent_type = agent_config.type

        raw_args = ""
        if agent_type == "pi":
            raw_args = agent_config.pi_args
        else:
            raw_args = agent_config.opencode_args

        try:
            command_args = shlex.split(raw_args)
        except ValueError as e:
            logger.warning(f"Invalid args for agent '{agent}': {e}")
            command_args = []
        return AgentArgs(agent, command_args, agent_type=agent_type)

    logger.debug(f"No config for agent '{agent}', using convention fallback")
    return AgentArgs(agent, [])
