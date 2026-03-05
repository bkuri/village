"""Tests for ACP bridge."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from village.acp.bridge import ACPBridge, ACPBridgeError
from village.config import Config
from village.event_log import Event, append_event
from village.locks import Lock, write_lock
from village.state_machine import TaskState


@pytest.fixture
def bridge(tmp_path: Path):
    """Create ACP bridge with temp config."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.village_dir.mkdir(parents=True, exist_ok=True)
    config.locks_dir.mkdir(parents=True, exist_ok=True)
    config.worktrees_dir.mkdir(parents=True, exist_ok=True)

    return ACPBridge(config)


@pytest.fixture
def bridge_with_lock(bridge: ACPBridge):
    """Create bridge with an active lock."""
    from datetime import datetime, timezone

    task_id = "test-locked"
    lock = Lock(
        task_id=task_id,
        pane_id="%99",
        window="test-window",
        agent="test-agent",
        claimed_at=datetime.now(timezone.utc),
    )
    lock._config = bridge.config
    write_lock(lock)
    return bridge, task_id, lock


@pytest.fixture
def bridge_with_worktree(bridge: ACPBridge):
    """Create bridge with worktree."""
    task_id = "test-worktree"
    worktree_path = bridge.config.worktrees_dir / task_id
    worktree_path.mkdir(parents=True, exist_ok=True)
    (worktree_path / "test.txt").write_text("test content")
    return bridge, task_id, worktree_path


@pytest.mark.asyncio
async def test_bridge_session_new(bridge: ACPBridge):
    """Test creating new ACP session."""
    result = await bridge.session_new({"sessionId": "test-123"})

    assert result["sessionId"] == "test-123"
    assert result["state"] == "queued"


@pytest.mark.asyncio
async def test_bridge_session_new_requires_id(bridge: ACPBridge):
    """Test session/new requires sessionId."""
    with pytest.raises(ACPBridgeError, match="sessionId required"):
        await bridge.session_new({})


@pytest.mark.asyncio
async def test_bridge_session_load_not_found(bridge: ACPBridge):
    """Test loading non-existent session."""
    with pytest.raises(ACPBridgeError, match="Task not found"):
        await bridge.session_load({"sessionId": "nonexistent"})


@pytest.mark.asyncio
async def test_bridge_session_load_existing(bridge: ACPBridge):
    """Test loading existing session."""
    # Create session first
    await bridge.session_new({"sessionId": "test-456"})

    # Load it
    result = await bridge.session_load({"sessionId": "test-456"})

    assert result["sessionId"] == "test-456"
    assert result["state"] == "queued"


@pytest.mark.asyncio
async def test_bridge_session_cancel(bridge: ACPBridge):
    """Test cancelling session."""
    # Create session
    await bridge.session_new({"sessionId": "test-789"})

    # Cancel it (from QUEUED state, should transition to FAILED)
    result = await bridge.session_cancel({"sessionId": "test-789"})

    assert result["sessionId"] == "test-789"
    assert result["state"] == "failed"


@pytest.mark.asyncio
async def test_bridge_fs_read_not_in_worktree(bridge: ACPBridge):
    """Test reading file outside worktree fails."""
    with pytest.raises(ACPBridgeError, match="not in Village worktree"):
        await bridge.fs_read_text_file({"path": "/tmp/test.txt"})


@pytest.mark.asyncio
async def test_bridge_fs_write_not_in_worktree(bridge: ACPBridge):
    """Test writing file outside worktree fails."""
    with pytest.raises(ACPBridgeError, match="not in Village worktree"):
        await bridge.fs_write_text_file(
            {
                "path": "/tmp/test.txt",
                "content": "test",
            }
        )


# === Terminal API Tests ===


@pytest.mark.asyncio
async def test_bridge_terminal_create_requires_session_id(bridge: ACPBridge):
    """Test terminal/create requires sessionId."""
    with pytest.raises(ACPBridgeError, match="sessionId required"):
        await bridge.terminal_create({"command": "ls"})


@pytest.mark.asyncio
async def test_bridge_terminal_create_requires_active_task(bridge: ACPBridge):
    """Test terminal/create requires active task."""
    # Create session but don't claim it (not active)
    await bridge.session_new({"sessionId": "test-term-1"})

    with pytest.raises(ACPBridgeError, match="Task not active"):
        await bridge.terminal_create({"sessionId": "test-term-1", "command": "ls"})


