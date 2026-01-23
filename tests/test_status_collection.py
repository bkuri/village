"""Test status data collection functions."""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from village.status import (
    FullStatus,
    Orphan,
    StatusSummary,
    Worker,
    collect_full_status,
    collect_orphans,
    collect_summary,
    collect_workers,
)


def test_collect_workers_no_locks(tmp_path: Path):
    """Test worker collection with no locks."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    workers = collect_workers("village")
    assert workers == []


def test_collect_workers_with_locks(tmp_path: Path):
    """Test worker collection with active locks."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config
    from village.locks import Lock, write_lock

    with patch("village.locks.get_config") as mock_locks_config:
        mock_locks_config.return_value = get_config()

        with patch("village.status.get_config") as mock_status_config:
            mock_status_config.return_value = get_config()

            with patch("village.locks.panes") as mock_panes:
                mock_panes.return_value = {"%12", "%13"}

                config = get_config()
                config.locks_dir.mkdir(parents=True, exist_ok=True)

                lock1 = Lock(
                    task_id="bd-a3f8",
                    pane_id="%12",
                    window="build-1-bd-a3f8",
                    agent="build",
                    claimed_at=datetime.now(timezone.utc),
                )
                write_lock(lock1)

                lock2 = Lock(
                    task_id="bd-b4f2",
                    pane_id="%13",
                    window="test-2-bd-b4f2",
                    agent="test",
                    claimed_at=datetime.now(timezone.utc),
                )
                write_lock(lock2)

                workers = collect_workers("village")

                assert len(workers) == 2
                task_ids = {w.task_id for w in workers}
                assert "bd-a3f8" in task_ids
                assert "bd-b4f2" in task_ids

                for worker in workers:
                    assert worker.status == "ACTIVE"

                lock1.path.unlink(missing_ok=True)
                lock2.path.unlink(missing_ok=True)


def test_collect_orphans_no_orphans(tmp_path: Path):
    """Test orphan collection with no orphans."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    workers: list[Worker] = []
    orphans = collect_orphans("village", workers)
    assert orphans == []


def test_collect_orphans_stale_locks(tmp_path: Path):
    """Test orphan detection for stale locks."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config
    from village.locks import Lock, write_lock

    with patch("village.locks.get_config") as mock_locks_config:
        mock_locks_config.return_value = get_config()

        with patch("village.status.get_config") as mock_status_config:
            mock_status_config.return_value = get_config()

            with patch("village.locks.panes") as mock_panes:
                mock_panes.return_value = set()

                config = get_config()
                config.locks_dir.mkdir(parents=True, exist_ok=True)

                lock = Lock(
                    task_id="bd-stale",
                    pane_id="%99",
                    window="test-window",
                    agent="test",
                    claimed_at=datetime.now(timezone.utc),
                )
                write_lock(lock)

                workers = [
                    Worker(
                        task_id="bd-stale",
                        pane_id="%99",
                        window="test-window",
                        agent="test",
                        claimed_at=datetime.now(timezone.utc).isoformat(),
                        status="STALE",
                    )
                ]

                orphans = collect_orphans("village", workers)

                assert len(orphans) == 1
                assert orphans[0].type == "STALE_LOCK"
                assert orphans[0].task_id == "bd-stale"
                assert orphans[0].reason == "pane_not_found"

                lock.path.unlink(missing_ok=True)


def test_collect_orphans_untracked_worktrees(tmp_path: Path):
    """Test orphan detection for untracked worktrees."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.config import get_config

    with patch("village.status.get_config") as mock_status_config:
        mock_status_config.return_value = get_config()

        config = get_config()
        worktrees_dir = config.worktrees_dir
        worktrees_dir.mkdir(parents=True, exist_ok=True)

        untracked_worktree = worktrees_dir / "bd-a1e2"
        untracked_worktree.mkdir()

        workers: list[Worker] = []

        orphans = collect_orphans("village", workers)

        assert len(orphans) == 1
        assert orphans[0].type == "UNTRACKED_WORKTREE"
        assert orphans[0].task_id is None
        assert orphans[0].reason == "no_matching_lock"

        untracked_worktree.rmdir()


def test_collect_summary_empty(tmp_path: Path):
    """Test summary collection with no data."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    workers: list[Worker] = []
    orphans: list[Orphan] = []

    summary = collect_summary("village", workers, orphans)

    assert not summary.tmux_running
    assert summary.tmux_session == "village"
    assert summary.locks_count == 0
    assert summary.locks_active == 0
    assert summary.locks_stale == 0
    assert summary.worktrees_count == 0
    assert summary.worktrees_tracked == 0
    assert summary.worktrees_untracked == 0
    assert not summary.config_exists
    assert summary.orphans_count == 0


def test_collect_full_status(tmp_path: Path):
    """Test full status collection."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    status = collect_full_status("village")

    assert isinstance(status, FullStatus)
    assert isinstance(status.summary, StatusSummary)
    assert isinstance(status.workers, list)
    assert isinstance(status.orphans, list)
