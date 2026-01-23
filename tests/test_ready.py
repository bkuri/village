"""Test readiness assessment and decision tree."""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from village.locks import Lock, write_lock
from village.ready import (
    ReadyState,
    assess_readiness,
    check_environment_ready,
    check_runtime_ready,
    check_work_available,
    collect_readiness_data,
    generate_suggested_actions,
)


def test_check_environment_ready_true(tmp_path: Path):
    """Test environment check when config exists."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.ensure_exists()

    # Create config file (ensure_exists only creates directories)
    config.config_path.touch()

    ready, error = check_environment_ready(config)

    assert ready is True
    assert error is None


def test_check_environment_ready_no_git(tmp_path: Path):
    """Test environment check when config file doesn't exist."""
    from unittest.mock import MagicMock

    # Create mock config that doesn't exist
    mock_config = MagicMock()
    mock_config.config_exists.return_value = False

    ready, error = check_environment_ready(mock_config)

    assert ready is False
    assert error == "Village runtime not initialized"


def test_check_runtime_ready_true():
    """Test runtime check when tmux session exists."""
    with patch("village.ready.session_exists") as mock_session:
        mock_session.return_value = True

        ready, error = check_runtime_ready("village")

        assert ready is True
        assert error is None


def test_check_runtime_ready_false():
    """Test runtime check when tmux session doesn't exist."""
    with patch("village.ready.session_exists") as mock_session:
        mock_session.return_value = False

        ready, error = check_runtime_ready("village")

        assert ready is False
        assert error is not None
        assert "not running" in error


def test_check_work_available_with_beads():
    """Test work check when beads returns tasks."""
    with patch("village.ready.run_command_output") as mock_beads:
        mock_beads.return_value = "bd-xxxx\nbd-yyyy\nbd-zzzz\n"

        status, count = check_work_available(True)

        assert status == "available"
        assert count == 3


def test_check_work_available_no_beads():
    """Test work check when beads not capable."""
    status, count = check_work_available(False)

    assert status == "unknown"
    assert count is None


def test_check_work_available_error():
    """Test work check when beads command fails."""
    from village.probes.tools import SubprocessError

    with patch("village.ready.run_command_output") as mock_beads:
        mock_beads.side_effect = SubprocessError("bd failed")

        status, count = check_work_available(True)

        assert status == "unknown"
        assert count is None


def test_collect_readiness_data_all_good(tmp_path: Path):
    """Test data collection when all checks pass."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.ensure_exists()
    config.config_path.touch()

    with patch("village.ready.session_exists") as mock_session:
        mock_session.return_value = True

        with patch("village.ready.beads_available") as mock_beads:
            mock_beads.return_value = type(
                "BeadsStatus",
                (),
                {
                    "command_available": True,
                    "repo_initialized": True,
                },
            )()

            with patch("village.ready.run_command_output") as mock_output:
                mock_output.return_value = "bd-xxxx\nbd-yyyy\n"

                with patch("village.ready.get_config") as mock_config:
                    mock_config.return_value = config

                    data = collect_readiness_data("village", config)

                    assert data["environment_ready"] is True
                    assert data["runtime_ready"] is True
                    assert data["work_available"] == "available"
                    assert data["ready_tasks_count"] == 2
                    assert data["beads_capable"] is True


def test_collect_readiness_data_with_orphans(tmp_path: Path):
    """Test data collection with orphans present."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.ensure_exists()
    config.config_path.touch()
    config.locks_dir.mkdir(parents=True, exist_ok=True)
    config.worktrees_dir.mkdir(parents=True, exist_ok=True)

    # Create a stale lock (no pane)
    lock1 = Lock(
        task_id="bd-a3f8",
        pane_id="%12",
        window="build-1-bd-a3f8",
        agent="build",
        claimed_at=datetime.now(timezone.utc),
    )
    write_lock(lock1)

    # Create untracked worktree
    worktree_dir = config.worktrees_dir / "bd-b4f2"
    worktree_dir.mkdir()

    with patch("village.ready.session_exists") as mock_session:
        mock_session.return_value = True

        with patch("village.ready.beads_available") as mock_beads:
            mock_beads.return_value = type(
                "BeadsStatus",
                (),
                {
                    "command_available": True,
                    "repo_initialized": True,
                },
            )()

            with patch("village.ready.run_command_output") as mock_output:
                mock_output.return_value = ""

                with patch("village.ready.get_config") as mock_config:
                    mock_config.return_value = config

                    data = collect_readiness_data("village", config)

                    assert data["orphans_count"] == 2
                    assert data["stale_locks_count"] == 1
                    assert data["untracked_worktrees_count"] == 1

                lock1.path.unlink(missing_ok=True)


def test_generate_suggested_actions_blocking_first():
    """Test that blocking actions come first."""
    actions = generate_suggested_actions(
        environment_ready=False,
        runtime_ready=False,
        environment_error="Runtime not initialized",
        runtime_error="Runtime not initialized",
        work_available="available",
        ready_count=3,
        orphans_data={"orphans_count": 2, "stale_locks_count": 2, "untracked_worktrees_count": 0},
        active_workers=0,
    )

    assert len(actions) == 1
    assert actions[0].action == "village up"
    assert actions[0].blocking is True


