"""Tests for state machine CLI commands."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from village.config import Config
from village.errors import EXIT_BLOCKED, EXIT_ERROR
from village.state_machine import TaskState, TaskStateMachine


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Create a mock config for testing."""
    return Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
        tmux_session="test",
        scm_kind="git",
        default_agent="worker",
        max_workers=2,
        queue_ttl_minutes=5,
    )


@pytest.fixture
def state_machine_cli_test_setup(mock_config: Config) -> None:
    """Setup state machine CLI tests."""
    mock_config.village_dir.mkdir(parents=True, exist_ok=True)
    mock_config.locks_dir.mkdir(parents=True, exist_ok=True)


class TestStateCommand:
    """Tests for `village state` command."""

    def test_state_command_displays_current_state(
        self, mock_config: Config, state_machine_cli_test_setup
    ) -> None:
        """Test that state command displays current state correctly."""
        # Create a lock file with a state
        lock_path = mock_config.locks_dir / "bd-a3f8.lock"
        lock_content = (
            "id=bd-a3f8\npane=%12\nwindow=build-1-bd-a3f8\nagent=build\nstate=in_progress\n"
        )
        lock_path.write_text(lock_content, encoding="utf-8")

        # Mock CLI invocation
        with patch("village.cli.get_config", return_value=mock_config):
            from village.cli import state

            result = runner.invoke(state, ["bd-a3f8"])

        assert result.exit_code == 0
        assert "Task: bd-a3f8" in result.output
        assert "Current State: in_progress" in result.output

    def test_state_command_json_output(
        self, mock_config: Config, state_machine_cli_test_setup
    ) -> None:
        """Test that state command outputs JSON correctly."""
        lock_path = mock_config.locks_dir / "bd-a3f8.lock"
        lock_content = (
            "id=bd-a3f8\n"
            "pane=%12\n"
            "window=build-1-bd-a3f8\n"
            "agent=build\n"
            "state=in_progress\n"
            'state_history=[{"ts":"2026-01-26T10:00:00","from_state":"queued","to_state":"in_progress","context":{}}]\n'
        )
        lock_path.write_text(lock_content, encoding="utf-8")

        with patch("village.cli.get_config", return_value=mock_config):
            from village.cli import state

            result = runner.invoke(state, ["bd-a3f8", "--json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["task_id"] == "bd-a3f8"
        assert output_data["current_state"] == "in_progress"
        assert len(output_data["history"]) == 1
        assert output_data["history"][0]["from_state"] == "queued"
        assert output_data["history"][0]["to_state"] == "in_progress"

    def test_state_command_no_state(
        self, mock_config: Config, state_machine_cli_test_setup
    ) -> None:
        """Test that state command handles tasks without state gracefully."""
        with patch("village.cli.get_config", return_value=mock_config):
            from village.cli import state

            result = runner.invoke(state, ["bd-a3f8"])

        assert result.exit_code == EXIT_BLOCKED.value
        assert "Task bd-a3f8 not found" in result.output

    def test_state_command_shows_history(
        self, mock_config: Config, state_machine_cli_test_setup
    ) -> None:
        """Test that state command displays transition history."""
        history_data = [
            {
                "ts": "2026-01-26T10:00:00",
                "from_state": "queued",
                "to_state": "in_progress",
                "context": {"pane_id": "%12"},
            },
            {
                "ts": "2026-01-26T10:05:00",
                "from_state": "in_progress",
                "to_state": "paused",
                "context": {"reason": "user_paused"},
            },
        ]

        lock_path = mock_config.locks_dir / "bd-a3f8.lock"
        lock_content = (
            "id=bd-a3f8\n"
            "pane=%12\n"
            "window=build-1-bd-a3f8\n"
            "agent=build\n"
            "state=paused\n"
            f"state_history={json.dumps(history_data, sort_keys=True)}\n"
        )
        lock_path.write_text(lock_content, encoding="utf-8")

        with patch("village.cli.get_config", return_value=mock_config):
            from village.cli import state

            result = runner.invoke(state, ["bd-a3f8"])

        assert result.exit_code == 0
        assert "State History:" in result.output
        assert "queued → in_progress" in result.output
        assert "in_progress → paused" in result.output
        assert "reason: user_paused" in result.output


class TestPauseCommand:
    """Tests for `village pause` command."""

    def test_pause_in_progress_task(
        self, mock_config: Config, state_machine_cli_test_setup
    ) -> None:
        """Test that pause command successfully pauses in-progress task."""
        lock_path = mock_config.locks_dir / "bd-a3f8.lock"
        lock_content = (
            "id=bd-a3f8\npane=%12\nwindow=build-1-bd-a3f8\nagent=build\nstate=in_progress\n"
        )
        lock_path.write_text(lock_content, encoding="utf-8")

        with patch("village.cli.get_config", return_value=mock_config):
            from village.cli import pause

            result = runner.invoke(pause, ["bd-a3f8"])

        assert result.exit_code == 0
        assert "Paused task bd-a3f8" in result.output

        # Verify state changed in lock file
        updated_content = lock_path.read_text(encoding="utf-8")
        assert "state=paused" in updated_content

    def test_pause_non_progress_task(
        self, mock_config: Config, state_machine_cli_test_setup
    ) -> None:
        """Test that pause command rejects pause of non-progress task."""
        lock_path = mock_config.locks_dir / "bd-a3f8.lock"
        lock_content = "id=bd-a3f8\npane=%12\nwindow=build-1-bd-a3f8\nagent=build\nstate=queued\n"
        lock_path.write_text(lock_content, encoding="utf-8")

        with patch("village.cli.get_config", return_value=mock_config):
            from village.cli import pause

            result = runner.invoke(pause, ["bd-a3f8"])

        assert result.exit_code == EXIT_BLOCKED.value
        assert "is not IN_PROGRESS" in result.output

    def test_pause_force_bypass(self, mock_config: Config, state_machine_cli_test_setup) -> None:
        """Test that --force bypasses validation."""
        lock_path = mock_config.locks_dir / "bd-a3f8.lock"
        lock_content = "id=bd-a3f8\npane=%12\nwindow=build-1-bd-a3f8\nagent=build\nstate=queued\n"
        lock_path.write_text(lock_content, encoding="utf-8")

        with patch("village.cli.get_config", return_value=mock_config):
            from village.cli import pause

            result = runner.invoke(pause, ["bd-a3f8", "--force"])

        assert result.exit_code == 0
        assert "Paused task bd-a3f8" in result.output

    def test_pause_logs_event(self, mock_config: Config, state_machine_cli_test_setup) -> None:
        """Test that pause logs transition event to events.log."""
        lock_path = mock_config.locks_dir / "bd-a3f8.lock"
        lock_content = (
            "id=bd-a3f8\npane=%12\nwindow=build-1-bd-a3f8\nagent=build\nstate=in_progress\n"
        )
        lock_path.write_text(lock_content, encoding="utf-8")

        events_log_path = mock_config.village_dir / "events.log"

        with patch("village.cli.get_config", return_value=mock_config):
            from village.cli import pause

            runner.invoke(pause, ["bd-a3f8"])

        # Verify event was logged
        assert events_log_path.exists()
        events_content = events_log_path.read_text(encoding="utf-8")
        assert "state_transition" in events_content
        assert 'to_state":"paused"' in events_content


class TestResumeTaskCommand:
    """Tests for `village resume-task` command."""

    def test_resume_paused_task(self, mock_config: Config, state_machine_cli_test_setup) -> None:
        """Test that resume-task command successfully resumes paused task."""
        lock_path = mock_config.locks_dir / "bd-a3f8.lock"
        lock_content = "id=bd-a3f8\npane=%12\nwindow=build-1-bd-a3f8\nagent=build\nstate=paused\n"
        lock_path.write_text(lock_content, encoding="utf-8")

        with patch("village.cli.get_config", return_value=mock_config):
            from village.cli import resume_task

            result = runner.invoke(resume_task, ["bd-a3f8"])

        assert result.exit_code == 0
        assert "Resumed task bd-a3f8" in result.output

        # Verify state changed in lock file
        updated_content = lock_path.read_text(encoding="utf-8")
        assert "state=in_progress" in updated_content

    def test_resume_non_paused_task(
        self, mock_config: Config, state_machine_cli_test_setup
    ) -> None:
        """Test that resume-task command rejects resume of non-paused task."""
        lock_path = mock_config.locks_dir / "bd-a3f8.lock"
        lock_content = "id=bd-a3f8\npane=%12\nwindow=build-1-bd-a3f8\nagent=build\nstate=queued\n"
        lock_path.write_text(lock_content, encoding="utf-8")

        with patch("village.cli.get_config", return_value=mock_config):
            from village.cli import resume_task

            result = runner.invoke(resume_task, ["bd-a3f8"])

        assert result.exit_code == EXIT_BLOCKED.value
        assert "is not PAUSED" in result.output

    def test_resume_force_bypass(self, mock_config: Config, state_machine_cli_test_setup) -> None:
        """Test that --force bypasses validation."""
        lock_path = mock_config.locks_dir / "bd-a3f8.lock"
        lock_content = "id=bd-a3f8\npane=%12\nwindow=build-1-bd-a3f8\nagent=build\nstate=queued\n"
        lock_path.write_text(lock_content, encoding="utf-8")

        with patch("village.cli.get_config", return_value=mock_config):
            from village.cli import resume_task

            result = runner.invoke(resume_task, ["bd-a3f8", "--force"])

        assert result.exit_code == 0
        assert "Resumed task bd-a3f8" in result.output

    def test_resume_logs_event(self, mock_config: Config, state_machine_cli_test_setup) -> None:
        """Test that resume-task logs transition event to events.log."""
        lock_path = mock_config.locks_dir / "bd-a3f8.lock"
        lock_content = "id=bd-a3f8\npane=%12\nwindow=build-1-bd-a3f8\nagent=build\nstate=paused\n"
        lock_path.write_text(lock_content, encoding="utf-8")

        events_log_path = mock_config.village_dir / "events.log"

        with patch("village.cli.get_config", return_value=mock_config):
            from village.cli import resume_task

            runner.invoke(resume_task, ["bd-a3f8"])

        # Verify event was logged
        assert events_log_path.exists()
        events_content = events_log_path.read_text(encoding="utf-8")
        assert "state_transition" in events_content
        assert 'to_state":"in_progress"' in events_content

        # Setup click runner
        from click.testing import CliRunner

        runner = CliRunner()
