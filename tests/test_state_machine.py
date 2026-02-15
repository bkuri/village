"""Test state machine functionality."""

import subprocess
from pathlib import Path

from village.config import Config
from village.state_machine import (
    InvalidStateTransitionError,
    StateNotInitializedError,
    StateTransition,
    TaskState,
    TaskStateMachine,
    TransitionResult,
)


def test_task_state_enum():
    """Test TaskState enum has all required states."""
    assert TaskState.QUEUED.value == "queued"
    assert TaskState.CLAIMED.value == "claimed"
    assert TaskState.IN_PROGRESS.value == "in_progress"
    assert TaskState.PAUSED.value == "paused"
    assert TaskState.COMPLETED.value == "completed"
    assert TaskState.FAILED.value == "failed"


def test_can_transition_valid():
    """Test valid transitions are accepted."""
    machine = TaskStateMachine()

    assert machine.can_transition(TaskState.QUEUED, TaskState.CLAIMED)
    assert machine.can_transition(TaskState.CLAIMED, TaskState.IN_PROGRESS)
    assert machine.can_transition(TaskState.CLAIMED, TaskState.FAILED)
    assert machine.can_transition(TaskState.IN_PROGRESS, TaskState.PAUSED)
    assert machine.can_transition(TaskState.IN_PROGRESS, TaskState.COMPLETED)
    assert machine.can_transition(TaskState.IN_PROGRESS, TaskState.FAILED)
    assert machine.can_transition(TaskState.PAUSED, TaskState.IN_PROGRESS)
    assert machine.can_transition(TaskState.PAUSED, TaskState.FAILED)


def test_can_transition_invalid():
    """Test invalid transitions are rejected."""
    machine = TaskStateMachine()

    assert not machine.can_transition(TaskState.QUEUED, TaskState.IN_PROGRESS)
    assert not machine.can_transition(TaskState.QUEUED, TaskState.COMPLETED)
    assert not machine.can_transition(TaskState.COMPLETED, TaskState.IN_PROGRESS)
    assert not machine.can_transition(TaskState.FAILED, TaskState.IN_PROGRESS)
    assert not machine.can_transition(TaskState.FAILED, TaskState.COMPLETED)


def test_get_state_no_lock(tmp_path: Path):
    """Test get_state returns None when lock doesn't exist."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    state = machine.get_state("bd-a3f8")

    assert state is None


def test_initialize_state(tmp_path: Path):
    """Test initializing state for a new task."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    result = machine.initialize_state("bd-a3f8", TaskState.QUEUED)

    assert result.success is True
    assert result.current_state == TaskState.QUEUED
    assert "initialized" in result.message.lower()

    state = machine.get_state("bd-a3f8")
    assert state == TaskState.QUEUED


def test_initialize_state_already_initialized(tmp_path: Path):
    """Test initializing an already initialized task fails."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)
    result = machine.initialize_state("bd-a3f8", TaskState.CLAIMED)

    assert result.success is False
    assert "already has state" in result.message.lower()


def test_transition_queued_to_claimed(tmp_path: Path):
    """Test transition QUEUED -> CLAIMED."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)

    result = machine.transition("bd-a3f8", TaskState.CLAIMED, {"pane_id": "%12"})

    assert result.success is True
    assert result.current_state == TaskState.CLAIMED

    state = machine.get_state("bd-a3f8")
    assert state == TaskState.CLAIMED


def test_transition_claimed_to_in_progress(tmp_path: Path):
    """Test transition CLAIMED -> IN_PROGRESS."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)
    machine.transition("bd-a3f8", TaskState.CLAIMED)

    result = machine.transition("bd-a3f8", TaskState.IN_PROGRESS)

    assert result.success is True
    assert result.current_state == TaskState.IN_PROGRESS


def test_transition_in_progress_to_paused(tmp_path: Path):
    """Test transition IN_PROGRESS -> PAUSED."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)
    machine.transition("bd-a3f8", TaskState.CLAIMED)
    machine.transition("bd-a3f8", TaskState.IN_PROGRESS)

    result = machine.transition("bd-a3f8", TaskState.PAUSED)

    assert result.success is True
    assert result.current_state == TaskState.PAUSED


