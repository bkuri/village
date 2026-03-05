"""Bridge ACP protocol to Village core operations.

This module provides the critical integration layer that:
- Maps ACP sessions to Village tasks
- Bridges ACP methods to Village operations (resume, queue, etc.)
- Converts Village events to ACP notifications
- Handles state transitions and error translation
"""

import logging
from pathlib import Path
from typing import Any

from village.config import Config, get_config
from village.event_log import Event, read_events
from village.locks import Lock, parse_lock
from village.resume import ResumeResult, execute_resume
from village.state_machine import TaskState, TaskStateMachine

logger = logging.getLogger(__name__)


class ACPBridgeError(Exception):
    """Bridge operation error."""

    pass


class ACPBridge:
    """Bridge ACP protocol to Village core operations.

    This is the integration layer that translates ACP concepts
    to Village concepts:

    ACP Session → Village Task
    ACP session/prompt → Village resume
    ACP fs/read → Village worktree access
    Village events → ACP session/update notifications
    """

    def __init__(self, config: Config | None = None):
        """Initialize ACP bridge.

        Args:
            config: Village config (uses default if not provided)
        """
        self.config = config or get_config()
        self.state_machine = TaskStateMachine(self.config)

    # === Session Lifecycle ===

    async def session_new(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ACP session/new.

        Creates Village task in QUEUED state.

        Args:
            params: ACP session/new parameters

        Returns:
            Session info with session_id

        Raises:
            ACPBridgeError: If sessionId not provided or creation fails
        """
        session_id = params.get("sessionId")
        if not session_id:
            raise ACPBridgeError("sessionId required")

        # Initialize Village task state
        result = self.state_machine.initialize_state(
            session_id,
            TaskState.QUEUED,
            context={"source": "acp", "params": params},
        )

        if not result.success:
            raise ACPBridgeError(f"Failed to create task: {result.message}")

        logger.info(f"Created ACP session: {session_id}")

        return {
            "sessionId": session_id,
            "state": "queued",
        }

    async def session_load(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ACP session/load.

        Loads existing Village task.

        Args:
            params: ACP session/load parameters

        Returns:
            Session info with current state

        Raises:
            ACPBridgeError: If sessionId not provided or task not found
        """
        session_id = params.get("sessionId")
        if not session_id:
            raise ACPBridgeError("sessionId required")

        # Check if task exists
        state = self.state_machine.get_state(session_id)
        if not state:
            raise ACPBridgeError(f"Task not found: {session_id}")

        # Get lock info if exists
        lock = self._get_lock(session_id)

        logger.info(f"Loaded ACP session: {session_id} (state={state.value})")

        return {
            "sessionId": session_id,
            "state": state.value,
            "lock": self._lock_to_dict(lock) if lock else None,
        }

    async def session_prompt(self, params: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Handle ACP session/prompt.

        Executes Village resume and collects events.

        Args:
            params: ACP session/prompt parameters

        Returns:
            Tuple of (response, notifications)

        Raises:
            ACPBridgeError: If sessionId not provided or execution fails
        """
        session_id = params.get("sessionId")
        message = params.get("message", "")
        agent = params.get("agent", self.config.default_agent)

        if not session_id:
            raise ACPBridgeError("sessionId required")

        # Check task exists and is in valid state
        state = self.state_machine.get_state(session_id)
        if not state:
            raise ACPBridgeError(f"Task not found: {session_id}")

        # Transition to IN_PROGRESS
        result = self.state_machine.transition(session_id, TaskState.IN_PROGRESS, context={"message": message})

        if not result.success:
            raise ACPBridgeError(f"Cannot start task: {result.message}")

        # Execute Village resume
        try:
            resume_result = execute_resume(
                task_id=session_id,
                agent=agent,
                config=self.config,
            )

            # Collect events for notifications
            events = self._collect_recent_events(session_id)
            notifications = [self._event_to_notification(e) for e in events]

            # Build response
            response = {
                "sessionId": session_id,
                "stopReason": "end_turn",
                "content": self._format_resume_result(resume_result),
            }

            logger.info(f"Completed ACP prompt for session {session_id}")

            return response, notifications

        except Exception as e:
            # Transition to FAILED
            self.state_machine.transition(session_id, TaskState.FAILED, context={"error": str(e)})
            raise ACPBridgeError(f"Task execution failed: {e}") from e

    async def session_cancel(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ACP session/cancel.

        Pauses Village task.

        Args:
            params: ACP session/cancel parameters

        Returns:
            Cancel confirmation

        Raises:
            ACPBridgeError: If sessionId not provided or pause fails
        """
        session_id = params.get("sessionId")
        if not session_id:
            raise ACPBridgeError("sessionId required")

        # Transition to PAUSED
        result = self.state_machine.transition(session_id, TaskState.PAUSED)

        if not result.success:
            raise ACPBridgeError(f"Cannot pause task: {result.message}")

        logger.info(f"Cancelled ACP session: {session_id}")

        return {"sessionId": session_id, "state": "paused"}

    async def session_set_mode(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ACP session/set_mode.

        Sets agent mode for session (build/test/frontend/etc).

        Args:
            params: ACP session/set_mode parameters
                - sessionId: Session ID
                - mode: Agent mode to set

        Returns:
            Mode confirmation

        Raises:
            ACPBridgeError: If sessionId not provided or mode invalid
        """
        session_id = params.get("sessionId")
        mode = params.get("mode", self.config.default_agent)

        if not session_id:
            raise ACPBridgeError("sessionId required")

        # Validate mode is a valid agent
        if mode not in self.config.agents:
            raise ACPBridgeError(f"Invalid mode: {mode}. Available: {list(self.config.agents.keys())}")

        # Check task exists
        state = self.state_machine.get_state(session_id)
        if not state:
            raise ACPBridgeError(f"Task not found: {session_id}")

        # Update task metadata with mode
        lock = self._get_lock(session_id)
        if lock:
            # Update lock with new agent mode
            lock_data = {
                "id": lock.task_id,
                "pane": lock.pane_id,
                "window": lock.window,
                "agent": mode,  # Update agent
                "claimed_at": lock.claimed_at.isoformat(),
            }

            # Write updated lock
            from village.locks import write_lock, Lock

            updated_lock = Lock(
                task_id=lock.task_id,
                pane_id=lock.pane_id,
                window=lock.window,
                agent=mode,
                claimed_at=lock.claimed_at,
            )
            write_lock(updated_lock)

        logger.info(f"Set mode {mode} for session {session_id}")

        return {"sessionId": session_id, "mode": mode}

    async def session_set_config_option(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ACP session/set_config_option.

        Sets runtime configuration option for session.

        Args:
            params: ACP session/set_config_option parameters
                - sessionId: Session ID
                - key: Configuration key
                - value: Configuration value

        Returns:
            Config confirmation

        Raises:
            ACPBridgeError: If sessionId not provided or config invalid
        """
        session_id = params.get("sessionId")
        key = params.get("key")
        value = params.get("value")

        if not session_id:
            raise ACPBridgeError("sessionId required")

        if not key:
            raise ACPBridgeError("key required")

        # Check task exists
        state = self.state_machine.get_state(session_id)
        if not state:
            raise ACPBridgeError(f"Task not found: {session_id}")

        # Validate config key (whitelist allowed keys)
        ALLOWED_CONFIG_KEYS = {
            "timeout",
            "max_tokens",
            "temperature",
            "model",
            "streaming",
        }

        if key not in ALLOWED_CONFIG_KEYS:
            raise ACPBridgeError(f"Invalid config key: {key}. Allowed: {ALLOWED_CONFIG_KEYS}")

        # Store config in task metadata (implementation depends on Village's config system)
        # For now, we just log it
        logger.info(f"Set config {key}={value} for session {session_id}")

        return {"sessionId": session_id, "key": key, "value": value}

    async def session_set_model(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ACP session/set_model.

        Sets LLM model for session.

        Args:
            params: ACP session/set_model parameters
                - sessionId: Session ID
                - model: Model identifier

        Returns:
            Model confirmation

        Raises:
            ACPBridgeError: If sessionId not provided
        """
        session_id = params.get("sessionId")
        model = params.get("model")

        if not session_id:
            raise ACPBridgeError("sessionId required")

        if not model:
            raise ACPBridgeError("model required")

        # Check task exists
        state = self.state_machine.get_state(session_id)
        if not state:
            raise ACPBridgeError(f"Task not found: {session_id}")

        # Update task metadata with model
        logger.info(f"Set model {model} for session {session_id}")

        return {"sessionId": session_id, "model": model}

    # === File System API ===

    async def fs_read_text_file(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ACP fs/read_text_file.

        Reads file from Village worktree.

        Args:
            params: ACP fs/read parameters

        Returns:
            File content

        Raises:
            ACPBridgeError: If path invalid or file not found
        """
        path = Path(params.get("path", ""))

        # Validate path is in worktree
        worktree_info = self._find_worktree_for_path(path)
        if not worktree_info:
            raise ACPBridgeError(f"Path not in Village worktree: {path}")

        # Check task is active
        if not self._is_task_active(worktree_info.task_id):
            raise ACPBridgeError(f"Task not active: {worktree_info.task_id}")

        # Read file
        try:
            content = path.read_text(encoding="utf-8")
            logger.debug(f"Read file: {path}")
            return {"content": content, "path": str(path)}
        except FileNotFoundError:
            raise ACPBridgeError(f"File not found: {path}")
        except Exception as e:
            raise ACPBridgeError(f"Failed to read file: {e}") from e

    async def fs_write_text_file(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ACP fs/write_text_file.

        Writes file to Village worktree (atomic).

        Args:
            params: ACP fs/write parameters

        Returns:
            Write confirmation

        Raises:
            ACPBridgeError: If path invalid or write fails
        """
        path = Path(params.get("path", ""))
        content = params.get("content", "")

        # Validate path is in worktree
        worktree_info = self._find_worktree_for_path(path)
        if not worktree_info:
            raise ACPBridgeError(f"Path not in Village worktree: {path}")

        # Check task is active
        if not self._is_task_active(worktree_info.task_id):
            raise ACPBridgeError(f"Task not active: {worktree_info.task_id}")

        # Atomic write
        try:
            temp_path = path.with_suffix(".tmp")
            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(path)

            logger.debug(f"Wrote file: {path}")
            return {"success": True, "path": str(path)}
        except Exception as e:
            raise ACPBridgeError(f"Failed to write file: {e}") from e

    # === Notification Streaming ===

    def _collect_recent_events(self, task_id: str, limit: int = 100) -> list[Event]:
        """Collect recent events for task.

        Args:
            task_id: Task ID
            limit: Maximum events to collect

        Returns:
            List of recent events
        """
        events = read_events(self.config.village_dir)
        task_events = [e for e in events if e.task_id == task_id]
        return task_events[-limit:] if len(task_events) > limit else task_events

    def _event_to_notification(self, event: Event) -> dict[str, Any]:
        """Convert Village event to ACP notification.

        Args:
            event: Village event

        Returns:
            ACP session/update notification
        """
        # Map Village events to ACP notifications
        # Note: Event doesn't have context attribute, we infer from cmd
        if event.cmd == "state_transition":
            # Parse from event data if available
            return {
                "method": "session/update",
                "params": {
                    "sessionId": event.task_id or "",
                    "update": {
                        "type": "state_change",
                        "cmd": event.cmd,
                        "result": event.result,
                    },
                },
            }
        elif event.cmd == "file_modified":
            return {
                "method": "session/update",
                "params": {
                    "sessionId": event.task_id or "",
                    "update": {
                        "type": "file_change",
                        "cmd": event.cmd,
                    },
                },
            }
        else:
            # Generic event notification
            return {
                "method": "session/update",
                "params": {
                    "sessionId": event.task_id or "",
                    "update": {
                        "type": "event",
                        "cmd": event.cmd,
                        "result": event.result,
                    },
                },
            }

    # === Helper Methods ===

    def _get_lock(self, task_id: str) -> Lock | None:
        """Get lock for task.

        Args:
            task_id: Task ID

        Returns:
            Lock if exists, None otherwise
        """
        lock_path = self.config.locks_dir / f"{task_id}.lock"
        return parse_lock(lock_path)

    def _lock_to_dict(self, lock: Lock) -> dict[str, Any]:
        """Convert lock to dict.

        Args:
            lock: Lock object

        Returns:
            Lock as dict
        """
        return {
            "taskId": lock.task_id,
            "paneId": lock.pane_id,
            "window": lock.window,
            "agent": lock.agent,
            "claimedAt": lock.claimed_at.isoformat(),
        }

    def _find_worktree_for_path(self, path: Path) -> Any:
        """Find worktree containing path.

        Args:
            path: File path

        Returns:
            Worktree info if found, None otherwise
        """
        from village.worktrees import get_worktree_info

        # Check all worktrees
        for worktree_dir in self.config.worktrees_dir.iterdir():
            if worktree_dir.is_dir():
                try:
                    # Check if path is under this worktree
                    path.relative_to(worktree_dir)
                    # Found it - extract task_id from directory name
                    task_id = worktree_dir.name
                    try:
                        info = get_worktree_info(task_id, self.config)
                        return info
                    except Exception:
                        # Worktree might not be valid
                        continue
                except ValueError:
                    # Path not under this worktree
                    continue

        return None

    def _is_task_active(self, task_id: str) -> bool:
        """Check if task is active (has lock and pane).

        Args:
            task_id: Task ID

        Returns:
            True if task is active
        """
        lock = self._get_lock(task_id)
        if not lock:
            return False

        # Check if pane exists
        from village.locks import is_active

        return is_active(lock, self.config.tmux_session)

    def _format_resume_result(self, result: ResumeResult) -> str:
        """Format resume result for ACP response.

        Args:
            result: Resume result

        Returns:
            Formatted content string
        """
        lines = [
            f"✓ Task {result.task_id} executed",
            f"Agent: {result.agent}",
            f"Worktree: {result.worktree_path}",
            f"Window: {result.window_name}",
            f"Pane: {result.pane_id}",
        ]

        if result.error:
            lines.append(f"Error: {result.error}")

        return "\n".join(lines)
