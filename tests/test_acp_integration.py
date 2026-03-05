"""Integration tests for ACP bridge operations.

End-to-end tests with real bridge operations, filesystem operations,
and session lifecycle management.
"""

import asyncio
import subprocess
from pathlib import Path

import pytest

from village.acp.bridge import ACPBridge, ACPBridgeError
from village.config import Config
from village.event_log import Event, append_event
from village.state_machine import TaskState
from village.locks import write_lock, Lock
from tests.fixtures.acp_fixtures import (
    create_test_file,
    create_test_worktree,
    ACPSessionBuilder,
    ACPTerminalBuilder,
)
from datetime import datetime, timezone


def _create_test_lock(task_id: str, bridge: ACPBridge) -> Lock:
    """Helper to create a test lock."""
    from datetime import datetime, timezone

    lock = Lock(
        task_id=task_id,
        pane_id="%99",
        window="test-window",
        agent="test-agent",
        claimed_at=datetime.now(timezone.utc),
    )
    write_lock(lock)
    return lock


@pytest.fixture
def bridge_with_worktree(acp_config: Config):
    """Create bridge with worktree setup."""
    bridge = ACPBridge(acp_config)

    task_id = "test-integration-1"
    worktree_path = create_test_worktree(
        task_id,
        acp_config,
        files={
            "src/main.py": "print('hello')",
            "README.md": "# Test Project",
            "config.json": '{"key": "value"}',
        },
    )

    return bridge, task_id, worktree_path


@pytest.mark.asyncio
@pytest.mark.integration
class TestSessionLifecycle:
    """Test complete session lifecycle."""

    async def test_full_session_lifecycle(self, bridge: ACPBridge):
        """Test new → load → prompt → cancel lifecycle."""
        session_id = "lifecycle-test-1"

        # 1. Create new session
        result = await bridge.session_new({"sessionId": session_id})
        assert result["sessionId"] == session_id
        assert result["state"] == "queued"

        # 2. Load session
        result = await bridge.session_load({"sessionId": session_id})
        assert result["sessionId"] == session_id
        assert result["state"] == "queued"

        # 3. Cancel session (from QUEUED state)
        result = await bridge.session_cancel({"sessionId": session_id})
        assert result["sessionId"] == session_id
        assert result["state"] in ("failed", "cancelled")

    async def test_session_new_duplicate_fails(self, bridge: ACPBridge):
        """Test creating duplicate session fails."""
        session_id = "duplicate-test-1"

        await bridge.session_new({"sessionId": session_id})

        with pytest.raises(ACPBridgeError, match="already initialized|Failed to create"):
            await bridge.session_new({"sessionId": session_id})

    async def test_session_load_nonexistent_fails(self, bridge: ACPBridge):
        """Test loading non-existent session fails."""
        with pytest.raises(ACPBridgeError, match="Task not found"):
            await bridge.session_load({"sessionId": "nonexistent-session"})

    async def test_session_cancel_nonexistent_fails(self, bridge: ACPBridge):
        """Test cancelling non-existent session fails."""
        with pytest.raises(ACPBridgeError, match="Task not found"):
            await bridge.session_cancel({"sessionId": "nonexistent-session"})

    async def test_session_state_transitions_queued_to_in_progress(self, bridge: ACPBridge):
        """Test session can transition from QUEUED to IN_PROGRESS."""
        session_id = "transition-test-1"

        # Create in QUEUED state
        await bridge.session_new({"sessionId": session_id})

        # Manually transition to IN_PROGRESS (simulating prompt start)
        result = bridge.state_machine.transition(session_id, TaskState.IN_PROGRESS)
        assert result.success

        # Verify state
        state = bridge.state_machine.get_state(session_id)
        assert state == TaskState.IN_PROGRESS

    async def test_session_state_transitions_in_progress_to_paused(self, bridge: ACPBridge):
        """Test session can transition from IN_PROGRESS to PAUSED."""
        session_id = "transition-test-2"

        # Create and transition to IN_PROGRESS
        await bridge.session_new({"sessionId": session_id})
        bridge.state_machine.transition(session_id, TaskState.CLAIMED)
        bridge.state_machine.transition(session_id, TaskState.IN_PROGRESS)

        # Pause via cancel
        result = await bridge.session_cancel({"sessionId": session_id})
        assert result["state"] == "paused"

    async def test_session_state_transitions_to_completed(self, bridge: ACPBridge):
        """Test session can transition to COMPLETED."""
        session_id = "transition-test-3"

        # Create and transition through states
        await bridge.session_new({"sessionId": session_id})
        bridge.state_machine.transition(session_id, TaskState.CLAIMED)
        bridge.state_machine.transition(session_id, TaskState.IN_PROGRESS)
        result = bridge.state_machine.transition(session_id, TaskState.COMPLETED)

        assert result.success
        state = bridge.state_machine.get_state(session_id)
        assert state == TaskState.COMPLETED