def test_transition_paused_to_in_progress(tmp_path: Path):
    """Test transition PAUSED -> IN_PROGRESS."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)
    machine.transition("bd-a3f8", TaskState.CLAIMED)
    machine.transition("bd-a3f8", TaskState.IN_PROGRESS)
    machine.transition("bd-a3f8", TaskState.PAUSED)

    result = machine.transition("bd-a3f8", TaskState.IN_PROGRESS)

    assert result.success is True
    assert result.current_state == TaskState.IN_PROGRESS


def test_transition_in_progress_to_completed(tmp_path: Path):
    """Test transition IN_PROGRESS -> COMPLETED."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)
    machine.transition("bd-a3f8", TaskState.CLAIMED)
    machine.transition("bd-a3f8", TaskState.IN_PROGRESS)

    result = machine.transition("bd-a3f8", TaskState.COMPLETED)

    assert result.success is True
    assert result.current_state == TaskState.COMPLETED


def test_transition_in_progress_to_failed(tmp_path: Path):
    """Test transition IN_PROGRESS -> FAILED."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)
    machine.transition("bd-a3f8", TaskState.CLAIMED)
    machine.transition("bd-a3f8", TaskState.IN_PROGRESS)

    result = machine.transition("bd-a3f8", TaskState.FAILED, {"error": "Task failed"})

    assert result.success is True
    assert result.current_state == TaskState.FAILED


def test_transition_paused_to_failed(tmp_path: Path):
    """Test transition PAUSED -> FAILED."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)
    machine.transition("bd-a3f8", TaskState.CLAIMED)
    machine.transition("bd-a3f8", TaskState.IN_PROGRESS)
    machine.transition("bd-a3f8", TaskState.PAUSED)

    result = machine.transition("bd-a3f8", TaskState.FAILED)

    assert result.success is True
    assert result.current_state == TaskState.FAILED


def test_transition_claimed_to_failed(tmp_path: Path):
    """Test transition CLAIMED -> FAILED (worktree setup failure)."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)
    machine.transition("bd-a3f8", TaskState.CLAIMED)

    result = machine.transition("bd-a3f8", TaskState.FAILED, {"error": "Worktree setup failed"})

    assert result.success is True
    assert result.current_state == TaskState.FAILED


def test_transition_invalid_no_state(tmp_path: Path):
    """Test transition fails when task has no initial state."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    result = machine.transition("bd-a3f8", TaskState.CLAIMED)

    assert result.success is False
    assert result.current_state is None
    assert "no initial state" in result.message.lower()


def test_transition_invalid_queued_to_in_progress(tmp_path: Path):
    """Test invalid transition QUEUED -> IN_PROGRESS fails."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)

    result = machine.transition("bd-a3f8", TaskState.IN_PROGRESS)

    assert result.success is False
    assert result.current_state == TaskState.QUEUED
    assert "Invalid transition" in result.message
    assert "claimed" in result.message.lower()


def test_transition_invalid_completed_to_in_progress(tmp_path: Path):
    """Test invalid transition COMPLETED -> IN_PROGRESS fails."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)
    machine.transition("bd-a3f8", TaskState.CLAIMED)
    machine.transition("bd-a3f8", TaskState.IN_PROGRESS)
    machine.transition("bd-a3f8", TaskState.COMPLETED)

    result = machine.transition("bd-a3f8", TaskState.IN_PROGRESS)

    assert result.success is False
    assert result.current_state == TaskState.COMPLETED
    assert "Invalid transition" in result.message


def test_get_state_history_empty(tmp_path: Path):
    """Test get_state_history returns empty list for non-existent task."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    history = machine.get_state_history("bd-a3f8")

    assert history == []


def test_get_state_history_initialized(tmp_path: Path):
    """Test get_state_history after initialization."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)

    history = machine.get_state_history("bd-a3f8")

    assert len(history) == 1
    assert history[0].from_state is None
    assert history[0].to_state == TaskState.QUEUED
    assert isinstance(history[0].ts, str)


