"""Test PPC contract generation."""

from pathlib import Path
from unittest.mock import patch

import click
import pytest

from village.config import AgentConfig, Config
from village.ppc import generate_ppc_contract
from village.probes.tools import SubprocessError


def test_generate_ppc_contract_success(tmp_path: Path):
    """Test successful PPC contract generation."""
    agent_config = AgentConfig(
        ppc_mode="build",
        ppc_traits=["conservative", "terse"],
        ppc_format="markdown",
    )

    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    with patch("village.ppc.run_command_output_cwd", return_value="# System prompt for build"):
        prompt = generate_ppc_contract("build", agent_config, config)

        assert prompt == "# System prompt for build"


def test_generate_ppc_contract_execution_error(tmp_path: Path):
    """Test PPC contract generation when execution fails raises ClickException."""
    agent_config = AgentConfig(ppc_mode="build")
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    with patch("village.ppc.run_command_output_cwd", side_effect=SubprocessError("Command failed")):
        with pytest.raises(click.ClickException, match="PPC is required but failed"):
            generate_ppc_contract("build", agent_config, config)


def test_generate_ppc_contract_default_values(tmp_path: Path):
    """Test PPC contract generation with default mode."""
    agent_config = AgentConfig(
        ppc_traits=["terse"],
        ppc_format="code",
    )

    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    with patch("village.ppc.run_command_output_cwd", return_value="Default prompt"):
        prompt = generate_ppc_contract("test", agent_config, config)

        assert prompt == "Default prompt"


def test_generate_ppc_contract_no_traits(tmp_path: Path):
    """Test PPC contract generation without traits."""
    agent_config = AgentConfig(ppc_mode="build", ppc_format="markdown")
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    with patch("village.ppc.run_command_output_cwd", return_value="# Prompt for build"):
        prompt = generate_ppc_contract("build", agent_config, config)

        assert prompt == "# Prompt for build"


def test_generate_ppc_contract_with_vars(tmp_path: Path):
    """Test PPC contract generation with variables passes --var flags and --policies."""
    agent_config = AgentConfig(ppc_mode="build", ppc_format="markdown")
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    spec_vars = {
        "spec_name": "001-feature.md",
        "worktree_path": "/worktrees/bd-a3f8",
        "git_root": str(tmp_path),
        "window_name": "build-1",
        "spec_content": "# Feature Spec",
    }

    with patch("village.ppc.run_command_output_cwd", return_value="# PPC output") as mock_run:
        prompt = generate_ppc_contract("build", agent_config, config, vars=spec_vars)

        assert prompt == "# PPC output"
        cmd = mock_run.call_args[0][0]
        assert "--var" in cmd
        assert "spec_name=001-feature.md" in cmd
        assert "worktree_path=/worktrees/bd-a3f8" in cmd
        assert "--policies" in cmd
        assert "spec_context" in cmd


def test_generate_ppc_contract_without_vars(tmp_path: Path):
    """Test PPC contract generation without variables does not add --var or --policies."""
    agent_config = AgentConfig(ppc_mode="build", ppc_format="markdown")
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    with patch("village.ppc.run_command_output_cwd", return_value="# PPC output") as mock_run:
        prompt = generate_ppc_contract("build", agent_config, config)

        assert prompt == "# PPC output"
        cmd = mock_run.call_args[0][0]
        assert "--var" not in cmd
        assert "--policies" not in cmd
