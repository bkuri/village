"""Test status command."""

import json
import os
import subprocess
from pathlib import Path

from click.testing import CliRunner

from village.cli import village


def test_status_short(tmp_path: Path):
    """Test status --short command."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(village, ["status", "--short"])

    assert result.exit_code == 0
    # Should contain tmux and locks info
    assert "tmux:" in result.output
    assert "locks:" in result.output


def test_status_json(tmp_path: Path):
    """Test status --json command."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(village, ["status", "--json"])

    assert result.exit_code == 0

    # Parse and validate JSON structure
    data = json.loads(result.output)
    assert data["command"] == "status"
    assert data["version"] == 1
    assert "tmux" in data
    assert "config" in data
    assert "locks" in data
    assert "worktrees" in data
    assert isinstance(data["tmux"]["running"], bool)
    assert isinstance(data["locks"]["count"], int)


def test_status_full(tmp_path: Path):
    """Test status command (full)."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(village, ["status"])

    assert result.exit_code == 0
    assert "Village directory:" in result.output
    assert "TMUX session:" in result.output


def test_status_verbose(tmp_path: Path):
    """Test status with verbose logging."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(village, ["-v", "status", "--short"])

    assert result.exit_code == 0
    # Debug logs should not appear in stdout (--short output is clean)
    assert "DEBUG" not in result.output
