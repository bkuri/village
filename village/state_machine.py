"""Task state machine for lifecycle management."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from village.config import Config, get_config
from village.event_log import Event

logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    """Task lifecycle states."""

    QUEUED = "queued"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TransitionResult:
    """Result of a state transition."""

    success: bool
    current_state: Optional[TaskState]
    message: str


@dataclass
class StateTransition:
    """Single state transition in history."""

    ts: str
    from_state: Optional[TaskState]
    to_state: TaskState
    context: dict[str, object]


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, task_id: str, from_state: str, to_state: str) -> None:
        self.task_id = task_id
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid state transition for task {task_id}: {from_state} -> {to_state}")


class StateNotInitializedError(Exception):
    """Raised when attempting to transition a task with no initial state."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task {task_id} has no initial state")


class TaskStateMachine:
    """Manages task lifecycle states with persistence and logging."""

    VALID_TRANSITIONS: dict[TaskState, set[TaskState]] = {
        TaskState.QUEUED: {TaskState.CLAIMED},
        TaskState.CLAIMED: {TaskState.IN_PROGRESS, TaskState.FAILED},
        TaskState.IN_PROGRESS: {TaskState.PAUSED, TaskState.COMPLETED, TaskState.FAILED},
        TaskState.PAUSED: {TaskState.IN_PROGRESS, TaskState.FAILED},
        TaskState.COMPLETED: set(),
        TaskState.FAILED: set(),
    }

    def __init__(self, config: Optional[Config] = None) -> None:
        """Initialize state machine.

        Args:
            config: Village config (uses default if not provided)
        """
        self._config = config or get_config()

    def _get_lock_path(self, task_id: str) -> Path:
        """Get lock file path for task.

        Args:
            task_id: Task identifier

        Returns:
            Path to lock file
        """
        return self._config.locks_dir / f"{task_id}.lock"

    def _read_state_from_lock(self, task_id: str) -> Optional[TaskState]:
        """Read current state from lock file.

        Args:
            task_id: Task identifier

        Returns:
            Current TaskState or None if not found
        """
        lock_path = self._get_lock_path(task_id)

        if not lock_path.exists():
            return None

        try:
            content = lock_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.startswith("state="):
                    state_str = line.split("=", 1)[1].strip()
                    try:
                        return TaskState(state_str)
                    except ValueError:
                        logger.warning(f"Invalid state in lock {task_id}: {state_str}")
                        return None
        except (IOError, OSError) as e:
            logger.error(f"Failed to read lock file {lock_path}: {e}")
            return None

        return None

    def _write_state_to_lock(self, task_id: str, state: TaskState) -> None:
        """Write state to lock file (append mode).

        Args:
            task_id: Task identifier
            state: New state to write
        """
        lock_path = self._get_lock_path(task_id)

        try:
            if lock_path.exists():
                content = lock_path.read_text(encoding="utf-8")
                lines = content.splitlines()

                new_lines = []
                state_updated = False
                for line in lines:
                    if line.startswith("state="):
                        new_lines.append(f"state={state.value}")
                        state_updated = True
                    else:
                        new_lines.append(line)

                if not state_updated:
                    new_lines.append(f"state={state.value}")

                new_content = "\n".join(new_lines) + "\n"
            else:
                new_content = f"state={state.value}\n"

            temp_path = lock_path.with_suffix(".tmp")
            temp_path.write_text(new_content, encoding="utf-8")
            temp_path.replace(lock_path)
            logger.debug(f"Wrote state to lock {task_id}: {state.value}")
        except (IOError, OSError) as e:
            logger.error(f"Failed to write state to lock {lock_path}: {e}")
            raise

    def _read_state_history(self, task_id: str) -> list[StateTransition]:
        """Read state transition history from lock file.

        Args:
            task_id: Task identifier

        Returns:
            List of StateTransition objects
        """
        lock_path = self._get_lock_path(task_id)

        if not lock_path.exists():
            return []

        try:
            content = lock_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.startswith("state_history="):
                    history_json = line.split("=", 1)[1].strip()
                    if not history_json:
                        return []
                    try:
                        history_data = json.loads(history_json)
                        return [
                            StateTransition(
                                ts=entry["ts"],
                                from_state=TaskState(entry["from_state"])
                                if entry.get("from_state")
                                else None,
                                to_state=TaskState(entry["to_state"]),
                                context=entry.get("context", {}),
                            )
                            for entry in history_data
                        ]
                    except (json.JSONDecodeError, ValueError, KeyError) as e:
                        logger.warning(f"Invalid state history in lock {task_id}: {e}")
                        return []
        except (IOError, OSError) as e:
            logger.error(f"Failed to read lock file {lock_path}: {e}")
            return []

        return []

    def _write_state_history(
        self,
        task_id: str,
        history: list[StateTransition],
    ) -> None:
        """Write state transition history to lock file.

        Args:
            task_id: Task identifier
            history: Complete history to write
        """
        lock_path = self._get_lock_path(task_id)

        try:
            history_json = json.dumps(
                [
                    {
                        "ts": t.ts,
                        "from_state": t.from_state.value if t.from_state else None,
                        "to_state": t.to_state.value,
                        "context": t.context,
                    }
                    for t in history
                ]
            )

            if lock_path.exists():
                content = lock_path.read_text(encoding="utf-8")
                lines = content.splitlines()

                new_lines = []
                history_updated = False
                for line in lines:
                    if line.startswith("state_history="):
                        new_lines.append(f"state_history={history_json}")
                        history_updated = True
                    else:
                        new_lines.append(line)

                if not history_updated:
                    new_lines.append(f"state_history={history_json}")

                new_content = "\n".join(new_lines) + "\n"
            else:
                new_content = f"state_history={history_json}\n"

            temp_path = lock_path.with_suffix(".tmp")
            temp_path.write_text(new_content, encoding="utf-8")
            temp_path.replace(lock_path)
            logger.debug(f"Wrote state history to lock {task_id}: {len(history)} entries")
        except (IOError, OSError) as e:
            logger.error(f"Failed to write state history to lock {lock_path}: {e}")
            raise

    def _log_transition_event(
        self,
        task_id: str,
        from_state: Optional[TaskState],
        to_state: TaskState,
        context: dict[str, object],
    ) -> None:
        """Log state transition to event log.

        Args:
            task_id: Task identifier
            from_state: Previous state (None for initial state)
            to_state: New state
            context: Transition context
        """
        event = Event(
            ts=datetime.now(timezone.utc).isoformat(),
            cmd="state_transition",
            task_id=task_id,
            result=None,
            error=None,
        )

        try:
            event_json = json.dumps(
                {
                    "ts": event.ts,
                    "cmd": event.cmd,
                    "task_id": event.task_id,
                    "result": event.result,
                    "error": event.error,
                    "from_state": from_state.value if from_state else None,
                    "to_state": to_state.value,
                    "context": context,
                },
                sort_keys=True,
            )

            event_log_path = self._config.village_dir / "events.log"
            with open(event_log_path, "a", encoding="utf-8") as f:
                f.write(event_json + "\n")
                f.flush()

            logger.debug(f"Logged transition: {task_id} {from_state} -> {to_state}")
        except IOError as e:
            logger.error(f"Failed to log transition event: {e}")

    def can_transition(self, from_state: TaskState, to_state: TaskState) -> bool:
        """Check if a state transition is valid.

        Args:
            from_state: Current state
            to_state: Desired next state

        Returns:
            True if transition is valid, False otherwise
        """
        valid_targets = self.VALID_TRANSITIONS.get(from_state, set())
        return to_state in valid_targets

    def get_state(self, task_id: str) -> Optional[TaskState]:
        """Get current state for a task.

        Args:
            task_id: Task identifier

        Returns:
            Current TaskState or None if task has no state
        """
        return self._read_state_from_lock(task_id)

    def get_state_history(self, task_id: str) -> list[StateTransition]:
        """Get state transition history for a task.

        Args:
            task_id: Task identifier

        Returns:
            List of StateTransition objects (empty if no history)
        """
        return self._read_state_history(task_id)

    def transition(
        self,
        task_id: str,
        new_state: TaskState,
        context: dict[str, object] | None = None,
    ) -> TransitionResult:
        """Transition task to new state.

        Args:
            task_id: Task identifier
            new_state: Target state
            context: Optional context data (e.g., error message, pane ID)

        Returns:
            TransitionResult with success status and message
        """
        context = context or {}
        current_state = self._read_state_from_lock(task_id)

        if current_state is None:
            return TransitionResult(
                success=False,
                current_state=None,
                message=f"Task {task_id} has no initial state",
            )

        if not self.can_transition(current_state, new_state):
            valid_targets = self.VALID_TRANSITIONS.get(current_state, set())
            valid_str = ", ".join(s.value for s in sorted(valid_targets, key=lambda x: x.value))
            message = (
                f"Invalid transition for task {task_id}: "
                f"{current_state.value} -> {new_state.value}. "
                f"Valid targets: {valid_str}"
            )
            logger.warning(message)
            return TransitionResult(
                success=False,
                current_state=current_state,
                message=message,
            )

        transition = StateTransition(
            ts=datetime.now(timezone.utc).isoformat(),
            from_state=current_state,
            to_state=new_state,
            context=context,
        )

        history = self._read_state_history(task_id)
        history.append(transition)

        try:
            self._write_state_to_lock(task_id, new_state)
            self._write_state_history(task_id, history)
            self._log_transition_event(task_id, current_state, new_state, context)

            logger.info(f"Task {task_id} transitioned: {current_state.value} -> {new_state.value}")
            return TransitionResult(
                success=True,
                current_state=new_state,
                message=f"Transitioned {task_id} to {new_state.value}",
            )
        except (IOError, OSError) as e:
            message = f"Failed to persist state transition for {task_id}: {e}"
            logger.error(message)
            return TransitionResult(
                success=False,
                current_state=current_state,
                message=message,
            )

    def initialize_state(
        self,
        task_id: str,
        initial_state: TaskState,
        context: dict[str, object] | None = None,
    ) -> TransitionResult:
        """Initialize state for a new task.

        Args:
            task_id: Task identifier
            initial_state: Starting state (typically QUEUED)
            context: Optional context data

        Returns:
            TransitionResult with success status and message
        """
        context = context or {}
        current_state = self._read_state_from_lock(task_id)

        if current_state is not None:
            return TransitionResult(
                success=False,
                current_state=current_state,
                message=f"Task {task_id} already has state: {current_state.value}",
            )

        transition = StateTransition(
            ts=datetime.now(timezone.utc).isoformat(),
            from_state=None,
            to_state=initial_state,
            context=context,
        )

        try:
            self._write_state_to_lock(task_id, initial_state)
            self._write_state_history(task_id, [transition])
            self._log_transition_event(task_id, None, initial_state, context)

            logger.info(f"Task {task_id} initialized with state: {initial_state.value}")
            return TransitionResult(
                success=True,
                current_state=initial_state,
                message=f"Initialized {task_id} with state {initial_state.value}",
            )
        except (IOError, OSError) as e:
            message = f"Failed to initialize state for {task_id}: {e}"
            logger.error(message)
            return TransitionResult(
                success=False,
                current_state=None,
                message=message,
            )
