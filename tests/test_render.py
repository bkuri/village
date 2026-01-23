"""Test renderer functions in isolation."""

import json
import os
import subprocess
from pathlib import Path

from village.render.json import render_status_json
from village.render.text import (
    format_datetime,
    render_full_status,
    render_orphans_grouped,
    render_summary,
    render_worker_table,
)
from village.status import FullStatus, Orphan, StatusSummary, Worker


def test_format_datetime():
    """Test datetime formatting."""
    iso_string = "2026-01-22T10:41:12+00:00"
    formatted = format_datetime(iso_string)
    assert "2026-01-22" in formatted
    assert "10:41:12" in formatted
    assert "UTC" in formatted


def test_format_datetime_invalid():
    """Test datetime formatting with invalid input."""
    formatted = format_datetime("invalid")
    assert formatted == "invalid"


def test_render_worker_table_empty():
    """Test worker table with no workers."""
    workers: list[Worker] = []
    output = render_worker_table(workers)
    assert output == "No workers found"


def test_render_worker_table_single():
    """Test worker table with one worker."""
    workers = [
        Worker(
            task_id="bd-a3f8",
            pane_id="%12",
            window="build-1-bd-a3f8",
            agent="build",
            claimed_at="2026-01-22T10:41:12+00:00",
            status="ACTIVE",
        )
    ]
    output = render_worker_table(workers)
    assert "TASK_ID" in output
    assert "bd-a3f8" in output
    assert "ACTIVE" in output
    assert "%12" in output


def test_render_worker_table_multiple():
    """Test worker table with multiple workers."""
    workers = [
        Worker(
            task_id="bd-a3f8",
            pane_id="%12",
            window="build-1-bd-a3f8",
            agent="build",
            claimed_at="2026-01-22T10:41:12+00:00",
            status="ACTIVE",
        ),
        Worker(
            task_id="bd-b4f2",
            pane_id="%99",
            window="test-2-bd-b4f2",
            agent="test",
            claimed_at="2026-01-22T11:15:30+00:00",
            status="STALE",
        ),
    ]
    output = render_worker_table(workers)
    assert "TASK_ID" in output
    assert "bd-a3f8" in output
    assert "bd-b4f2" in output
    assert "ACTIVE" in output
    assert "STALE" in output


def test_render_orphans_grouped_empty():
    """Test orphan grouped rendering with no orphans."""
    orphans: list[Orphan] = []
    output = render_orphans_grouped(orphans)
    assert output == "No orphans found"


def test_render_orphans_grouped_stale_locks():
    """Test orphan grouped rendering with stale locks."""
    orphans = [
        Orphan(
            type="STALE_LOCK",
            task_id="bd-stale",
            path="/path/.village/locks/bd-stale.lock",
            reason="pane_not_found",
        )
    ]
    output = render_orphans_grouped(orphans)
    assert "ORPHANS" in output
    assert "STALE LOCKS" in output
    assert "bd-stale" in output
    assert "SUGGESTED ACTIONS" in output
    assert "village cleanup" in output


def test_render_orphans_grouped_no_actions():
    """Test orphan grouped rendering without suggested actions."""
    orphans = [
        Orphan(
            type="STALE_LOCK",
            task_id="bd-stale",
            path="/path/.village/locks/bd-stale.lock",
            reason="pane_not_found",
        )
    ]
    output = render_orphans_grouped(orphans, show_actions=False)
    assert "ORPHANS" in output
    assert "STALE LOCKS" in output
    assert "SUGGESTED ACTIONS" not in output


def test_render_orphans_grouped_mixed():
    """Test orphan grouped rendering with mixed types."""
    orphans = [
        Orphan(
            type="STALE_LOCK",
            task_id="bd-stale",
            path="/path/.village/locks/bd-stale.lock",
            reason="pane_not_found",
        ),
        Orphan(
            type="UNTRACKED_WORKTREE",
            task_id=None,
            path="/path/.worktrees/bd-a1e2",
            reason="no_matching_lock",
        ),
    ]
    output = render_orphans_grouped(orphans)
    assert "ORPHANS (2):" in output
    assert "STALE LOCKS (1):" in output
    assert "UNTRACKED WORKTREES (1):" in output
    assert "SUGGESTED ACTIONS" in output


