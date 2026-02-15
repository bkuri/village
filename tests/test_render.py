"""Test renderer functions in isolation."""

import json
import os
import subprocess
from pathlib import Path

from village.chat.drafts import DraftTask
from village.ready import ReadyAssessment, SuggestedAction
from village.render.json import render_status_json
from village.render.text import (
    format_datetime,
    render_full_status,
    render_initialization_plan,
    render_orphans_grouped,
    render_ready_text,
    render_resume_actions,
    render_resume_result,
    render_summary,
    render_worker_table,
)
from village.resume import ResumeAction, ResumeResult
from village.runtime import InitializationPlan
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


def test_render_full_status_with_locks():
    """Test full status rendering with locks flag."""
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

    flags = {"workers": False, "locks": True, "orphans": False}
    output = render_full_status(status, flags)
    assert "TASK_ID" in output
    assert "bd-a3f8" in output


def test_render_full_status_with_orphans():
    """Test full status rendering with orphans flag."""
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
            worktrees_count=0,
            worktrees_tracked=0,
            worktrees_untracked=0,
            config_exists=True,
            orphans_count=1,
        ),
        workers=[],
        orphans=orphans,
    )

    flags = {"workers": False, "locks": False, "orphans": True}
    output = render_full_status(status, flags)
    assert "ORPHANS" in output
    assert "STALE LOCKS" in output


def test_render_resume_result_success():
    """Test render_resume_result with success."""
    result = ResumeResult(
        success=True,
        task_id="bd-a3f8",
        agent="build",
        worktree_path=Path("/tmp/.worktrees/bd-a3f8"),
        window_name="build-1-bd-a3f8",
        pane_id="%12",
    )

    output = render_resume_result(result)
    assert "✓ Resume successful: bd-a3f8" in output
    assert "Window: build-1-bd-a3f8" in output
    assert "Pane: %12" in output
    assert "Worktree:" in output


def test_render_resume_result_failure():
    """Test render_resume_result with failure."""
    result = ResumeResult(
        success=False,
        task_id="bd-a3f8",
        agent="build",
        worktree_path=Path(""),
        window_name="",
        pane_id="",
        error="Failed to create worktree",
    )

    output = render_resume_result(result)
    assert "✗ Resume failed: bd-a3f8" in output
    assert "Error: Failed to create worktree" in output


def test_render_resume_actions_without_meta():
    """Test render_resume_actions without metadata."""
    action = ResumeAction(
        action="resume",
        reason="Task ready",
        blocking=False,
        meta={},
    )

    output = render_resume_actions(action)
    assert "Action: village resume" in output
    assert "Reason: Task ready" in output
    assert "Run:" not in output


def test_render_resume_actions_with_meta():
    """Test render_resume_actions with metadata."""
    action = ResumeAction(
        action="up",
        reason="Runtime not initialized",
        blocking=True,
        meta={"command": "village up --detached"},
    )

    output = render_resume_actions(action)
    assert "Action: village up" in output
    assert "Reason: Runtime not initialized" in output
    assert "Run: village up --detached" in output


def test_render_initialization_plan_new():
    """Test render_initialization_plan with new session."""
    plan = InitializationPlan(
        needs_session=True,
        needs_directories=True,
        needs_beads_init=True,
        session_exists=False,
        directories_exist=False,
        beads_initialized=False,
    )

    output = render_initialization_plan(plan, "village", plan_mode=True)
    assert "DRY RUN:  Would initialize village runtime" in output
    assert "Session: village (new)" in output
    assert "Directories: .village/ (create)" in output
    assert "Beads: would initialize (not found)" in output


def test_render_initialization_plan_existing():
    """Test render_initialization_plan with existing session."""
    plan = InitializationPlan(
        needs_session=False,
        needs_directories=False,
        needs_beads_init=False,
        session_exists=True,
        directories_exist=True,
        beads_initialized=True,
    )

    output = render_initialization_plan(plan, "village", plan_mode=False)
    assert "Session: village (exists)" in output
    assert "Directories: .village/ (exists)" in output
    assert "Beads: .beads/ (exists)" in output
    assert "DRY RUN:" not in output


def test_render_suggested_actions_empty():
    """Test render_suggested_actions with empty list."""
    from village.render.text import render_suggested_actions

    actions: list[SuggestedAction] = []
    output = render_suggested_actions(actions)
    assert "SUGGESTED ACTIONS:" in output
    assert "None (everything looks good)" in output