@pytest.mark.asyncio
async def test_bridge_terminal_output_requires_ids(bridge: ACPBridge):
    """Test terminal/output requires sessionId and terminalId."""
    with pytest.raises(ACPBridgeError, match="sessionId required"):
        await bridge.terminal_output({"terminalId": "term-123"})

    with pytest.raises(ACPBridgeError, match="terminalId required"):
        await bridge.terminal_output({"sessionId": "test-123"})


@pytest.mark.asyncio
async def test_bridge_terminal_output_nonexistent_terminal(bridge: ACPBridge):
    """Test terminal/output fails for nonexistent terminal."""
    with pytest.raises(ACPBridgeError, match="Terminal not found"):
        await bridge.terminal_output({"sessionId": "test-123", "terminalId": "term-999"})


@pytest.mark.asyncio
async def test_bridge_terminal_kill_requires_ids(bridge: ACPBridge):
    """Test terminal/kill requires sessionId and terminalId."""
    with pytest.raises(ACPBridgeError, match="sessionId required"):
        await bridge.terminal_kill({"terminalId": "term-123"})


@pytest.mark.asyncio
async def test_bridge_terminal_release_requires_ids(bridge: ACPBridge):
    """Test terminal/release requires sessionId and terminalId."""
    with pytest.raises(ACPBridgeError, match="sessionId required"):
        await bridge.terminal_release({"terminalId": "term-123"})


@pytest.mark.asyncio
async def test_bridge_terminal_wait_requires_ids(bridge: ACPBridge):
    """Test terminal/wait_for_exit requires sessionId and terminalId."""
    with pytest.raises(ACPBridgeError, match="sessionId required"):
        await bridge.terminal_wait_for_exit({"terminalId": "term-123"})

    with pytest.raises(ACPBridgeError, match="terminalId required"):
        await bridge.terminal_wait_for_exit({"sessionId": "test-123"})


# === Notification Streaming Tests ===


@pytest.mark.asyncio
async def test_bridge_event_to_notification_state_change(bridge: ACPBridge):
    """Test state_transition event maps to state_change notification."""
    from village.event_log import Event

    event = Event(
        ts="2026-03-05T00:00:00Z",
        cmd="state_transition",
        task_id="test-123",
        result="ok",
    )

    notification = bridge._event_to_notification(event)

    assert notification["method"] == "session/update"
    assert notification["params"]["sessionId"] == "test-123"
    assert notification["params"]["update"]["type"] == "state_change"
    assert notification["params"]["update"]["cmd"] == "state_transition"
    assert notification["params"]["update"]["result"] == "ok"


@pytest.mark.asyncio
async def test_bridge_event_to_notification_file_change(bridge: ACPBridge):
    """Test file_modified event maps to file_change notification."""
    from village.event_log import Event

    event = Event(
        ts="2026-03-05T00:00:00Z",
        cmd="file_modified",
        task_id="test-456",
    )

    notification = bridge._event_to_notification(event)

    assert notification["method"] == "session/update"
    assert notification["params"]["sessionId"] == "test-456"
    assert notification["params"]["update"]["type"] == "file_change"
    assert notification["params"]["update"]["cmd"] == "file_modified"


@pytest.mark.asyncio
async def test_bridge_event_to_notification_conflict(bridge: ACPBridge):
    """Test conflict_detected event maps to conflict notification."""
    from village.event_log import Event

    event = Event(
        ts="2026-03-05T00:00:00Z",
        cmd="conflict_detected",
        task_id="test-789",
        error="Merge conflict in src/main.py",
    )

    notification = bridge._event_to_notification(event)

    assert notification["method"] == "session/update"
    assert notification["params"]["sessionId"] == "test-789"
    assert notification["params"]["update"]["type"] == "conflict"
    assert notification["params"]["update"]["cmd"] == "conflict_detected"
    assert notification["params"]["update"]["error"] == "Merge conflict in src/main.py"