@pytest.mark.asyncio
@pytest.mark.integration
class TestFileSystemOperations:
    """Test file system operations with real worktrees."""

    async def test_fs_read_file_in_worktree(self, bridge_with_worktree: tuple[ACPBridge, str, Path]):
        """Test reading file from worktree."""
        bridge, task_id, worktree_path = bridge_with_worktree

        # Create lock for task (makes it "active")
        lock = Lock(
            task_id=task_id,
            pane_id="%99",
            window="test-window",
            agent="test-agent",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(lock)

        # Read file from worktree
        file_path = worktree_path / "src" / "main.py"
        result = await bridge.fs_read_text_file({"path": str(file_path)})

        assert result["content"] == "print('hello')"
        assert result["path"] == str(file_path)

    async def test_fs_read_file_not_found(self, bridge_with_worktree: tuple[ACPBridge, str, Path]):
        """Test reading non-existent file fails."""
        bridge, task_id, worktree_path = bridge_with_worktree

        # Create lock
        lock = Lock(
            task_id=task_id,
            pane_id="%99",
            window="test-window",
            agent="test-agent",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(lock)

        # Try to read non-existent file
        file_path = worktree_path / "nonexistent.py"
        with pytest.raises(ACPBridgeError, match="File not found"):
            await bridge.fs_read_text_file({"path": str(file_path)})

    async def test_fs_read_file_outside_worktree(self, bridge: ACPBridge):
        """Test reading file outside worktree fails."""
        with pytest.raises(ACPBridgeError, match="not in Village worktree"):
            await bridge.fs_read_text_file({"path": "/etc/passwd"})

    async def test_fs_write_file_in_worktree(self, bridge_with_worktree: tuple[ACPBridge, str, Path]):
        """Test writing file to worktree."""
        bridge, task_id, worktree_path = bridge_with_worktree

        # Create lock
        lock = Lock(
            task_id=task_id,
            pane_id="%99",
            window="test-window",
            agent="test-agent",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(lock)

        # Write file
        file_path = worktree_path / "src" / "new_file.py"
        result = await bridge.fs_write_text_file({"path": str(file_path), "content": "# New file\nprint('new')"})

        assert result["success"]
        assert file_path.exists()
        assert file_path.read_text() == "# New file\nprint('new')"

    async def test_fs_write_file_atomic(self, bridge_with_worktree: tuple[ACPBridge, str, Path]):
        """Test file write is atomic (no partial writes)."""
        bridge, task_id, worktree_path = bridge_with_worktree

        # Create lock
        lock = Lock(
            task_id=task_id,
            pane_id="%99",
            window="test-window",
            agent="test-agent",
            claimed_at=datetime.now(timezone.utc),
        )
        write_lock(lock)

        # Write file
        file_path = worktree_path / "atomic_test.txt"
        await bridge.fs_write_text_file({"path": str(file_path), "content": "atomic content"})

        # No .tmp file should exist
        assert not file_path.with_suffix(".tmp").exists()
        # Original file should exist with correct content
        assert file_path.read_text() == "atomic content"

    async def test_fs_write_file_outside_worktree(self, bridge: ACPBridge):
        """Test writing file outside worktree fails."""
        with pytest.raises(ACPBridgeError, match="not in Village worktree"):
            await bridge.fs_write_text_file({"path": "/tmp/test.txt", "content": "test"})

    async def test_fs_operations_require_active_task(self, bridge_with_worktree: tuple[ACPBridge, str, Path]):
        """Test file operations require active task."""
        bridge, task_id, worktree_path = bridge_with_worktree

        # Don't create lock - task not active

        file_path = worktree_path / "src" / "main.py"

        with pytest.raises(ACPBridgeError, match="Task not active"):
            await bridge.fs_read_text_file({"path": str(file_path)})

        with pytest.raises(ACPBridgeError, match="Task not active"):
            await bridge.fs_write_text_file({"path": str(file_path), "content": "test"})


@pytest.mark.asyncio
@pytest.mark.integration
class TestTerminalOperations:
    """Test terminal operations (requires tmux in CI)."""

    async def test_terminal_create_requires_session_id(self, bridge: ACPBridge):
        """Test terminal/create requires sessionId."""
        with pytest.raises(ACPBridgeError, match="sessionId required"):
            await bridge.terminal_create({"command": "ls"})

    async def test_terminal_create_requires_active_task(self, bridge: ACPBridge):
        """Test terminal/create requires active task."""
        # Create session but don't activate it
        await bridge.session_new({"sessionId": "term-test-1"})

        with pytest.raises(ACPBridgeError, match="Task not active"):
            await bridge.terminal_create({"sessionId": "term-test-1", "command": "ls"})

    async def test_terminal_output_requires_ids(self, bridge: ACPBridge):
        """Test terminal/output requires both IDs."""
        with pytest.raises(ACPBridgeError, match="sessionId required"):
            await bridge.terminal_output({"terminalId": "term-123"})

        with pytest.raises(ACPBridgeError, match="terminalId required"):
            await bridge.terminal_output({"sessionId": "session-123"})

    async def test_terminal_output_nonexistent_terminal(self, bridge: ACPBridge):
        """Test terminal/output fails for nonexistent terminal."""
        with pytest.raises(ACPBridgeError, match="Terminal not found"):
            await bridge.terminal_output({"sessionId": "session-123", "terminalId": "term-999"})

    async def test_terminal_kill_requires_ids(self, bridge: ACPBridge):
        """Test terminal/kill requires both IDs."""
        with pytest.raises(ACPBridgeError, match="sessionId required"):
            await bridge.terminal_kill({"terminalId": "term-123"})

        with pytest.raises(ACPBridgeError, match="terminalId required"):
            await bridge.terminal_kill({"sessionId": "session-123"})

    async def test_terminal_release_requires_ids(self, bridge: ACPBridge):
        """Test terminal/release requires both IDs."""
        with pytest.raises(ACPBridgeError, match="sessionId required"):
            await bridge.terminal_release({"terminalId": "term-123"})

        with pytest.raises(ACPBridgeError, match="terminalId required"):
            await bridge.terminal_release({"sessionId": "session-123"})

    async def test_terminal_wait_for_exit_requires_ids(self, bridge: ACPBridge):
        """Test terminal/wait_for_exit requires both IDs."""
        with pytest.raises(ACPBridgeError, match="sessionId required"):
            await bridge.terminal_wait_for_exit({"terminalId": "term-123"})

        with pytest.raises(ACPBridgeError, match="terminalId required"):
            await bridge.terminal_wait_for_exit({"sessionId": "session-123"})


@pytest.mark.asyncio
@pytest.mark.integration
class TestNotificationStreaming:
    """Test notification streaming."""

    async def test_stream_notifications_yields_events(self, bridge: ACPBridge, sample_acp_events: list[Event]):
        """Test stream_notifications yields notification events."""
        session_id = "test-stream-1"

        # Write events to event log
        for event in sample_acp_events:
            if event.task_id == "test-123":
                event.task_id = session_id
            append_event(event, bridge.config.village_dir)

        # Stream a few events
        notifications = []
        stream = bridge.stream_notifications(session_id, poll_interval=0.01)

        # Get first few notifications
        count = 0
        async for notification in stream:
            notifications.append(notification)
            count += 1
            if count >= 2:
                break

        assert len(notifications) >= 2
        for notif in notifications:
            assert notif["method"] == "session/update"
            assert notif["params"]["sessionId"] == session_id

    async def test_stream_notifications_filters_by_session(self, bridge: ACPBridge, sample_acp_events: list[Event]):
        """Test stream_notifications only yields events for session."""
        session_id = "test-stream-2"

        # Write events for different sessions
        for event in sample_acp_events:
            append_event(event, bridge.config.village_dir)

        # Stream should only get events for our session
        stream = bridge.stream_notifications(session_id, poll_interval=0.01)

        # Check first notification
        async for notification in stream:
            assert notification["params"]["sessionId"] == session_id
            break

    async def test_stream_notifications_continuous(self, bridge: ACPBridge, sample_acp_events: list[Event]):
        """Test stream_notifications continues streaming."""
        session_id = "test-stream-3"

        # Write initial event
        event = Event(
            ts="2026-03-05T10:00:00Z",
            cmd="queue",
            task_id=session_id,
            result="ok",
        )
        append_event(event, bridge.config.village_dir)

        # Start streaming
        stream = bridge.stream_notifications(session_id, poll_interval=0.01)

        # Get first event
        async for notification in stream:
            assert notification is not None
            break

        # Write another event
        event2 = Event(
            ts="2026-03-05T10:01:00Z",
            cmd="state_transition",
            task_id=session_id,
            result="ok",
        )
        append_event(event2, bridge.config.village_dir)

        # Should get second event
        async for notification in stream:
            assert notification is not None
            break


@pytest.mark.asyncio
@pytest.mark.integration
class TestEventToNotificationMapping:
    """Test event to notification mapping."""

    async def test_state_transition_maps_to_state_change(self, bridge: ACPBridge):
        """Test state_transition event maps to state_change notification."""
        from village.event_log import Event

        event = Event(
            ts="2026-03-05T10:00:00Z",
            cmd="state_transition",
            task_id="test-123",
            result="ok",
        )

        notification = bridge._event_to_notification(event)

        assert notification["params"]["update"]["type"] == "state_change"

    async def test_file_modified_maps_to_file_change(self, bridge: ACPBridge):
        """Test file_modified event maps to file_change notification."""
        from village.event_log import Event

        for cmd in ["file_modified", "file_created", "file_deleted"]:
            event = Event(
                ts="2026-03-05T10:00:00Z",
                cmd=cmd,
                task_id="test-123",
            )

            notification = bridge._event_to_notification(event)

            assert notification["params"]["update"]["type"] == "file_change"

    async def test_conflict_detected_maps_to_conflict(self, bridge: ACPBridge):
        """Test conflict_detected event maps to conflict notification."""
        from village.event_log import Event

        for cmd in ["conflict_detected", "merge_conflict"]:
            event = Event(
                ts="2026-03-05T10:00:00Z",
                cmd=cmd,
                task_id="test-123",
                error="Merge conflict in src/main.py",
            )

            notification = bridge._event_to_notification(event)

            assert notification["params"]["update"]["type"] == "conflict"

    async def test_lifecycle_events_map_correctly(self, bridge: ACPBridge):
        """Test lifecycle events (queue, resume, cleanup) map correctly."""
        from village.event_log import Event

        for cmd in ["queue", "resume", "cleanup", "claim", "release"]:
            event = Event(
                ts="2026-03-05T10:00:00Z",
                cmd=cmd,
                task_id="test-123",
                result="ok",
            )

            notification = bridge._event_to_notification(event)

            assert notification["params"]["update"]["type"] == "lifecycle"

    async def test_error_events_map_to_error(self, bridge: ACPBridge):
        """Test error events map to error notification type."""
        from village.event_log import Event

        event = Event(
            ts="2026-03-05T10:00:00Z",
            cmd="resume",
            task_id="test-123",
            result="error",
            error="Failed to execute task",
        )

        notification = bridge._event_to_notification(event)

        assert notification["params"]["update"]["type"] == "error"
        assert notification["params"]["update"]["error"] == "Failed to execute task"

    async def test_unknown_events_map_to_event(self, bridge: ACPBridge):
        """Test unknown event types map to generic event."""
        from village.event_log import Event

        event = Event(
            ts="2026-03-05T10:00:00Z",
            cmd="unknown_command",
            task_id="test-123",
        )

        notification = bridge._event_to_notification(event)

        assert notification["params"]["update"]["type"] == "event"


@pytest.mark.asyncio
@pytest.mark.integration
class TestBridgeErrorHandling:
    """Test bridge error handling."""

    async def test_session_new_missing_session_id(self, bridge: ACPBridge):
        """Test session/new requires sessionId."""
        with pytest.raises(ACPBridgeError, match="sessionId required"):
            await bridge.session_new({})

    async def test_session_load_missing_session_id(self, bridge: ACPBridge):
        """Test session/load requires sessionId."""
        with pytest.raises(ACPBridgeError, match="sessionId required"):
            await bridge.session_load({})

    async def test_session_prompt_missing_session_id(self, bridge: ACPBridge):
        """Test session/prompt requires sessionId."""
        with pytest.raises(ACPBridgeError, match="sessionId required"):
            await bridge.session_prompt({"message": "test"})

    async def test_session_cancel_missing_session_id(self, bridge: ACPBridge):
        """Test session/cancel requires sessionId."""
        with pytest.raises(ACPBridgeError, match="sessionId required"):
            await bridge.session_cancel({})

    async def test_session_prompt_nonexistent_session(self, bridge: ACPBridge):
        """Test session/prompt fails for non-existent session."""
        with pytest.raises(ACPBridgeError, match="Task not found"):
            await bridge.session_prompt({"sessionId": "nonexistent", "message": "test"})

    async def test_session_prompt_invalid_state(self, bridge: ACPBridge):
        """Test session/prompt fails for invalid state."""
        session_id = "invalid-state-test"

        # Create session in COMPLETED state
        await bridge.session_new({"sessionId": session_id})
        bridge.state_machine.transition(session_id, TaskState.CLAIMED)
        bridge.state_machine.transition(session_id, TaskState.IN_PROGRESS)
        bridge.state_machine.transition(session_id, TaskState.COMPLETED)

        # Try to prompt - should fail
        with pytest.raises(ACPBridgeError, match="Cannot start task"):
            await bridge.session_prompt({"sessionId": session_id, "message": "test"})


@pytest.mark.asyncio
@pytest.mark.integration
class TestBridgeHelperMethods:
    """Test bridge helper methods."""

    async def test_get_lock_returns_none_for_nonexistent(self, bridge: ACPBridge):
        """Test _get_lock returns None for non-existent task."""
        lock = bridge._get_lock("nonexistent-task")
        assert lock is None

    async def test_find_worktree_for_path_finds_existing(self, bridge_with_worktree: tuple[ACPBridge, str, Path]):
        """Test _find_worktree_for_path finds worktree."""
        bridge, task_id, worktree_path = bridge_with_worktree

        file_path = worktree_path / "src" / "main.py"
        info = bridge._find_worktree_for_path(file_path)

        assert info is not None

    async def test_find_worktree_for_path_returns_none_outside(self, bridge: ACPBridge):
        """Test _find_worktree_for_path returns None for path outside worktrees."""
        info = bridge._find_worktree_for_path(Path("/tmp/test.txt"))
        assert info is None

    async def test_is_task_active_returns_false_without_lock(self, bridge: ACPBridge):
        """Test _is_task_active returns False without lock."""
        is_active = bridge._is_task_active("nonexistent-task")
        assert is_active is False


@pytest.mark.asyncio
@pytest.mark.slow
class TestPerformance:
    """Performance benchmarks for key operations."""

    async def test_session_new_performance(self, bridge: ACPBridge):
        """Benchmark session_new operation."""
        import time

        iterations = 100
        start = time.time()

        for i in range(iterations):
            await bridge.session_new({"sessionId": f"perf-test-{i}"})

        elapsed = time.time() - start
        avg_time = elapsed / iterations

        # Should be under 10ms per operation
        assert avg_time < 0.01, f"session_new too slow: {avg_time:.3f}s avg"

    async def test_session_load_performance(self, bridge: ACPBridge):
        """Benchmark session_load operation."""
        import time

        # Create sessions
        for i in range(100):
            await bridge.session_new({"sessionId": f"perf-load-{i}"})

        iterations = 100
        start = time.time()

        for i in range(iterations):
            await bridge.session_load({"sessionId": f"perf-load-{i}"})

        elapsed = time.time() - start
        avg_time = elapsed / iterations

        # Should be under 5ms per operation
        assert avg_time < 0.005, f"session_load too slow: {avg_time:.3f}s avg"

    async def test_event_to_notification_performance(self, bridge: ACPBridge):
        """Benchmark event_to_notification operation."""
        import time

        from village.event_log import Event

        events = [
            Event(
                ts=f"2026-03-05T10:{i:02d}:00Z",
                cmd="state_transition",
                task_id=f"perf-event-{i}",
                result="ok",
            )
            for i in range(1000)
        ]

        start = time.time()

        for event in events:
            bridge._event_to_notification(event)

        elapsed = time.time() - start
        avg_time = elapsed / 1000

        # Should be under 0.1ms per operation
        assert avg_time < 0.0001, f"event_to_notification too slow: {avg_time:.6f}s avg"

    async def test_stream_notifications_performance(self, bridge: ACPBridge):
        """Benchmark stream_notifications operation."""
        import time

        from village.event_log import Event, append_event

        session_id = "perf-stream-1"

        # Create events
        for i in range(100):
            event = Event(
                ts=f"2026-03-05T10:{i:02d}:00Z",
                cmd="state_transition",
                task_id=session_id,
                result="ok",
            )
            append_event(event, bridge.config.village_dir)

        # Measure streaming
        start = time.time()

        count = 0
        stream = bridge.stream_notifications(session_id, poll_interval=0.001)
        async for _ in stream:
            count += 1
            if count >= 100:
                break

        elapsed = time.time() - start

        # Should process 100 events in under 1 second
        assert elapsed < 1.0, f"stream_notifications too slow: {elapsed:.3f}s for 100 events"


@pytest.fixture
def bridge(acp_config: Config):
    """Create ACP bridge with temp config."""
    return ACPBridge(acp_config)


@pytest.fixture
def sample_acp_events():
    """Create sample ACP events for testing."""
    from village.event_log import Event

    return [
        Event(
            ts="2026-03-05T10:00:00Z",
            cmd="state_transition",
            task_id="test-123",
            result="ok",
        ),
        Event(
            ts="2026-03-05T10:01:00Z",
            cmd="file_modified",
            task_id="test-123",
        ),
        Event(
            ts="2026-03-05T10:02:00Z",
            cmd="conflict_detected",
            task_id="test-123",
            error="Merge conflict in src/main.py",
        ),
        Event(
            ts="2026-03-05T10:03:00Z",
            cmd="queue",
            task_id="test-456",
            result="ok",
        ),
        Event(
            ts="2026-03-05T10:04:00Z",
            cmd="resume",
            task_id="test-456",
            result="error",
            error="Task execution failed",
        ),
    ]