def test_render_ready_text_work_available():
    """Test render_ready_text with work available."""
    assessment = ReadyAssessment(
        overall="ready",
        environment_ready=True,
        runtime_ready=True,
        work_available="available",
        orphans_count=0,
        stale_locks_count=0,
        untracked_worktrees_count=0,
        active_workers_count=0,
        ready_tasks_count=2,
        suggested_actions=[],
        error=None,
    )

    output = render_ready_text(assessment)
    assert "OVERALL STATUS: READY" in output
    assert "Environment Check:   ✓ Git repository found" in output
    assert "Runtime Check:       ✓ Tmux session running" in output
    assert "Work Available:      ✓ 2 ready task(s) available" in output
    assert "Orphans:             ✓ None" in output


def test_render_ready_text_work_not_available():
    """Test render_ready_text with no work available."""
    assessment = ReadyAssessment(
        overall="ready",
        environment_ready=True,
        runtime_ready=True,
        work_available="not_available",
        orphans_count=0,
        stale_locks_count=0,
        untracked_worktrees_count=0,
        active_workers_count=0,
        ready_tasks_count=0,
        suggested_actions=[],
        error=None,
    )

    output = render_ready_text(assessment)
    assert "Work Available:      ✓ No ready tasks available" in output


def test_render_ready_text_work_unknown():
    """Test render_ready_text with unknown work status."""
    assessment = ReadyAssessment(
        overall="not_ready",
        environment_ready=True,
        runtime_ready=False,
        work_available="unknown",
        orphans_count=0,
        stale_locks_count=0,
        untracked_worktrees_count=0,
        active_workers_count=0,
        ready_tasks_count=0,
        suggested_actions=[],
        error=None,
    )

    output = render_ready_text(assessment)
    assert "Work Available:      ? Cannot determine (Beads not available)" in output


def test_render_ready_text_with_orphans():
    """Test render_ready_text with orphans."""
    assessment = ReadyAssessment(
        overall="not_ready",
        environment_ready=True,
        runtime_ready=True,
        work_available="available",
        orphans_count=3,
        stale_locks_count=2,
        untracked_worktrees_count=1,
        active_workers_count=0,
        ready_tasks_count=0,
        suggested_actions=[],
        error=None,
    )

    output = render_ready_text(assessment)
    assert "Orphans:             ✗ 2 stale locks, 1 untracked worktrees" in output


def test_render_ready_text_with_error():
    """Test render_ready_text with error."""
    assessment = ReadyAssessment(
        overall="error",
        environment_ready=False,
        runtime_ready=False,
        work_available="unknown",
        orphans_count=0,
        stale_locks_count=0,
        untracked_worktrees_count=0,
        active_workers_count=0,
        ready_tasks_count=0,
        suggested_actions=[],
        error="Failed to initialize tmux session",
    )

    output = render_ready_text(assessment)
    assert "ERROR: Failed to initialize tmux session" in output


def test_render_suggested_actions_with_blocking():
    """Test render_suggested_actions with blocking actions."""
    from village.render.text import render_suggested_actions

    actions = [
        SuggestedAction(
            action="village up",
            reason="Runtime not initialized",
            blocking=True,
        ),
        SuggestedAction(
            action="village cleanup",
            reason="Remove 2 stale locks",
            blocking=False,
        ),
    ]

    output = render_suggested_actions(actions)
    assert "SUGGESTED ACTIONS:" in output
    assert "1. [BLOCKING] village up" in output
    assert "2. village cleanup" in output
    assert "[BLOCKING]" in output


def test_render_drafts_table_empty():
    """Test render_drafts_table with no drafts."""
    from village.render.text import render_drafts_table

    drafts: list[DraftTask] = []
    output = render_drafts_table(drafts)
    assert output == "No drafts found."


def test_render_drafts_table_with_drafts():
    """Test render_drafts_table with drafts."""
    from datetime import datetime, timezone

    from village.render.text import render_drafts_table

    drafts = [
        DraftTask(
            id="draft-1",
            title="Fix bug in authentication module",
            description="Users cannot login",
            created_at=datetime.now(timezone.utc),
            scope="fix",
        ),
        DraftTask(
            id="draft-2",
            title="Add unit tests for queue",
            description="Improve test coverage",
            created_at=datetime.now(timezone.utc),
            scope="feature",
        ),
    ]

    output = render_drafts_table(drafts)
    assert "draft-1" in output
    assert "Fix bug in authentication module" in output
    assert "draft-2" in output
    assert "Add unit tests for queue" in output
