"""Test ready CLI command."""

import json
import os
import subprocess
from pathlib import Path


def test_ready_command_text_output(tmp_path: Path, monkeypatch):
    """Test ready command with text output."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.ensure_exists()

    from click.testing import CliRunner

    from village.cli import village

    runner = CliRunner()

    result = runner.invoke(village, ["ready"])

    assert result.exit_code == 0
    output = result.output
    assert "OVERALL STATUS:" in output
    assert "Environment Check:" in output
    assert "Runtime Check:" in output
    assert "Work Available:" in output
    assert "Orphans:" in output
    assert "SUGGESTED ACTIONS:" in output


def test_ready_command_json_output(tmp_path: Path, monkeypatch):
    """Test ready command with JSON output."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.ensure_exists()

    from click.testing import CliRunner

    from village.cli import village

    runner = CliRunner()

    result = runner.invoke(village, ["ready", "--json"])

    assert result.exit_code == 0
    output = result.output

    data = json.loads(output)
    assert data["command"] == "ready"
    assert data["version"] == 1
    assert "assessment" in data
    assert "overall" in data["assessment"]
    assert "environment_ready" in data["assessment"]
    assert "runtime_ready" in data["assessment"]
    assert "work_available" in data["assessment"]

    # No suggested actions in JSON
    assert "suggested_actions" not in data["assessment"]


def test_ready_command_not_ready(tmp_path: Path):
    """Test ready command when environment not ready."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from click.testing import CliRunner

    from village.cli import village

    runner = CliRunner()

    result = runner.invoke(village, ["ready"])

    assert result.exit_code == 0
    output = result.output
    assert "OVERALL STATUS: NOT READY" in output
    assert "Environment Check:   ✗ Village runtime not initialized" in output
    assert "village up" in output


def test_ready_command_with_orphans(tmp_path: Path):
    """Test ready command when orphans exist."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config
    from village.locks import Lock, write_lock

    config = get_config()
    config.ensure_exists()
    config.config_path.touch()
    config.locks_dir.mkdir(parents=True, exist_ok=True)

    # Create stale lock
    lock1 = Lock(
        task_id="bd-a3f8",
        pane_id="%12",
        window="build-1-bd-a3f8",
        agent="build",
        claimed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    write_lock(lock1)

    from unittest.mock import patch

    from click.testing import CliRunner

    from village.cli import village

    runner = CliRunner()

    with patch("village.ready.session_exists") as mock_session:
        mock_session.return_value = True

        result = runner.invoke(village, ["ready"])

        assert result.exit_code == 0
        output = result.output
        assert "Orphans:" in output
        assert "stale locks" in output.lower()
        assert "village cleanup" in output

    lock1.path.unlink(missing_ok=True)
