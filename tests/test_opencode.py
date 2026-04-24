"""Test OpenCode invocation builder."""

from village.agent_command import build_agent_command
from village.agents import AgentArgs


def test_build_opencode_command_with_args():
    """Test building OpenCode command with arguments."""
    agent_args = AgentArgs(
        agent="build",
        command_args=["--mode", "patch", "--safe"],
        agent_type="opencode",
    )

    command = build_agent_command(agent_args)

    assert command == "opencode --mode patch --safe"


def test_build_opencode_command_without_args():
    """Test building OpenCode command without arguments."""
    agent_args = AgentArgs(agent="test", command_args=[], agent_type="opencode")

    command = build_agent_command(agent_args)

    assert command == "opencode"


def test_build_opencode_command_single_arg():
    """Test building OpenCode command with single argument."""
    agent_args = AgentArgs(
        agent="deploy",
        command_args=["--verbose"],
        agent_type="opencode",
    )

    command = build_agent_command(agent_args)

    assert command == "opencode --verbose"


def test_build_opencode_command_multiple_args():
    """Test building OpenCode command with multiple arguments."""
    agent_args = AgentArgs(
        agent="build",
        command_args=["--mode", "patch", "--safe", "--verbose", "--dry-run"],
        agent_type="opencode",
    )

    command = build_agent_command(agent_args)

    assert command == "opencode --mode patch --safe --verbose --dry-run"
