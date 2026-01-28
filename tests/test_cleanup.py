"""Test cleanup operations."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from village.cleanup import execute_cleanup, find_stale_locks, plan_cleanup
from village.config import Config
from village.locks import Lock, write_lock


@pytest.fixture
def mock_config(tmp_path: Path):
    """Mock config with temp directory."""
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.locks_dir.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture(autouse=True)
def clean_mock_config(mock_config: Config):
    """Auto-use fixture to clean up after each test."""
    yield
    # Clean up any created files
    for lock_file in mock_config.locks_dir.glob("*.lock"):
        lock_file.unlink(missing_ok=True)


def test_find_stale_locks(mock_config: Config):
    """Test finding stale locks."""
    with patch("village.locks.get_config") as mock_locks_config:
        mock_locks_config.return_value = mock_config

        with patch("village.cleanup.get_config") as mock_cleanup_config:
            mock_cleanup_config.return_value = mock_config

            with patch("village.probes.tmux.refresh_panes"):
                with patch("village.probes.tmux.panes") as mock_panes:
                    mock_panes.return_value = {"%12"}

                    locks_to_create = [
                        Lock(
                            task_id="bd-active",
                            pane_id="%12",
                            window="test-window-active",
                            agent="test",
                            claimed_at=datetime.now(timezone.utc),
                        ),
                        Lock(
                            task_id="bd-stale",
                            pane_id="%99",
                            window="test-window-stale",
                            agent="test",
                            claimed_at=datetime.now(timezone.utc),
                        ),
                    ]

                    for lock in locks_to_create:
                        write_lock(lock)

                    stale = find_stale_locks("village")

                    assert len(stale) == 1
                    assert stale[0].task_id == "bd-stale"

                    for lock in locks_to_create:
                        lock.path.unlink(missing_ok=True)


def test_plan_cleanup(mock_config: Config):
    """Test cleanup plan generation."""
    with patch("village.locks.get_config") as mock_locks_config:
        mock_locks_config.return_value = mock_config

        with patch("village.cleanup.get_config") as mock_cleanup_config:
            mock_cleanup_config.return_value = mock_config

            with patch("village.probes.tmux.refresh_panes"):
                with patch("village.probes.tmux.panes") as mock_panes:
                    mock_panes.return_value = set()

                    stale_lock = Lock(
                        task_id="bd-stale",
                        pane_id="%99",
                        window="test-window",
                        agent="test",
                        claimed_at=datetime.now(timezone.utc),
                    )
                    write_lock(stale_lock)

                    plan = plan_cleanup("village")

                    assert len(plan.stale_locks) == 1
                    assert plan.stale_locks[0].task_id == "bd-stale"
                    assert len(plan.locks_to_remove) == 1
                    assert plan.locks_to_remove[0] == stale_lock

                    stale_lock.path.unlink(missing_ok=True)


def test_plan_cleanup_no_stale(mock_config: Config):
    """Test plan_cleanup with no stale locks."""
    with patch("village.locks.get_config") as mock_locks_config:
        mock_locks_config.return_value = mock_config

        with patch("village.cleanup.get_config") as mock_cleanup_config:
            mock_cleanup_config.return_value = mock_config

            with patch("village.probes.tmux.refresh_panes"):
                with patch("village.probes.tmux.panes") as mock_panes:
                    mock_panes.return_value = set()

                    plan = plan_cleanup("village")

                    assert len(plan.stale_locks) == 0
                    assert len(plan.locks_to_remove) == 0


def test_execute_cleanup_logs_events(mock_config: Config):
    """Test execute_cleanup logs cleanup events."""
    from village.event_log import read_events

    with patch("village.locks.get_config") as mock_locks_config:
        mock_locks_config.return_value = mock_config

        with patch("village.cleanup.get_config") as mock_cleanup_config:
            mock_cleanup_config.return_value = mock_config

            with patch("village.probes.tmux.refresh_panes"):
                with patch("village.probes.tmux.panes") as mock_panes:
                    mock_panes.return_value = set()

                    mock_config.git_root.mkdir(parents=True, exist_ok=True)
                    subprocess.run(["git", "init"], cwd=mock_config.git_root, check=True)
                    mock_config.village_dir.mkdir(parents=True, exist_ok=True)

                    stale_lock = Lock(
                        task_id="bd-stale",
                        pane_id="%99",
                        window="test-window-stale",
                        agent="test",
                        claimed_at=datetime.now(timezone.utc),
                    )
                    stale_lock._config = mock_config
                    write_lock(stale_lock)

                    plan = plan_cleanup("village")
                    execute_cleanup(plan, mock_config)

                    events = read_events(mock_config.village_dir)
                    cleanup_events = [e for e in events if e.cmd == "cleanup"]
                    assert len(cleanup_events) >= 1
                    assert cleanup_events[0].task_id == "bd-stale"
                    assert cleanup_events[0].pane == "%99"
                    assert cleanup_events[0].result == "ok"

                    stale_lock.path.unlink(missing_ok=True)
