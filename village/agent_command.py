"""Agent command builder — dispatches on agent type."""

from village.agents import AgentArgs


def build_agent_command(agent_args: AgentArgs) -> str:
    """Build command string for the agent's backend type."""
    if agent_args.agent_type == "opencode":
        return _build_opencode_command(agent_args)
    elif agent_args.agent_type == "pi":
        return _build_pi_command(agent_args)
    else:
        return _build_opencode_command(agent_args)


def _build_opencode_command(agent_args: AgentArgs) -> str:
    parts = ["opencode"]
    if agent_args.command_args:
        parts = parts + agent_args.command_args
    return " ".join(parts)


def _build_pi_command(agent_args: AgentArgs) -> str:
    parts = ["pi", "--no-session"]
    if agent_args.command_args:
        parts = parts + agent_args.command_args
    return " ".join(parts)