@pytest.mark.asyncio
async def test_bridge_event_to_notification_lifecycle(bridge: ACPBridge):
    """Test lifecycle events (queue, resume, cleanup) map correctly."""
    from village.event_log import Event

    for cmd in ["queue", "resume", "cleanup"]:
        event = Event(
            ts="2026-03-05T00:00:00Z",
            cmd=cmd,
            task_id="test-lifecycle",
            result="ok",
        )

        notification = bridge._event_to_notification(event)

        assert notification["params"]["update"]["type"] == "lifecycle"
        assert notification["params"]["update"]["cmd"] == cmd


@pytest.mark.asyncio
async def test_bridge_event_to_notification_error(bridge: ACPBridge):
    """Test error events map to error notification type."""
    from village.event_log import Event

    event = Event(
        ts="2026-03-05T00:00:00Z",
        cmd="resume",
        task_id="test-error",
        result="error",
        error="Failed to execute task",
    )

    notification = bridge._event_to_notification(event)

    assert notification["params"]["update"]["type"] == "error"
    assert notification["params"]["update"]["error"] == "Failed to execute task"


@pytest.mark.asyncio
async def test_bridge_stream_notifications_yields_events(bridge: ACPBridge):
    """Test stream_notifications generator exists and can be iterated."""
    # Just verify the stream can be created and is an async generator
    from collections.abc import AsyncGenerator

    stream = bridge.stream_notifications("test-session", poll_interval=0.1)
    assert isinstance(stream, AsyncGenerator)

    # Don't actually iterate - just verify it's the right type
    # Real-time streaming is better tested in integration tests


# === Edge Cases and Error Handling ===


@pytest.mark.asyncio
async def test_bridge_session_new_with_special_characters(bridge: ACPBridge):
    """Test session ID with special characters."""
    session_id = "test-session-with-dashes-and_underscores"
    result = await bridge.session_new({"sessionId": session_id})
    assert result["sessionId"] == session_id


@pytest.mark.asyncio
async def test_bridge_session_new_with_context(bridge: ACPBridge):
    """Test session creation with additional context."""
    result = await bridge.session_new({"sessionId": "test-context", "agent": "claude-code", "cwd": "/tmp"})
    assert result["sessionId"] == "test-context"


@pytest.mark.asyncio
async def test_bridge_session_load_with_lock(bridge_with_lock: tuple):
    """Test loading session that has a lock."""
    bridge, task_id, lock = bridge_with_lock

    # Initialize state
    bridge.state_machine.initialize_state(task_id, TaskState.QUEUED)

    result = await bridge.session_load({"sessionId": task_id})
    assert result["sessionId"] == task_id
    assert result["lock"] is not None
    assert result["lock"]["taskId"] == task_id


@pytest.mark.asyncio
async def test_bridge_session_cancel_from_claimed_state(bridge: ACPBridge):
    """Test cancelling session from CLAIMED state."""
    session_id = "test-cancel-claimed"

    # Create and claim
    await bridge.session_new({"sessionId": session_id})
    bridge.state_machine.transition(session_id, TaskState.CLAIMED)

    # Cancel from CLAIMED
    result = await bridge.session_cancel({"sessionId": session_id})
    assert result["state"] == "failed"


@pytest.mark.asyncio
async def test_bridge_session_cancel_from_in_progress_state(bridge: ACPBridge):
    """Test cancelling session from IN_PROGRESS state."""
    session_id = "test-cancel-progress"

    # Create and start
    await bridge.session_new({"sessionId": session_id})
    bridge.state_machine.transition(session_id, TaskState.CLAIMED)
    bridge.state_machine.transition(session_id, TaskState.IN_PROGRESS)

    # Cancel from IN_PROGRESS (should pause)
    result = await bridge.session_cancel({"sessionId": session_id})
    assert result["state"] == "paused"


@pytest.mark.asyncio
async def test_bridge_session_cancel_from_completed_state(bridge: ACPBridge):
    """Test cancelling session from COMPLETED state."""
    session_id = "test-cancel-completed"

    # Create and complete
    await bridge.session_new({"sessionId": session_id})
    bridge.state_machine.transition(session_id, TaskState.CLAIMED)
    bridge.state_machine.transition(session_id, TaskState.IN_PROGRESS)
    bridge.state_machine.transition(session_id, TaskState.COMPLETED)

    # Cancel from COMPLETED (no-op)
    result = await bridge.session_cancel({"sessionId": session_id})
    assert result["state"] == "completed"


