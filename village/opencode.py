"""OpenCode invocation builder (compatibility shim — use agent_command instead)."""

from village.agent_command import build_agent_command
from village.agents import AgentArgs


def build_opencode_command(agent_args: AgentArgs) -> str:
    """Build OpenCode command string (backward compat — use build_agent_command)."""
    return build_agent_command(agent_args)
