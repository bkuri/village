"""Tests for automatic rollback in resume operations."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from village.config import Config
from village.state_machine import TaskState, TaskStateMachine
from village.resume import execute_resume
from village.scm.git import GitSCM
from village.locks import Lock


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
def rollback_test_setup(mock_config: Config) -> None:
    """Setup rollback tests."""
    mock_config.village_dir.mkdir(parents=True, exist_ok=True)
    mock_config.locks_dir.mkdir(parents=True, exist_ok=True)
    mock_config.worktrees_dir.mkdir(parents=True, exist_ok=True)

    # Initialize git repo
    import subprocess

    subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True, capture_output=True)


class TestResumeWithRollback:
    """Tests for automatic rollback on task failure."""

    def test_resume_failure_with_rollback(self, mock_config: Config, rollback_test_setup) -> None:
        """Test that task failure triggers rollback when enabled."""
        # Create worktree
        worktree_path = mock_config.worktrees_dir / "bd-a3f8"
        worktree_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=worktree_path, check=True, capture_output=True)

        # Create a file that should be rolled back
        test_file = worktree_path / "test.txt"
        test_file.write_text("This should be removed on rollback", encoding="utf-8")

        # Mock reset_workspace to track it's called
        with patch("village.scm.git.GitSCM.reset_workspace") as mock_reset:
            result = execute_resume(
                task_id="bd-a3f8",
                agent="worker",
                detached=True,
                dry_run=False,
                config=mock_config,
            )

            assert result.success is False
            assert mock_reset.called
            mock_reset.assert_called_once_with(worktree_path)

    def test_resume_failure_without_rollback(
        self, mock_config: Config, rollback_test_setup
    ) -> None:
        """Test that rollback is skipped when config disables it."""
        # Mock config with rollback disabled
        mock_config_no_rollback = Config(
            git_root=mock_config.git_root,
            village_dir=mock_config.village_dir,
            worktrees_dir=mock_config.worktrees_dir,
            tmux_session=mock_config.tmux_session,
            scm_kind=mock_config.scm_kind,
            default_agent=mock_config.default_agent,
            max_workers=mock_config.max_workers,
            queue_ttl_minutes=mock_config.queue_ttl_minutes,
        )
        mock_config_no_rollback.safety.rollback_on_failure = False

        # Create worktree
        worktree_path = mock_config.worktrees_dir / "bd-a3f8"
        worktree_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=worktree_path, check=True, capture_output=True)

        # Create a file
        test_file = worktree_path / "test.txt"
        test_file.write_text("This should NOT be removed", encoding="utf-8")

        # Mock reset_workspace to ensure it's NOT called
        with patch("village.scm.git.GitSCM.reset_workspace") as mock_reset:
            result = execute_resume(
                task_id="bd-a3f8",
                agent="worker",
                detached=True,
                dry_run=False,
                config=mock_config_no_rollback,
            )

            assert result.success is False
            assert not mock_reset.called

    def test_resume_rollback_fails_gracefully(
        self, mock_config: Config, rollback_test_setup
    ) -> None:
        """Test that rollback errors don't cause cascading failures."""
        # Create worktree
        worktree_path = mock_config.worktrees_dir / "bd-a3f8"
        worktree_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=worktree_path, check=True, capture_output=True)

        # Mock reset_workspace to raise an error
        from village.probes.tools import SubprocessError

        with patch("village.scm.git.GitSCM.reset_workspace") as mock_reset:
            mock_reset.side_effect = RuntimeError("Failed to reset")

            result = execute_resume(
                task_id="bd-a3f8",
                agent="worker",
                detached=True,
                dry_run=False,
                config=mock_config,
            )

            # Task should still be marked as FAILED even if rollback fails
            assert result.success is False
            assert result.error is not None

    def test_resume_success_no_rollback(self, mock_config: Config, rollback_test_setup) -> None:
        """Test that successful task execution doesn't trigger rollback."""
        # Create worktree
        worktree_path = mock_config.worktrees_dir / "bd-a3f8"
        worktree_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=worktree_path, check=True, capture_output=True)

        # Mock execute_opencode to return success
        with patch("village.resume.execute_opencode") as mock_execute:
            mock_execute.return_value = MagicMock(
                success=True,
                pane_id="%12",
                window_name="worker-1-bd-a3f8",
            )
            with patch("village.scm.git.GitSCM.reset_workspace") as mock_reset:
                result = execute_resume(
                    task_id="bd-a3f8",
                    agent="worker",
                    detached=True,
                    dry_run=False,
                    config=mock_config,
                )

                assert result.success is True
                assert not mock_reset.called


class TestRollbackEventLogging:
    """Tests for rollback event logging."""

    def test_rollback_event_logged(self, mock_config: Config, rollback_test_setup) -> None:
        """Test that rollback attempts are logged to events.log."""
        # Create worktree
        worktree_path = mock_config.worktrees_dir / "bd-a3f8"
        worktree_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=worktree_path, check=True, capture_output=True)

        # Mock execute_opencode to raise error
        with patch("village.resume.execute_opencode") as mock_execute:
            mock_execute.side_effect = Exception("Task failed")

            with patch("village.scm.git.GitSCM.reset_workspace"):
                execute_resume(
                    task_id="bd-a3f8",
                    agent="worker",
                    detached=True,
                    dry_run=False,
                    config=mock_config,
                )

        # Check events.log for rollback entry
        events_log_path = mock_config.village_dir / "events.log"
        assert events_log_path.exists()

        events_content = events_log_path.read_text(encoding="utf-8")
        events = [json.loads(line) for line in events_content.strip().split("\n") if line.strip()]

        rollback_events = [e for e in events if e.get("cmd") == "rollback"]
        assert len(rollback_events) > 0
        assert rollback_events[0]["task_id"] == "bd-a3f8"


class TestStateMachineIntegration:
    """Tests for state machine integration with resume."""

    def test_resume_failure_marks_task_as_failed(
        self, mock_config: Config, rollback_test_setup
    ) -> None:
        """Test that failed task transitions to FAILED state."""
        # Create worktree
        worktree_path = mock_config.worktrees_dir / "bd-a3f8"
        worktree_path.mkdir(parents=True, exist_ok=True)

        # Mock execute_opencode to raise error
        with patch("village.resume.execute_opencode") as mock_execute:
            mock_execute.side_effect = Exception("Task failed")
            with patch("village.scm.git.GitSCM.reset_workspace"):
                execute_resume(
                    task_id="bd-a3f8",
                    agent="worker",
                    detached=True,
                    dry_run=False,
                    config=mock_config,
                )

        # Check state machine
        state_machine = TaskStateMachine(mock_config)
        final_state = state_machine.get_state("bd-a3f8")

        assert final_state == TaskState.FAILED