@pytest.mark.asyncio
async def test_bridge_session_cancel_from_paused_state(bridge: ACPBridge):
    """Test cancelling session from PAUSED state."""
    session_id = "test-cancel-paused"

    # Create and pause
    await bridge.session_new({"sessionId": session_id})
    bridge.state_machine.transition(session_id, TaskState.CLAIMED)
    bridge.state_machine.transition(session_id, TaskState.IN_PROGRESS)
    bridge.state_machine.transition(session_id, TaskState.PAUSED)

    # Cancel from PAUSED (no-op)
    result = await bridge.session_cancel({"sessionId": session_id})
    assert result["state"] == "paused"


# === File System Edge Cases ===


@pytest.mark.asyncio
async def test_bridge_fs_read_with_relative_path(bridge: ACPBridge):
    """Test reading with relative path fails."""
    with pytest.raises(ACPBridgeError):
        await bridge.fs_read_text_file({"path": "../test.txt"})


@pytest.mark.asyncio
async def test_bridge_fs_read_empty_path(bridge: ACPBridge):
    """Test reading with empty path fails."""
    with pytest.raises(ACPBridgeError):
        await bridge.fs_read_text_file({"path": ""})


@pytest.mark.asyncio
async def test_bridge_fs_write_empty_content(bridge_with_worktree: tuple):
    """Test writing empty content."""
    bridge, task_id, worktree_path = bridge_with_worktree

    # Create lock to make task "active"
    from datetime import datetime, timezone

    lock = Lock(
        task_id=task_id,
        pane_id="%99",
        window="test",
        agent="test",
        claimed_at=datetime.now(timezone.utc),
    )
    lock._config = bridge.config
    write_lock(lock)

    file_path = worktree_path / "empty.txt"
    result = await bridge.fs_write_text_file({"path": str(file_path), "content": ""})

    assert result["success"]
    assert file_path.read_text() == ""


# === Terminal API Edge Cases ===


@pytest.mark.asyncio
async def test_bridge_terminal_create_with_args(bridge_with_lock: tuple):
    """Test terminal creation with command args."""
    bridge, task_id, lock = bridge_with_lock

    # Make task active by transitioning state
    bridge.state_machine.initialize_state(task_id, TaskState.QUEUED)
    bridge.state_machine.transition(task_id, TaskState.CLAIMED)
    bridge.state_machine.transition(task_id, TaskState.IN_PROGRESS)

    with patch("village.probes.tmux.create_window") as mock_create:
        mock_create.return_value = True

        result = await bridge.terminal_create(
            {
                "sessionId": task_id,
                "command": "python",
                "args": ["-m", "pytest"],
            }
        )

        assert "terminalId" in result
        assert result["terminalId"].startswith("term-")


@pytest.mark.asyncio
async def test_bridge_terminal_create_with_env(bridge_with_lock: tuple):
    """Test terminal creation with environment variables."""
    bridge, task_id, lock = bridge_with_lock

    # Make task active
    bridge.state_machine.initialize_state(task_id, TaskState.QUEUED)
    bridge.state_machine.transition(task_id, TaskState.CLAIMED)
    bridge.state_machine.transition(task_id, TaskState.IN_PROGRESS)

    with patch("village.probes.tmux.create_window") as mock_create:
        mock_create.return_value = True

        result = await bridge.terminal_create(
            {
                "sessionId": task_id,
                "command": "echo",
                "env": [{"name": "TEST", "value": "value"}],
            }
        )

        assert "terminalId" in result


@pytest.mark.asyncio
async def test_bridge_terminal_create_failure(bridge_with_lock: tuple):
    """Test terminal creation failure."""
    bridge, task_id, lock = bridge_with_lock

    # Make task active
    bridge.state_machine.initialize_state(task_id, TaskState.QUEUED)
    bridge.state_machine.transition(task_id, TaskState.CLAIMED)
    bridge.state_machine.transition(task_id, TaskState.IN_PROGRESS)

    with patch("village.probes.tmux.create_window") as mock_create:
        mock_create.return_value = False

        with pytest.raises(ACPBridgeError, match="Failed to create terminal"):
            await bridge.terminal_create({"sessionId": task_id, "command": "ls"})


