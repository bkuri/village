"""Test fixtures and utilities."""

from pathlib import Path
from unittest.mock import patch

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
