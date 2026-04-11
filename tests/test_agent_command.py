"""Test agent command builder."""

from village.agent_command import build_agent_command
from village.agents import AgentArgs


def test_build_opencode_command_with_args():
    agent_args = AgentArgs(agent="build", command_args=["--mode", "patch", "--safe"], agent_type="opencode")
    assert build_agent_command(agent_args) == "opencode --mode patch --safe"


def test_build_opencode_command_without_args():
    agent_args = AgentArgs(agent="test", command_args=[], agent_type="opencode")
    assert build_agent_command(agent_args) == "opencode"


def test_build_pi_command_with_args():
    agent_args = AgentArgs(agent="build", command_args=["--thinking", "high"], agent_type="pi")
    assert build_agent_command(agent_args) == "pi --no-session --thinking high"


def test_build_pi_command_without_args():
    agent_args = AgentArgs(agent="build", command_args=[], agent_type="pi")
    assert build_agent_command(agent_args) == "pi --no-session"


def test_default_falls_back_to_opencode():
    agent_args = AgentArgs(agent="build", command_args=["--verbose"], agent_type="unknown")
    assert build_agent_command(agent_args) == "opencode --verbose"
