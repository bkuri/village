"""Tests for contract generation."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from village.config import Config
from village.contracts import (
    CONTRACT_VERSION,
    ResumeContract,
    contract_to_dict,
    format_contract_as_html,
    format_contract_for_stdin,
    generate_contract,
)


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Create a mock config."""
    return Config(
        git_root=tmp_path / "repo",
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )


class TestResumeContract:
    """Tests for ResumeContract dataclass."""

    def test_contract_creation(self) -> None:
        """Test ResumeContract creation."""
        contract = ResumeContract(
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            git_root=Path("/tmp/repo"),
            window_name="build-1-bd-a3f8",
            claimed_at=datetime.now(),
            village_dir=Path("/tmp/.village"),
        )

        assert contract.task_id == "bd-a3f8"
        assert contract.agent == "build"
        assert contract.worktree_path == Path("/tmp/.worktrees/bd-a3f8")
        assert contract.version == CONTRACT_VERSION

    def test_contract_default_village_dir(self, mock_config: Config) -> None:
        """Test that village_dir defaults from config."""
        with patch("village.contracts.get_config", return_value=mock_config):
            contract = ResumeContract(
                task_id="bd-a3f8",
                agent="build",
                worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
                git_root=Path("/tmp/repo"),
                window_name="build-1-bd-a3f8",
                claimed_at=datetime.now(),
                village_dir=None,
            )

            assert contract.village_dir == mock_config.village_dir


class TestGenerateContract:
    """Tests for generate_contract."""

    def test_generates_contract_successfully(
        self,
        mock_config: Config,
    ) -> None:
        """Test successful contract generation."""
        task_id = "bd-a3f8"
        agent = "build"
        worktree_path = Path("/tmp/.worktrees/bd-a3f8")
        window_name = "build-1-bd-a3f8"

        with patch("village.contracts.get_config", return_value=mock_config):
            contract = generate_contract(task_id, agent, worktree_path, window_name, mock_config)

            assert contract.task_id == task_id
            assert contract.agent == agent
            assert contract.worktree_path == worktree_path
            assert contract.window_name == window_name
            assert contract.git_root == mock_config.git_root
            assert contract.village_dir == mock_config.village_dir

    def test_generates_contract_with_defaults(
        self,
        mock_config: Config,
    ) -> None:
        """Test contract generation with default config."""
        task_id = "bd-a3f8"
        agent = "build"
        worktree_path = Path("/tmp/.worktrees/bd-a3f8")
        window_name = "build-1-bd-a3f8"

        with patch("village.contracts.get_config", return_value=mock_config):
            contract = generate_contract(task_id, agent, worktree_path, window_name)

            assert contract.task_id == task_id
            assert contract.agent == agent
            assert contract.git_root == mock_config.git_root


class TestFormatContractForStdin:
    """Tests for format_contract_for_stdin."""

    def test_formats_as_json_string(self) -> None:
        """Test that contract formats as JSON string."""
        contract = ResumeContract(
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            git_root=Path("/tmp/repo"),
            window_name="build-1-bd-a3f8",
            claimed_at=datetime.now(),
            village_dir=Path("/tmp/.village"),
        )

        result = format_contract_for_stdin(contract)

        # Parse as JSON to verify it's valid
        parsed = json.loads(result)

        assert parsed["task_id"] == "bd-a3f8"
        assert parsed["agent"] == "build"
        assert parsed["window_name"] == "build-1-bd-a3f8"

    def test_includes_all_fields(self) -> None:
        """Test that all fields are included in JSON."""
        contract = ResumeContract(
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            git_root=Path("/tmp/repo"),
            window_name="build-1-bd-a3f8",
            claimed_at=datetime.now(),
            village_dir=Path("/tmp/.village"),
        )

        result = format_contract_for_stdin(contract)
        parsed = json.loads(result)

        expected_keys = [
            "version",
            "task_id",
            "agent",
            "worktree_path",
            "git_root",
            "window_name",
            "claimed_at",
            "village_dir",
        ]

        for key in expected_keys:
            assert key in parsed

    def test_sorts_keys(self) -> None:
        """Test that JSON keys are sorted."""
        contract = ResumeContract(
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            git_root=Path("/tmp/repo"),
            window_name="build-1-bd-a3f8",
            claimed_at=datetime.now(),
            village_dir=Path("/tmp/.village"),
        )

        result = format_contract_for_stdin(contract)
        parsed = json.loads(result)
        keys = list(parsed.keys())

        # Keys should be sorted alphabetically
        assert keys == sorted(keys)


