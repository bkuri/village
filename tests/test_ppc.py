"""Test PPC contract generation."""

from pathlib import Path
from unittest.mock import patch

from village.config import AgentConfig, Config, get_config
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

    # Mock run_command_output_cwd to return success
    with patch("village.ppc.run_command_output_cwd", return_value="# System prompt for build"):
        with patch(
            "village.ppc.detect_ppc",
            return_value=type(
                "Status", (), {"available": True, "version": "v0.2.0", "prompts_dir": None}
            ),
        ):
            prompt, warning = generate_ppc_contract("build", agent_config, config)

            assert warning is None
            assert prompt == "# System prompt for build"


def test_generate_ppc_contract_not_available():
    """Test PPC contract generation when PPC not available."""
    agent_config = AgentConfig(
        ppc_mode="build",
        ppc_traits=["conservative"],
    )

    config = get_config()

    with patch(
        "village.ppc.detect_ppc",
        return_value=type("Status", (), {"available": False, "version": None, "prompts_dir": None}),
    ):
        prompt, warning = generate_ppc_contract("build", agent_config, config)

        assert prompt is None
        assert warning == "ppc_not_available"


def test_generate_ppc_contract_execution_error(tmp_path: Path):
    """Test PPC contract generation when execution fails."""
    agent_config = AgentConfig(ppc_mode="build")
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    # Mock run_command_output_cwd to raise error
    with patch("village.ppc.run_command_output_cwd", side_effect=SubprocessError("Command failed")):
        with patch(
            "village.ppc.detect_ppc",
            return_value=type(
                "Status", (), {"available": True, "version": "v0.2.0", "prompts_dir": None}
            ),
        ):
            prompt, warning = generate_ppc_contract("build", agent_config, config)

            assert prompt is None
            assert "ppc_execution_failed" in warning


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
        with patch(
            "village.ppc.detect_ppc",
            return_value=type(
                "Status", (), {"available": True, "version": "v0.2.0", "prompts_dir": None}
            ),
        ):
            prompt, warning = generate_ppc_contract("test", agent_config, config)

            assert warning is None
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
        with patch(
            "village.ppc.detect_ppc",
            return_value=type(
                "Status", (), {"available": True, "version": "v0.2.0", "prompts_dir": None}
            ),
        ):
            prompt, warning = generate_ppc_contract("build", agent_config, config)

            assert warning is None
            assert prompt == "# Prompt for build"