def test_generate_suggested_actions_cleanup_second():
    """Test that cleanup action comes after blocking issues resolved."""
    actions = generate_suggested_actions(
        environment_ready=True,
        runtime_ready=True,
        environment_error=None,
        runtime_error=None,
        work_available="available",
        ready_count=3,
        orphans_data={"orphans_count": 2, "stale_locks_count": 2, "untracked_worktrees_count": 0},
        active_workers=0,
    )

    assert len(actions) == 2
    assert actions[0].action == "village cleanup"
    assert actions[0].blocking is True
    assert actions[1].action == "village queue --n 3"
    assert actions[1].blocking is False


def test_generate_suggested_actions_priority_order():
    """Test that actions are in correct priority order."""
    actions = generate_suggested_actions(
        environment_ready=True,
        runtime_ready=True,
        environment_error=None,
        runtime_error=None,
        work_available="available",
        ready_count=3,
        orphans_data={"orphans_count": 0, "stale_locks_count": 0, "untracked_worktrees_count": 0},
        active_workers=2,
    )

    assert len(actions) == 2
    assert actions[0].action == "village queue --n 3"
    assert actions[1].action == "village status --workers"


def test_generate_suggested_actions_no_duplicates():
    """Test that actions are not duplicated."""
    actions = generate_suggested_actions(
        environment_ready=True,
        runtime_ready=True,
        environment_error=None,
        runtime_error=None,
        work_available="not_available",
        ready_count=None,
        orphans_data={"orphans_count": 0, "stale_locks_count": 0, "untracked_worktrees_count": 0},
        active_workers=2,
    )

    assert len(actions) == 1
    assert actions[0].action == "village status --workers"


def test_assess_readiness_not_ready(tmp_path: Path):
    """Test assessment when environment not ready."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    assessment = assess_readiness("village")

    assert assessment.overall == ReadyState.NOT_READY
    assert assessment.environment_ready is False
    assert len(assessment.suggested_actions) == 1
    assert assessment.suggested_actions[0].action == "village up"


def test_assess_readiness_ready(tmp_path: Path):
    """Test assessment when all checks pass and no orphans."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.ensure_exists()
    config.config_path.touch()

    with patch("village.ready.session_exists") as mock_session:
        mock_session.return_value = True

        with patch("village.ready.beads_available") as mock_beads:
            mock_beads.return_value = type(
                "BeadsStatus",
                (),
                {
                    "command_available": True,
                    "repo_initialized": True,
                },
            )()

            with patch("village.ready.run_command_output") as mock_output:
                mock_output.return_value = "bd-xxxx\n"

                with patch("village.ready.get_config") as mock_config:
                    mock_config.return_value = config

                    assessment = assess_readiness("village")

                    assert assessment.overall == ReadyState.READY
                    assert assessment.environment_ready is True
                    assert assessment.runtime_ready is True
                    assert assessment.work_available == "available"
                    assert assessment.ready_tasks_count == 1


def test_assess_readiness_ready_with_actions(tmp_path: Path):
    """Test assessment when checks pass but orphans exist."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.ensure_exists()
    config.config_path.touch()
    config.worktrees_dir.mkdir(parents=True, exist_ok=True)

    # Create untracked worktree
    worktree_dir = config.worktrees_dir / "bd-b4f2"
    worktree_dir.mkdir()

    with patch("village.ready.session_exists") as mock_session:
        mock_session.return_value = True

        with patch("village.ready.beads_available") as mock_beads:
            mock_beads.return_value = type(
                "BeadsStatus",
                (),
                {
                    "command_available": True,
                    "repo_initialized": True,
                },
            )()

            with patch("village.ready.run_command_output") as mock_output:
                mock_output.return_value = "bd-xxxx\n"

                with patch("village.ready.get_config") as mock_config:
                    mock_config.return_value = config

                    assessment = assess_readiness("village")

                    assert assessment.overall == ReadyState.READY_WITH_ACTIONS
                    assert assessment.orphans_count == 1


def test_assess_readiness_ready_no_work(tmp_path: Path):
    """Test assessment when checks pass but no work available."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    config = get_config()
    config.ensure_exists()
    config.config_path.touch()

    with patch("village.ready.session_exists") as mock_session:
        mock_session.return_value = True

        with patch("village.ready.beads_available") as mock_beads:
            mock_beads.return_value = type(
                "BeadsStatus",
                (),
                {
                    "command_available": True,
                    "repo_initialized": True,
                },
            )()

            with patch("village.ready.run_command_output") as mock_output:
                mock_output.return_value = ""

                with patch("village.ready.get_config") as mock_config:
                    mock_config.return_value = config

                    assessment = assess_readiness("village")

                    assert assessment.overall == ReadyState.READY_NO_WORK
                    assert assessment.work_available == "not_available"