class TestFormatContractAsHtml:
    """Tests for format_contract_as_html."""

    def test_generates_valid_html(self) -> None:
        """Test that HTML is generated."""
        contract = ResumeContract(
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            git_root=Path("/tmp/repo"),
            window_name="build-1-bd-a3f8",
            claimed_at=datetime.now(),
            village_dir=Path("/tmp/.village"),
        )

        result = format_contract_as_html(contract)

        assert "<pre>" in result
        assert "</pre>" in result
        assert '<script type="application/json" id="village-meta">' in result
        assert "</script>" in result

    def test_includes_json_metadata(self) -> None:
        """Test that JSON metadata is embedded."""
        contract = ResumeContract(
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            git_root=Path("/tmp/repo"),
            window_name="build-1-bd-a3f8",
            claimed_at=datetime.now(),
            village_dir=Path("/tmp/.village"),
        )

        result = format_contract_as_html(contract)

        # Extract JSON from script tag
        start = result.find("{")
        end = result.rfind("}") + 1
        json_str = result[start:end]

        parsed = json.loads(json_str)

        assert parsed["task_id"] == "bd-a3f8"
        assert parsed["agent"] == "build"
        assert parsed["window_name"] == "build-1-bd-a3f8"

    def test_uses_indented_json(self) -> None:
        """Test that JSON is indented with 2 spaces."""
        contract = ResumeContract(
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            git_root=Path("/tmp/repo"),
            window_name="build-1-bd-a3f8",
            claimed_at=datetime.now(),
            village_dir=Path("/tmp/.village"),
        )

        result = format_contract_as_html(contract)

        # Check for indentation (2 spaces)
        assert "  " in result

    def test_sorts_keys(self) -> None:
        """Test that JSON keys are sorted in HTML."""
        contract = ResumeContract(
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            git_root=Path("/tmp/repo"),
            window_name="build-1-bd-a3f8",
            claimed_at=datetime.now(),
            village_dir=Path("/tmp/.village"),
        )

        result = format_contract_as_html(contract)

        # Extract JSON from script tag
        start = result.find("{")
        end = result.rfind("}") + 1
        json_str = result[start:end]

        parsed = json.loads(json_str)
        keys = list(parsed.keys())

        assert keys == sorted(keys)


class TestContractToDict:
    """Tests for contract_to_dict."""

    def test_converts_to_dict(self) -> None:
        """Test that contract converts to dict."""
        contract = ResumeContract(
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            git_root=Path("/tmp/repo"),
            window_name="build-1-bd-a3f8",
            claimed_at=datetime.now(),
            village_dir=Path("/tmp/.village"),
        )

        result = contract_to_dict(contract)

        assert isinstance(result, dict)
        assert result["task_id"] == "bd-a3f8"
        assert result["agent"] == "build"
        assert result["window_name"] == "build-1-bd-a3f8"

    def test_converts_paths_to_strings(self) -> None:
        """Test that Path objects are converted to strings."""
        contract = ResumeContract(
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            git_root=Path("/tmp/repo"),
            window_name="build-1-bd-a3f8",
            claimed_at=datetime.now(),
            village_dir=Path("/tmp/.village"),
        )

        result = contract_to_dict(contract)

        assert isinstance(result["worktree_path"], str)
        assert isinstance(result["git_root"], str)
        assert isinstance(result["village_dir"], str)

    def test_converts_datetime_to_isoformat(self) -> None:
        """Test that datetime is converted to ISO format."""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        contract = ResumeContract(
            task_id="bd-a3f8",
            agent="build",
            worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
            git_root=Path("/tmp/repo"),
            window_name="build-1-bd-a3f8",
            claimed_at=dt,
            village_dir=Path("/tmp/.village"),
        )

        result = contract_to_dict(contract)

        assert result["claimed_at"] == "2024-01-15T10:30:45"


class TestContractVersion:
    """Tests for CONTRACT_VERSION constant."""

    def test_version_is_1(self) -> None:
        """Test that contract version is 1."""
        assert CONTRACT_VERSION == 1
