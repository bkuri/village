"""Test OpenCode invocation builder."""

from village.agents import AgentArgs
from village.opencode import build_opencode_command


def test_build_opencode_command_with_args():
    """Test building OpenCode command with arguments."""
    agent_args = AgentArgs(
        agent="build",
        opencode_args=["--mode", "patch", "--safe"],
    )

    command = build_opencode_command(agent_args)

    assert command == "opencode --mode patch --safe"


def test_build_opencode_command_without_args():
    """Test building OpenCode command without arguments."""
    agent_args = AgentArgs(agent="test", opencode_args=[])

    command = build_opencode_command(agent_args)

    assert command == "opencode"


def test_build_opencode_command_single_arg():
    """Test building OpenCode command with single argument."""
    agent_args = AgentArgs(
        agent="deploy",
        opencode_args=["--verbose"],
    )

    command = build_opencode_command(agent_args)

    assert command == "opencode --verbose"


def test_build_opencode_command_multiple_args():
    """Test building OpenCode command with multiple arguments."""
    agent_args = AgentArgs(
        agent="build",
        opencode_args=["--mode", "patch", "--safe", "--verbose", "--dry-run"],
    )

    command = build_opencode_command(agent_args)

    assert command == "opencode --mode patch --safe --verbose --dry-run"
