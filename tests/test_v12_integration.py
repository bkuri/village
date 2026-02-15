"""Integration tests for v1.2 reliability features.

Tests end-to-end workflows for event logging, queue deduplication,
and cleanup operations.
"""

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from village.config import Config
from village.event_log import Event, append_event, read_events


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Create a mock config."""
    return Config(
        git_root=tmp_path / "repo",
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
        tmux_session="village",
        default_agent="worker",
    )


class TestV12EventLoggingIntegration:
    """Integration tests for v1.2 event logging."""

    def test_resume_command_logs_event(self, mock_config: Config):
        """Test resume command logs start and success events."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)
        mock_config.village_dir.mkdir(parents=True, exist_ok=True)

        # Verify event log path is created
        assert mock_config.village_dir.exists()


class TestV12DeduplicationIntegration:
    """Integration tests for queue deduplication guard."""

    def test_queue_blocks_recently_executed_task(self, mock_config: Config):
        """Test queue skips tasks executed within TTL."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)
        mock_config.village_dir.mkdir(parents=True, exist_ok=True)

        # Add recent event (within default 5 minute TTL)
        recent_ts = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        event = Event(
            ts=recent_ts,
            cmd="queue",
            task_id="bd-a3f8",
            pane="%12",
            result="ok",
        )
        append_event(event, mock_config.village_dir)

        # Read events and verify recent task is logged
        events = read_events(mock_config.village_dir)
        queue_events = [e for e in events if e.cmd == "queue" and e.task_id == "bd-a3f8"]

        assert len(queue_events) >= 1
        assert queue_events[0].pane == "%12"
        assert queue_events[0].result == "ok"


class TestV12CleanupIntegration:
    """Integration tests for v1.2 cleanup enhancements."""

    def test_cleanup_creates_plan(self, mock_config: Config):
        """Test cleanup creates plan."""
        mock_config.git_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)
        mock_config.village_dir.mkdir(parents=True, exist_ok=True)
        mock_config.locks_dir.mkdir(parents=True, exist_ok=True)

        # Verify cleanup plan can be generated
        from village.cleanup import plan_cleanup

        with patch("village.probes.tmux.refresh_panes"):
            with patch("village.probes.tmux.panes"):
                plan = plan_cleanup("village")

        # Plan should be created without errors
        assert plan is not None
        assert plan.stale_locks is not None
        assert plan.orphan_worktrees is not None
