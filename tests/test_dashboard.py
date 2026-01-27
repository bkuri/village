"""Test dashboard module."""

import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

from village.dashboard import (
    DashboardState,
    VillageDashboard,
    clear_screen,
    hide_cursor,
    move_cursor,
    render_dashboard,
    render_dashboard_static,
    show_cursor,
)


def test_render_dashboard_static(tmp_path: Path):
    """Test static dashboard rendering."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    output = render_dashboard_static()

    assert isinstance(output, str)
    assert "Village Dashboard" in output
    assert "ACTIVE WORKERS" in output
    assert "TASK QUEUE" in output
    assert "LOCK STATUS" in output


def test_dashboard_init():
    """Test VillageDashboard initialization."""
    dashboard = VillageDashboard()

    assert dashboard.session_name == "village"
    assert dashboard.state.max_workers == 2
    assert not dashboard._running


def test_dashboard_init_custom_session():
    """Test VillageDashboard with custom session name."""
    dashboard = VillageDashboard(session_name="custom-session")

    assert dashboard.session_name == "custom-session"
    assert dashboard.state.session_name == "custom-session"


def test_dashboard_quit():
    """Test dashboard quit method."""
    dashboard = VillageDashboard()
    dashboard._running = True

    dashboard.quit()

    assert not dashboard._running


def test_clear_screen():
    """Test clear_screen function."""
    with patch("sys.stdout.write") as mock_write:
        with patch("sys.stdout.flush") as mock_flush:
            clear_screen()
            mock_write.assert_called_once_with("\033[2J\033[H")
            mock_flush.assert_called_once()


def test_hide_cursor():
    """Test hide_cursor function."""
    with patch("sys.stdout.write") as mock_write:
        with patch("sys.stdout.flush") as mock_flush:
            hide_cursor()
            mock_write.assert_called_once_with("\033[?25l")
            mock_flush.assert_called_once()


def test_show_cursor():
    """Test show_cursor function."""
    with patch("sys.stdout.write") as mock_write:
        with patch("sys.stdout.flush") as mock_flush:
            show_cursor()
            mock_write.assert_called_once_with("\033[?25h")
            mock_flush.assert_called_once()


def test_move_cursor():
    """Test move_cursor function."""
    with patch("sys.stdout.write") as mock_write:
        with patch("sys.stdout.flush") as mock_flush:
            move_cursor(5, 10)
            mock_write.assert_called_once_with("\033[5;10H")
            mock_flush.assert_called_once()


def test_render_dashboard(tmp_path: Path):
    """Test render_dashboard function."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from datetime import datetime, timezone

    from village.queue import QueuePlan, QueueTask
    from village.status import FullStatus, StatusSummary, Worker

    full_status = FullStatus(
        summary=StatusSummary(
            tmux_running=True,
            tmux_session="village",
            locks_count=1,
            locks_active=1,
            locks_stale=0,
            worktrees_count=0,
            worktrees_tracked=0,
            worktrees_untracked=0,
            config_exists=True,
            orphans_count=0,
        ),
        workers=[
            Worker(
                task_id="bd-test",
                pane_id="%1",
                window="window1",
                agent="worker",
                claimed_at=datetime.now(timezone.utc).isoformat(),
                status="ACTIVE",
            )
        ],
        orphans=[],
    )

    queue_plan = QueuePlan(
        ready_tasks=[
            QueueTask(task_id="bd-task1", agent="worker", agent_metadata={}),
            QueueTask(task_id="bd-task2", agent="worker", agent_metadata={}),
        ],
        available_tasks=[
            QueueTask(task_id="bd-task1", agent="worker", agent_metadata={}),
        ],
        blocked_tasks=[
            QueueTask(task_id="bd-task2", agent="worker", skip_reason="active_lock"),
        ],
        slots_available=1,
        workers_count=1,
        concurrency_limit=2,
    )

    state = DashboardState(
        session_name="village",
        max_workers=2,
        last_refresh=time.time(),
    )

    with patch("sys.stdout.write") as mock_write:
        with patch("sys.stdout.flush") as mock_flush:
            render_dashboard(full_status, queue_plan, [], state)

            assert mock_write.call_count > 0
            assert mock_flush.call_count > 0