@pytest.mark.asyncio
async def test_bridge_terminal_output_wrong_session(bridge: ACPBridge):
    """Test terminal output with wrong session ID."""
    # Create terminal for one session
    if not hasattr(bridge, "_terminals"):
        bridge._terminals = {}
    bridge._terminals["term-123"] = {"sessionId": "session-1", "windowName": "window-1"}

    # Try to access from different session
    with pytest.raises(ACPBridgeError, match="does not belong to session"):
        await bridge.terminal_output({"sessionId": "session-2", "terminalId": "term-123"})


@pytest.mark.asyncio
async def test_bridge_terminal_kill_wrong_session(bridge: ACPBridge):
    """Test terminal kill with wrong session ID."""
    if not hasattr(bridge, "_terminals"):
        bridge._terminals = {}
    bridge._terminals["term-123"] = {"sessionId": "session-1", "windowName": "window-1"}

    with pytest.raises(ACPBridgeError, match="does not belong to session"):
        await bridge.terminal_kill({"sessionId": "session-2", "terminalId": "term-123"})


@pytest.mark.asyncio
async def test_bridge_terminal_release(bridge: ACPBridge):
    """Test terminal release removes from tracking."""
    if not hasattr(bridge, "_terminals"):
        bridge._terminals = {}
    bridge._terminals["term-123"] = {"sessionId": "session-1", "windowName": "window-1"}

    result = await bridge.terminal_release({"sessionId": "session-1", "terminalId": "term-123"})

    assert result["released"]
    assert "term-123" not in bridge._terminals


# === Event Collection Tests ===


@pytest.mark.asyncio
async def test_bridge_collect_recent_events(bridge: ACPBridge):
    """Test collecting recent events for task."""
    task_id = "test-events"

    # Write some events
    for i in range(5):
        event = Event(
            ts=f"2026-03-05T10:0{i}:00Z",
            cmd="queue",
            task_id=task_id,
            result="ok",
        )
        append_event(event, bridge.config.village_dir)

    events = bridge._collect_recent_events(task_id)

    assert len(events) == 5
    assert all(e.task_id == task_id for e in events)


@pytest.mark.asyncio
async def test_bridge_collect_recent_events_with_limit(bridge: ACPBridge):
    """Test collecting recent events respects limit."""
    task_id = "test-events-limit"

    # Write more events than limit
    for i in range(150):
        event = Event(
            ts=f"2026-03-05T10:{i:02d}:00Z",
            cmd="queue",
            task_id=task_id,
            result="ok",
        )
        append_event(event, bridge.config.village_dir)

    events = bridge._collect_recent_events(task_id, limit=100)

    assert len(events) == 100


@pytest.mark.asyncio
async def test_bridge_collect_recent_events_no_events(bridge: ACPBridge):
    """Test collecting events when none exist."""
    events = bridge._collect_recent_events("nonexistent-task")

    assert events == []


# === Lock Helper Tests ===


@pytest.mark.asyncio
async def test_bridge_lock_to_dict(bridge_with_lock: tuple):
    """Test converting lock to dict."""
    bridge, task_id, lock = bridge_with_lock

    lock_dict = bridge._lock_to_dict(lock)

    assert lock_dict["taskId"] == task_id
    assert lock_dict["paneId"] == "%99"
    assert lock_dict["window"] == "test-window"
    assert lock_dict["agent"] == "test-agent"
    assert "claimedAt" in lock_dict


# === Helper Method Tests ===


@pytest.mark.asyncio
async def test_bridge_is_task_active_false_no_lock(bridge: ACPBridge):
    """Test _is_task_active returns False without lock."""
    is_active = bridge._is_task_active("nonexistent")
    assert is_active is False


@pytest.mark.asyncio
async def test_bridge_find_worktree_no_worktrees(bridge: ACPBridge):
    """Test _find_worktree_for_path with no worktrees."""
    info = bridge._find_worktree_for_path(Path("/tmp/test.txt"))
    assert info is None