def test_get_state_history_full_lifecycle(tmp_path: Path):
    """Test get_state_history after full task lifecycle."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)
    machine.transition("bd-a3f8", TaskState.CLAIMED, {"pane_id": "%12"})
    machine.transition("bd-a3f8", TaskState.IN_PROGRESS)
    machine.transition("bd-a3f8", TaskState.PAUSED)
    machine.transition("bd-a3f8", TaskState.IN_PROGRESS)
    machine.transition("bd-a3f8", TaskState.COMPLETED)

    history = machine.get_state_history("bd-a3f8")

    assert len(history) == 6
    assert history[0].from_state is None
    assert history[0].to_state == TaskState.QUEUED
    assert history[1].from_state == TaskState.QUEUED
    assert history[1].to_state == TaskState.CLAIMED
    assert history[1].context == {"pane_id": "%12"}  # type: ignore[assignment]
    assert history[5].to_state == TaskState.COMPLETED


def test_state_persistence_across_instances(tmp_path: Path):
    """Test state persists across TaskStateMachine instances."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine1 = TaskStateMachine(config)
    machine1.initialize_state("bd-a3f8", TaskState.QUEUED)
    machine1.transition("bd-a3f8", TaskState.CLAIMED)

    machine2 = TaskStateMachine(config)
    state = machine2.get_state("bd-a3f8")

    assert state == TaskState.CLAIMED


def test_state_history_persistence_across_instances(tmp_path: Path):
    """Test state history persists across TaskStateMachine instances."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine1 = TaskStateMachine(config)
    machine1.initialize_state("bd-a3f8", TaskState.QUEUED)
    machine1.transition("bd-a3f8", TaskState.CLAIMED)
    machine1.transition("bd-a3f8", TaskState.IN_PROGRESS)

    machine2 = TaskStateMachine(config)
    history = machine2.get_state_history("bd-a3f8")

    assert len(history) == 3
    assert history[2].to_state == TaskState.IN_PROGRESS


def test_invalid_state_transition_error():
    """Test InvalidStateTransitionError exception."""
    error = InvalidStateTransitionError("bd-a3f8", "queued", "completed")
    assert "bd-a3f8" in str(error)
    assert "queued -> completed" in str(error)


def test_state_not_initialized_error():
    """Test StateNotInitializedError exception."""
    error = StateNotInitializedError("bd-a3f8")
    assert "bd-a3f8" in str(error)
    assert "no initial state" in str(error)


def test_transition_with_context(tmp_path: Path):
    """Test transition with context data."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)

    context = {  # type: ignore[assignment]
        "pane_id": "%12",
        "window": "build-1-bd-a3f8",
        "agent": "build",
    }
    result = machine.transition("bd-a3f8", TaskState.CLAIMED, context)

    assert result.success is True

    history = machine.get_state_history("bd-a3f8")
    assert len(history) == 2
    assert history[1].context == context


def test_multiple_tasks(tmp_path: Path):
    """Test state machine handles multiple tasks independently."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)

    machine.initialize_state("bd-a3f8", TaskState.QUEUED)
    machine.initialize_state("bd-1234", TaskState.QUEUED)

    machine.transition("bd-a3f8", TaskState.CLAIMED)
    machine.transition("bd-1234", TaskState.CLAIMED)
    machine.transition("bd-1234", TaskState.FAILED)

    state1 = machine.get_state("bd-a3f8")
    state2 = machine.get_state("bd-1234")

    assert state1 == TaskState.CLAIMED
    assert state2 == TaskState.FAILED


def test_lock_file_format(tmp_path: Path):
    """Test lock file contains correct format."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)
    machine.transition("bd-a3f8", TaskState.CLAIMED, {"pane_id": "%12"})

    lock_path = config.locks_dir / "bd-a3f8.lock"
    content = lock_path.read_text(encoding="utf-8")

    assert "state=claimed" in content
    assert "state_history=" in content