def test_render_summary_empty():
    """Test summary rendering with no data."""
    summary = StatusSummary(
        tmux_running=False,
        tmux_session="village",
        locks_count=0,
        locks_active=0,
        locks_stale=0,
        worktrees_count=0,
        worktrees_tracked=0,
        worktrees_untracked=0,
        config_exists=False,
        orphans_count=0,
    )
    output = render_summary(summary)
    assert "Village directory:" in output
    assert "TMUX session:" in output
    assert "not running" in output
    assert "Lock files: 0 (0 ACTIVE, 0 STALE)" in output
    assert "Worktrees: 0 (0 tracked, 0 untracked)" in output
    assert "Config file: not created" in output


def test_render_summary_with_data():
    """Test summary rendering with data."""
    summary = StatusSummary(
        tmux_running=True,
        tmux_session="village",
        locks_count=2,
        locks_active=1,
        locks_stale=1,
        worktrees_count=3,
        worktrees_tracked=2,
        worktrees_untracked=1,
        config_exists=True,
        orphans_count=2,
    )
    output = render_summary(summary)
    assert "Village directory:" in output
    assert "TMUX session: village running" in output
    assert "Lock files: 2 (1 ACTIVE, 1 STALE)" in output
    assert "Worktrees: 3 (2 tracked, 1 untracked)" in output
    assert "Config file: exists" in output
    assert "WARNING: Orphans detected" in output


def test_render_full_status_no_flags(tmp_path: Path):
    """Test full status rendering with no flags."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    summary = StatusSummary(
        tmux_running=False,
        tmux_session="village",
        locks_count=0,
        locks_active=0,
        locks_stale=0,
        worktrees_count=0,
        worktrees_tracked=0,
        worktrees_untracked=0,
        config_exists=False,
        orphans_count=0,
    )

    status = FullStatus(
        summary=summary,
        workers=[],
        orphans=[],
    )

    flags = {"workers": False, "locks": False, "orphans": False}
    output = render_full_status(status, flags)
    assert "Village directory:" in output
    assert "Use --workers, --locks, --orphans for details." in output


def test_render_full_status_with_workers():
    """Test full status rendering with workers flag."""
    workers = [
        Worker(
            task_id="bd-a3f8",
            pane_id="%12",
            window="build-1-bd-a3f8",
            agent="build",
            claimed_at="2026-01-22T10:41:12+00:00",
            status="ACTIVE",
        )
    ]

    status = FullStatus(
        summary=StatusSummary(
            tmux_running=True,
            tmux_session="village",
            locks_count=1,
            locks_active=1,
            locks_stale=0,
            worktrees_count=1,
            worktrees_tracked=1,
            worktrees_untracked=0,
            config_exists=True,
            orphans_count=0,
        ),
        workers=workers,
        orphans=[],
    )

    flags = {"workers": True, "locks": False, "orphans": False}
    output = render_full_status(status, flags)
    assert "TASK_ID" in output
    assert "bd-a3f8" in output


def test_render_status_json(tmp_path: Path):
    """Test JSON renderer."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    workers = [
        Worker(
            task_id="bd-a3f8",
            pane_id="%12",
            window="build-1-bd-a3f8",
            agent="build",
            claimed_at="2026-01-22T10:41:12+00:00",
            status="ACTIVE",
        )
    ]

    status = FullStatus(
        summary=StatusSummary(
            tmux_running=True,
            tmux_session="village",
            locks_count=1,
            locks_active=1,
            locks_stale=0,
            worktrees_count=1,
            worktrees_tracked=1,
            worktrees_untracked=0,
            config_exists=True,
            orphans_count=0,
        ),
        workers=workers,
        orphans=[],
    )

    output = render_status_json(status)
    data = json.loads(output)

    assert data["command"] == "status"
    assert data["version"] == 1
    assert "summary" in data
    assert "workers" in data
    assert "orphans" in data
    assert len(data["workers"]) == 1
    assert data["workers"][0]["task_id"] == "bd-a3f8"
    assert data["workers"][0]["status"] == "ACTIVE"


def test_render_status_json_no_actions():
    """Test JSON renderer has no suggested actions."""
    orphans = [
        Orphan(
            type="STALE_LOCK",
            task_id="bd-stale",
            path="/path/.village/locks/bd-stale.lock",
            reason="pane_not_found",
        )
    ]

    status = FullStatus(
        summary=StatusSummary(
            tmux_running=False,
            tmux_session="village",
            locks_count=1,
            locks_active=0,
            locks_stale=1,
            worktrees_count=1,
            worktrees_tracked=0,
            worktrees_untracked=1,
            config_exists=True,
            orphans_count=1,
        ),
        workers=[],
        orphans=orphans,
    )

    output = render_status_json(status)
    data = json.loads(output)

    assert "suggested_actions" not in data
    assert "orphans" in data
    assert len(data["orphans"]) == 1
