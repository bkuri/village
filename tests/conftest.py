"""Test fixtures and utilities."""

from pathlib import Path
from typing import Generator
from unittest.mock import patch

import click.testing
import pytest

from village.probes.tools import SubprocessError


@pytest.fixture
def mock_git_root(tmp_path: Path):
    """Mock git root path."""
    with patch("village.probes.repo.run_command_output") as mock_run:
        mock_run.return_value = str(tmp_path)
        yield tmp_path


@pytest.fixture
def mock_tmux_output(monkeypatch):
    """Mock tmux command output."""

    def _mock(output: str):
        def _run_command_output(cmd):
            if "tmux" in cmd:
                return output
            raise SubprocessError("Unexpected command")

        monkeypatch.setattr(
            "village.probes.tmux.run_command_output",
            _run_command_output,
        )

    return _mock


@pytest.fixture
def runner() -> click.testing.CliRunner:
    """Click CliRunner for testing CLI commands."""
    return click.testing.CliRunner()


@pytest.fixture
def mock_subproc() -> Generator[tuple[type, type], None, None]:
    """
    Mock subprocess wrapper at single point.

    Mocks:
    - village.probes.tools.run_command
    - village.probes.tools.run_command_output

    Yields:
        Tuple of (mock_run, mock_output)
    """
    with patch("village.probes.tools.run_command") as mock_run:
        with patch("village.probes.tools.run_command_output") as mock_output:
            yield mock_run, mock_output
