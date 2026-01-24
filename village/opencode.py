"""OpenCode invocation builder."""

from village.agents import AgentArgs


def build_opencode_command(agent_args: AgentArgs) -> str:
    """
    Build OpenCode command string.

    Pure function - no side effects.

    Args:
        agent_args: Resolved agent arguments

    Returns:
        Command string (e.g., "opencode --mode patch --safe")
    """
    parts = ["opencode"]
    if agent_args.opencode_args:
        parts = parts + agent_args.opencode_args
    return " ".join(parts)
