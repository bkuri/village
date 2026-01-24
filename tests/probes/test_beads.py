"""Test beads availability detection."""

from pathlib import Path
from unittest.mock import patch

import pytest

from village.probes.beads import (
    BeadsStatus,
    beads_available,
    beads_ready_capability,
)
from village.probes.tools import SubprocessError


def test_beads_available_returns_status():
    """Test that beads_available returns BeadsStatus."""
    status = beads_available()
    assert isinstance(status, BeadsStatus)


def test_beads_available_when_command_missing():
    """Test detection when bd command is missing."""
    with patch("village.probes.beads.run_command_output") as mock_run:
        mock_run.side_effect = SubprocessError("bd not found")

        status = beads_available()

        assert status.command_available is False
        assert status.error is not None


def test_beads_available_when_command_broken():
    """Test detection when bd command is non-functional."""
    with patch("village.probes.beads.run_command_output") as mock_run:

        def side_effect(cmd):
            if cmd == ["which", "bd"]:
                return "/usr/bin/bd"
            elif cmd == ["bd", "--version"]:
                raise SubprocessError("command failed")
            raise SubprocessError("unknown command")

        mock_run.side_effect = side_effect

        status = beads_available()

        assert status.command_available is False
        assert status.command_path == "/usr/bin/bd"
        assert status.error and "not functional" in status.error


def test_beads_available_success():
    """Test successful beads detection."""
    with patch("village.probes.beads.run_command_output") as mock_run:

        def side_effect(cmd):
            if cmd == ["which", "bd"]:
                return "/usr/bin/bd"
            elif cmd == ["bd", "--version"]:
                return "bd version 0.47.1"
            raise SubprocessError("unknown command")

        mock_run.side_effect = side_effect

        with patch("village.probes.beads.find_git_root") as mock_git_root:
            mock_git_root.return_value = Path("/tmp/test_repo")

            def exists_side_effect(self):
                return str(self).endswith(".beads")

            with patch.object(Path, "exists", exists_side_effect):
                with patch.object(Path, "is_dir", return_value=True):
                    status = beads_available()

                    assert status.command_available is True
                    assert status.command_path == "/usr/bin/bd"
                    assert status.version == "bd version 0.47.1"
                    assert status.repo_initialized is True


def test_beads_available_not_in_git_repo():
    """Test when not in git repo."""
    with patch("village.probes.beads.run_command_output") as mock_run:
        mock_run.return_value = "/usr/bin/bd"

        with patch("village.probes.beads.find_git_root") as mock_git_root:
            mock_git_root.side_effect = RuntimeError("Not in git repo")

            status = beads_available()

            assert status.command_available is True
            assert status.repo_initialized is False


def test_beads_ready_capability_true():
    """Test beads_ready_capability when ready."""
    with patch("village.probes.beads.beads_available") as mock_available:
        mock_available.return_value = BeadsStatus(
            command_available=True,
            repo_initialized=True,
        )

        result = beads_ready_capability()

        assert result is True


def test_beads_ready_capability_false():
    """Test beads_ready_capability when not ready."""
    with patch("village.probes.beads.beads_available") as mock_available:
        mock_available.return_value = BeadsStatus(
            command_available=False,
            repo_initialized=False,
        )

        result = beads_ready_capability()

        assert result is False


@pytest.mark.integration
def test_beads_available_integration():
    """Test beads detection with real bd command."""
    import shutil

    if not shutil.which("bd"):
        pytest.skip("bd command not available")

    status = beads_available()
    assert isinstance(status, BeadsStatus)
    # Actual values depend on system state