def test_render_dashboard_with_orphans(tmp_path: Path):
    """Test render_dashboard with orphans."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.queue import QueuePlan
    from village.status import FullStatus, Orphan, StatusSummary

    full_status = FullStatus(
        summary=StatusSummary(
            tmux_running=True,
            tmux_session="village",
            locks_count=0,
            locks_active=0,
            locks_stale=0,
            worktrees_count=0,
            worktrees_tracked=0,
            worktrees_untracked=0,
            config_exists=True,
            orphans_count=2,
        ),
        workers=[],
        orphans=[
            Orphan(
                type="STALE_LOCK",
                task_id="bd-stale",
                path="/tmp/stale.lock",
                reason="pane_not_found",
            ),
            Orphan(
                type="UNTRACKED_WORKTREE",
                task_id=None,
                path="/tmp/untracked-worktree",
                reason="no_matching_lock",
            ),
        ],
    )

    queue_plan = QueuePlan(
        ready_tasks=[],
        available_tasks=[],
        blocked_tasks=[],
        slots_available=2,
        workers_count=0,
        concurrency_limit=2,
    )

    state = DashboardState(
        session_name="village",
        max_workers=2,
        last_refresh=time.time(),
    )

    with patch("sys.stdout.write") as mock_write:
        with patch("sys.stdout.flush"):
            render_dashboard(full_status, queue_plan, full_status.orphans, state)

            assert mock_write.call_count > 0


def test_dashboard_wait_for_input_no_input():
    """Test _wait_for_input when no input available."""
    dashboard = VillageDashboard()

    with patch("select.select", return_value=([], [], [])):
        result = dashboard._wait_for_input(1)
        assert not result


def test_dashboard_wait_for_input_available():
    """Test _wait_for_input when input is available."""
    dashboard = VillageDashboard()

    with patch("select.select", return_value=([sys.stdin], [], [])):
        result = dashboard._wait_for_input(1)
        assert result


def test_dashboard_handle_input_quit():
    """Test _handle_input with quit command."""
    dashboard = VillageDashboard()

    with patch("sys.stdin.read", return_value="q"):
        result = dashboard._handle_input()
        assert result


def test_dashboard_handle_input_refresh():
    """Test _handle_input with refresh command."""
    dashboard = VillageDashboard()
    dashboard.refresh_display = Mock()

    with patch("sys.stdin.read", return_value="r"):
        result = dashboard._handle_input()
        assert not result
        dashboard.refresh_display.assert_called_once()


def test_dashboard_handle_input_quit_uppercase():
    """Test _handle_input with uppercase quit command."""
    dashboard = VillageDashboard()

    with patch("sys.stdin.read", return_value="Q"):
        result = dashboard._handle_input()
        assert result


def test_dashboard_handle_input_error():
    """Test _handle_input handles IOError gracefully."""
    dashboard = VillageDashboard()

    with patch("sys.stdin.read", side_effect=IOError("Mock error")):
        result = dashboard._handle_input()
        assert not result


def test_dashboard_state_dataclass():
    """Test DashboardState dataclass."""
    state = DashboardState(
        session_name="test",
        max_workers=5,
        last_refresh=123.456,
    )

    assert state.session_name == "test"
    assert state.max_workers == 5
    assert state.last_refresh == 123.456


def test_render_dashboard_static_content(tmp_path: Path):
    """Test render_dashboard_static output content."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    output = render_dashboard_static()

    lines = output.split("\n")

    assert any("Village Dashboard" in line for line in lines)
    assert any("ACTIVE WORKERS" in line for line in lines)
    assert any("TASK QUEUE" in line for line in lines)
    assert any("LOCK STATUS" in line for line in lines)


def test_render_dashboard_with_no_workers(tmp_path: Path):
    """Test render_dashboard when no workers are active."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.queue import QueuePlan
    from village.status import FullStatus, StatusSummary

    full_status = FullStatus(
        summary=StatusSummary(
            tmux_running=True,
            tmux_session="village",
            locks_count=0,
            locks_active=0,
            locks_stale=0,
            worktrees_count=0,
            worktrees_tracked=0,
            worktrees_untracked=0,
            config_exists=True,
            orphans_count=0,
        ),
        workers=[],
        orphans=[],
    )

    queue_plan = QueuePlan(
        ready_tasks=[],
        available_tasks=[],
        blocked_tasks=[],
        slots_available=2,
        workers_count=0,
        concurrency_limit=2,
    )

    state = DashboardState(
        session_name="village",
        max_workers=2,
        last_refresh=time.time(),
    )

    with patch("sys.stdout.write") as mock_write:
        with patch("sys.stdout.flush"):
            render_dashboard(full_status, queue_plan, [], state)

            written_output = "".join(call[0][0] for call in mock_write.call_args_list)
            assert "No active workers" in written_output


def test_render_dashboard_with_many_tasks(tmp_path: Path):
    """Test render_dashboard truncates long task lists."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    os.chdir(tmp_path)

    from village.queue import QueuePlan, QueueTask
    from village.status import FullStatus, StatusSummary

    full_status = FullStatus(
        summary=StatusSummary(
            tmux_running=True,
            tmux_session="village",
            locks_count=0,
            locks_active=0,
            locks_stale=0,
            worktrees_count=0,
            worktrees_tracked=0,
            worktrees_untracked=0,
            config_exists=True,
            orphans_count=0,
        ),
        workers=[],
        orphans=[],
    )

    available_tasks = [
        QueueTask(task_id=f"bd-task{i}", agent="worker", agent_metadata={}) for i in range(10)
    ]
    blocked_tasks = [
        QueueTask(task_id=f"bd-blocked{i}", agent="worker", skip_reason="test") for i in range(10)
    ]

    queue_plan = QueuePlan(
        ready_tasks=available_tasks + blocked_tasks,
        available_tasks=available_tasks,
        blocked_tasks=blocked_tasks,
        slots_available=2,
        workers_count=0,
        concurrency_limit=2,
    )

    state = DashboardState(
        session_name="village",
        max_workers=2,
        last_refresh=time.time(),
    )

    with patch("sys.stdout.write") as mock_write:
        with patch("sys.stdout.flush"):
            render_dashboard(full_status, queue_plan, [], state)

            written_output = "".join(call[0][0] for call in mock_write.call_args_list)
            assert "and 5 more" in written_output