def test_event_log_written(tmp_path: Path):
    """Test state transitions are logged to events.log."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)
    machine.transition("bd-a3f8", TaskState.CLAIMED)

    event_log_path = config.village_dir / "events.log"
    assert event_log_path.exists()

    content = event_log_path.read_text(encoding="utf-8")
    assert '"cmd": "state_transition"' in content
    assert '"task_id": "bd-a3f8"' in content
    assert '"from_state": "queued"' in content
    assert '"to_state": "claimed"' in content


def test_transition_result_dataclass():
    """Test TransitionResult dataclass."""
    result = TransitionResult(
        success=True,
        current_state=TaskState.IN_PROGRESS,
        message="Transition successful",
    )

    assert result.success is True
    assert result.current_state == TaskState.IN_PROGRESS
    assert result.message == "Transition successful"


def test_state_transition_dataclass():
    """Test StateTransition dataclass."""
    transition = StateTransition(
        ts="2026-01-26T10:00:00",
        from_state=TaskState.QUEUED,
        to_state=TaskState.CLAIMED,
        context={"pane_id": "%12"},
    )

    assert transition.ts == "2026-01-26T10:00:00"
    assert transition.from_state == TaskState.QUEUED
    assert transition.to_state == TaskState.CLAIMED
    assert transition.context == {"pane_id": "%12"}  # type: ignore[assignment]


def test_can_transition_from_terminal_states():
    """Test that terminal states have no valid transitions."""
    machine = TaskStateMachine()

    assert len(machine.VALID_TRANSITIONS[TaskState.COMPLETED]) == 0
    assert len(machine.VALID_TRANSITIONS[TaskState.FAILED]) == 0


def test_read_state_from_lock_corrupted_state(tmp_path: Path):
    """Test reading lock file with invalid state value."""
    from village.state_machine import TaskStateMachine

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    # Create lock file with invalid state
    lock_path = config.locks_dir / "bd-a3f8.lock"
    lock_path.write_text("state=invalid_state\n", encoding="utf-8")

    machine = TaskStateMachine(config)
    state = machine.get_state("bd-a3f8")

    # Should return None for corrupted state
    assert state is None


def test_write_state_no_existing_state_line(tmp_path: Path):
    """Test writing state when lock file has no state line."""
    from village.state_machine import TaskStateMachine

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    # Create lock file with other data but no state line
    lock_path = config.locks_dir / "bd-a3f8.lock"
    lock_path.write_text("pane=%12\nwindow=build\n", encoding="utf-8")

    machine = TaskStateMachine(config)
    result = machine.initialize_state("bd-a3f8", TaskState.QUEUED)

    assert result.success is True

    # Verify state line was appended
    content = lock_path.read_text(encoding="utf-8")
    assert "pane=%12" in content
    assert "state=queued" in content


def test_read_state_history_empty_json(tmp_path: Path):
    """Test reading lock file with empty state_history JSON."""
    from village.state_machine import TaskStateMachine

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    # Create lock file with empty state_history
    lock_path = config.locks_dir / "bd-a3f8.lock"
    lock_path.write_text("state=queued\nstate_history=\n", encoding="utf-8")

    machine = TaskStateMachine(config)
    history = machine.get_state_history("bd-a3f8")

    # Should return empty list for empty JSON
    assert history == []


def test_read_state_history_corrupted_json(tmp_path: Path):
    """Test reading lock file with invalid state_history JSON."""
    from village.state_machine import TaskStateMachine

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    # Create lock file with invalid JSON
    lock_path = config.locks_dir / "bd-a3f8.lock"
    lock_path.write_text("state=queued\nstate_history={invalid json}\n", encoding="utf-8")

    machine = TaskStateMachine(config)
    history = machine.get_state_history("bd-a3f8")

    # Should return empty list for corrupted JSON
    assert history == []


def test_write_state_history_no_existing_history_line(tmp_path: Path):
    """Test writing state history when lock file has no history line."""
    from village.state_machine import TaskStateMachine

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    # Create lock file with state but no history
    lock_path = config.locks_dir / "bd-a3f8.lock"
    lock_path.write_text("state=queued\n", encoding="utf-8")

    machine = TaskStateMachine(config)
    machine.transition("bd-a3f8", TaskState.CLAIMED)

    # Verify state_history line was appended
    content = lock_path.read_text(encoding="utf-8")
    assert "state_history=" in content


def test_read_state_from_lock_io_error(tmp_path: Path):
    """Test reading lock file with IOError."""
    from unittest.mock import patch

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    # Create lock file
    lock_path = config.locks_dir / "bd-a3f8.lock"
    lock_path.write_text("state=queued\n", encoding="utf-8")

    machine = TaskStateMachine(config)

    # Mock read_text to raise IOError
    with patch.object(Path, "read_text", side_effect=IOError("Permission denied")):
        state = machine.get_state("bd-a3f8")
        # Should return None on IOError
        assert state is None


def test_write_state_to_lock_io_error(tmp_path: Path):
    """Test writing state to lock file with IOError."""
    from unittest.mock import patch

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)

    # Mock write_text to raise IOError
    with patch.object(Path, "write_text", side_effect=IOError("Disk full")):
        result = machine.transition("bd-a3f8", TaskState.CLAIMED)
        # Should return failure on write error
        assert result.success is False
        assert "Failed to persist state transition" in result.message


def test_read_state_history_io_error(tmp_path: Path):
    """Test reading state history from lock file with IOError."""
    from unittest.mock import patch

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    # Create lock file
    lock_path = config.locks_dir / "bd-a3f8.lock"
    lock_path.write_text("state=queued\n", encoding="utf-8")

    machine = TaskStateMachine(config)

    # Mock read_text to raise IOError
    with patch.object(Path, "read_text", side_effect=IOError("Permission denied")):
        history = machine.get_state_history("bd-a3f8")
        # Should return empty list on IOError
        assert history == []


def test_write_state_history_io_error(tmp_path: Path):
    """Test writing state history to lock file with IOError."""
    from unittest.mock import patch

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)

    # Mock write_text to raise OSError
    with patch.object(Path, "write_text", side_effect=OSError("No space left")):
        result = machine.transition("bd-a3f8", TaskState.CLAIMED)
        # Should return failure on write error
        assert result.success is False
        assert "Failed to persist state transition" in result.message


def test_log_transition_event_io_error(tmp_path: Path):
    """Test logging transition event with IOError."""
    from unittest.mock import mock_open, patch

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)

    # Mock file open to raise IOError
    with patch("builtins.open", mock_open()) as mock_file:
        mock_file.side_effect = IOError("Cannot write to event log")

        # Transition should succeed despite logging error
        result = machine.initialize_state("bd-a3f8", TaskState.QUEUED)
        # Should still succeed even if event logging fails
        assert result.success is True


def test_transition_write_error(tmp_path: Path):
    """Test transition when write operations fail."""
    from unittest.mock import patch

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)
    machine.initialize_state("bd-a3f8", TaskState.QUEUED)

    # Mock replace to raise OSError
    with patch.object(Path, "replace", side_effect=OSError("No space left")):
        result = machine.transition("bd-a3f8", TaskState.CLAIMED)
        # Should return failure
        assert result.success is False
        assert "Failed to persist state transition" in result.message
        # State should not have changed
        state = machine.get_state("bd-a3f8")
        assert state == TaskState.QUEUED


def test_initialize_state_write_error(tmp_path: Path):
    """Test initialize_state when write operations fail."""
    from unittest.mock import patch

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()

    machine = TaskStateMachine(config)

    # Mock replace to raise OSError
    with patch.object(Path, "replace", side_effect=OSError("Disk full")):
        result = machine.initialize_state("bd-a3f8", TaskState.QUEUED)
        # Should return failure
        assert result.success is False
        assert "Failed to initialize state" in result.message
        # State should not have been initialized
        state = machine.get_state("bd-a3f8")
        assert state is None
