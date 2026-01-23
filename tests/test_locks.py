"""Test lock parsing and evaluation."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from village.config import Config
from village.locks import Lock, evaluate_locks, is_active, parse_lock


def test_parse_lock_valid():
    """Test parsing valid lock file."""
    with patch("village.config.get_config") as mock_config:
        mock_config.return_value = Config(
            git_root=Path("/tmp/test"),
            village_dir=Path("/tmp/test/.village"),
            worktrees_dir=Path("/tmp/test/.worktrees"),
        )

    content = (
        "id=bd-a3f8\n"
        "pane=%12\n"
        "window=build-1-bd-a3f8\n"
        "agent=build\n"
        "claimed_at=2026-01-22T10:41:12\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".lock", delete=False) as f:
        f.write(content)
        f.flush()

        lock = parse_lock(Path(f.name))

        assert lock is not None
        assert lock.task_id == "bd-a3f8"
        assert lock.pane_id == "%12"
        assert lock.window == "build-1-bd-a3f8"
        assert lock.agent == "build"
        assert isinstance(lock.claimed_at, datetime)


def test_parse_lock_invalid():
    """Test parsing invalid lock file."""
    with patch("village.config.get_config") as mock_config:
        mock_config.return_value = Config(
            git_root=Path("/tmp/test"),
            village_dir=Path("/tmp/test/.village"),
            worktrees_dir=Path("/tmp/test/.worktrees"),
        )

    content = "invalid\ncorrupted\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".lock", delete=False) as f:
        f.write(content)
        f.flush()

        lock = parse_lock(Path(f.name))

        assert lock is None


def test_parse_lock_missing():
    """Test parsing missing lock file."""
    with patch("village.config.get_config") as mock_config:
        mock_config.return_value = Config(
            git_root=Path("/tmp/test"),
            village_dir=Path("/tmp/test/.village"),
            worktrees_dir=Path("/tmp/test/.worktrees"),
        )

    lock = parse_lock(Path("/tmp/does-not-exist.lock"))
    assert lock is None


def test_parse_lock_missing_datetime():
    """Test parsing lock without datetime."""
    with patch("village.config.get_config") as mock_config:
        mock_config.return_value = Config(
            git_root=Path("/tmp/test"),
            village_dir=Path("/tmp/test/.village"),
            worktrees_dir=Path("/tmp/test/.worktrees"),
        )

    content = "id=bd-a3f8\npane=%12\nwindow=build-1-bd-a3f8\nagent=build\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".lock", delete=False) as f:
        f.write(content)
        f.flush()

        lock = parse_lock(Path(f.name))

        assert lock is None


def test_is_active_with_existing_pane():
    """Test is_active returns True when pane exists."""
    with (
        patch("village.config.get_config") as mock_config,
        patch("village.locks.pane_exists") as mock_exists,
    ):
        mock_config.return_value = Config(
            git_root=Path("/tmp/test"),
            village_dir=Path("/tmp/test/.village"),
            worktrees_dir=Path("/tmp/test/.worktrees"),
        )
        mock_exists.return_value = True

        lock = Lock(
            task_id="bd-a3f8",
            pane_id="%12",
            window="build-1-bd-a3f8",
            agent="build",
            claimed_at=datetime.now(timezone.utc),
        )

        assert is_active(lock, "village") is True


def test_is_active_with_missing_pane():
    """Test is_active returns False when pane doesn't exist."""
    with (
        patch("village.config.get_config") as mock_config,
        patch("village.locks.pane_exists") as mock_exists,
    ):
        mock_config.return_value = Config(
            git_root=Path("/tmp/test"),
            village_dir=Path("/tmp/test/.village"),
            worktrees_dir=Path("/tmp/test/.worktrees"),
        )
        mock_exists.return_value = False

        lock = Lock(
            task_id="bd-a3f8",
            pane_id="%99",
            window="build-1-bd-a3f8",
            agent="build",
            claimed_at=datetime.now(timezone.utc),
        )

        assert is_active(lock, "village") is False


def test_evaluate_locks():
    """Test batch lock evaluation."""
    with (
        patch("village.config.get_config") as mock_config,
        patch("village.locks.panes") as mock_panes,
    ):
        mock_config.return_value = Config(
            git_root=Path("/tmp/test"),
            village_dir=Path("/tmp/test/.village"),
            worktrees_dir=Path("/tmp/test/.worktrees"),
        )
        mock_panes.return_value = {"%12"}

        locks = [
            Lock(
                task_id="bd-a3f8",
                pane_id="%12",
                window="build-1-bd-a3f8",
                agent="build",
                claimed_at=datetime.now(timezone.utc),
            ),
            Lock(
                task_id="bd-1234",
                pane_id="%99",
                window="test-1-bd-1234",
                agent="test",
                claimed_at=datetime.now(timezone.utc),
            ),
        ]

        status_map = evaluate_locks(locks, "village")

        assert status_map["bd-a3f8"] is True
        assert status_map["bd-1234"] is False