@pytest.mark.asyncio
async def test_bridge_format_resume_result(bridge: ACPBridge):
    """Test _format_resume_result."""
    from village.resume import ResumeResult

    result = ResumeResult(
        task_id="test-123",
        agent="claude-code",
        worktree_path=Path("/tmp/worktree"),
        window_name="test-window",
        pane_id="%99",
        success=True,
    )

    formatted = bridge._format_resume_result(result)

    assert "test-123" in formatted
    assert "claude-code" in formatted
    assert "/tmp/worktree" in formatted


@pytest.mark.asyncio
async def test_bridge_format_resume_result_with_error(bridge: ACPBridge):
    """Test _format_resume_result with error."""
    from village.resume import ResumeResult

    result = ResumeResult(
        task_id="test-456",
        agent="claude-code",
        worktree_path=Path("/tmp/worktree"),
        window_name="test-window",
        pane_id="%99",
        success=False,
        error="Task failed",
    )

    formatted = bridge._format_resume_result(result)

    assert "Error: Task failed" in formatted


# === State Machine Integration ===


@pytest.mark.asyncio
async def test_bridge_session_state_persistence(bridge: ACPBridge):
    """Test session state persists across operations."""
    session_id = "test-persist"

    # Create session
    await bridge.session_new({"sessionId": session_id})

    # Verify state
    state = bridge.state_machine.get_state(session_id)
    assert state == TaskState.QUEUED

    # Load session
    await bridge.session_load({"sessionId": session_id})

    # Verify state still there
    state = bridge.state_machine.get_state(session_id)
    assert state == TaskState.QUEUED


@pytest.mark.asyncio
async def test_bridge_multiple_sessions(bridge: ACPBridge):
    """Test managing multiple sessions."""
    sessions = [f"multi-{i}" for i in range(5)]

    # Create all sessions
    for session_id in sessions:
        await bridge.session_new({"sessionId": session_id})

    # Verify all exist
    for session_id in sessions:
        result = await bridge.session_load({"sessionId": session_id})
        assert result["sessionId"] == session_id


# === Notification Edge Cases ===


@pytest.mark.asyncio
async def test_bridge_event_to_notification_with_pane(bridge: ACPBridge):
    """Test event with pane field."""
    event = Event(
        ts="2026-03-05T10:00:00Z",
        cmd="queue",
        task_id="test-pane",
        pane="%12",
        result="ok",
    )

    notification = bridge._event_to_notification(event)

    assert notification["params"]["update"]["pane"] == "%12"


@pytest.mark.asyncio
async def test_bridge_event_to_notification_without_task_id(bridge: ACPBridge):
    """Test event without task_id."""
    event = Event(
        ts="2026-03-05T10:00:00Z",
        cmd="queue",
        task_id=None,
        result="ok",
    )

    notification = bridge._event_to_notification(event)

    assert notification["params"]["sessionId"] == ""


@pytest.mark.asyncio
async def test_bridge_event_to_notification_all_file_events(bridge: ACPBridge):
    """Test all file event types."""
    for cmd in ["file_modified", "file_created", "file_deleted"]:
        event = Event(
            ts="2026-03-05T10:00:00Z",
            cmd=cmd,
            task_id="test-file",
        )

        notification = bridge._event_to_notification(event)

        assert notification["params"]["update"]["type"] == "file_change"


@pytest.mark.asyncio
async def test_bridge_event_to_notification_all_conflict_events(bridge: ACPBridge):
    """Test all conflict event types."""
    for cmd in ["conflict_detected", "merge_conflict"]:
        event = Event(
            ts="2026-03-05T10:00:00Z",
            cmd=cmd,
            task_id="test-conflict",
            error="Conflict",
        )

        notification = bridge._event_to_notification(event)

        assert notification["params"]["update"]["type"] == "conflict"


@pytest.mark.asyncio
async def test_bridge_event_to_notification_all_lifecycle_events(bridge: ACPBridge):
    """Test all lifecycle event types."""
    for cmd in ["queue", "resume", "cleanup", "claim", "release"]:
        event = Event(
            ts="2026-03-05T10:00:00Z",
            cmd=cmd,
            task_id="test-lifecycle",
            result="ok",
        )

        notification = bridge._event_to_notification(event)

        assert notification["params"]["update"]["type"] == "lifecycle"
