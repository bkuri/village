"""Bridge ACP protocol to Village core operations.

This module provides the critical integration layer that:
- Maps ACP sessions to Village tasks
- Bridges ACP methods to Village operations (resume, queue, etc.)
- Converts Village events to ACP notifications
- Handles state transitions and error translation
"""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
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
        self._session_cwds: dict[str, str] = {}
        self._session_models: dict[str, str] = {}

    def _get_session_config(self, session_id: str) -> Config:
        """Get config for a session.

        Args:
            session_id: Session ID

        Returns:
            Config for the session's cwd, or default config
        """
        from village.config import get_config_for_cwd

        cwd = self._session_cwds.get(session_id)
        if cwd:
            try:
                return get_config_for_cwd(cwd)
            except Exception as e:
                logger.warning(f"Failed to load config for cwd {cwd}: {e}, using default")
                return self.config
        return self.config

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

        cwd = params.get("cwd")
        if cwd:
            self._session_cwds[session_id] = cwd

        # Initialize Village task state
        result = self.state_machine.initialize_state(
            session_id,
            TaskState.QUEUED,
            context={"source": "acp", "params": params},
        )

        if not result.success:
            raise ACPBridgeError(f"Failed to create task: {result.message}")

        logger.info(f"Created ACP session: {session_id} (cwd={cwd})")

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

        cwd = params.get("cwd")
        if cwd:
            self._session_cwds[session_id] = cwd

        # Check if task exists
        state = self.state_machine.get_state(session_id)
        if not state:
            raise ACPBridgeError(f"Task not found: {session_id}")

        # Get lock info if exists
        config = self._get_session_config(session_id)
        lock = self._get_lock(session_id, config)

        logger.info(f"Loaded ACP session: {session_id} (state={state.value})")

        return {
            "sessionId": session_id,
            "state": state.value,
            "lock": self._lock_to_dict(lock) if lock else None,
        }

    def set_session_model(self, session_id: str, model_id: str) -> None:
        """Store model override for a session.

        Args:
            session_id: Session ID
            model_id: Model ID to use for this session
        """
        self._session_models[session_id] = model_id
        logger.info(f"Set model override for session {session_id}: {model_id}")

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

        if not session_id:
            raise ACPBridgeError("sessionId required")

        # Get config for this session's cwd
        config = self._get_session_config(session_id)

        # Determine agent: check model override first, then params, then default
        agent = self._get_agent_for_session(session_id, config)
        if not agent:
            agent = params.get("agent", config.default_agent)

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
                config=config,
            )

            # Collect events for notifications
            events = self._collect_recent_events(session_id, config=config)
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

        Cancels or pauses Village task based on current state.

        Args:
            params: ACP session/cancel parameters

        Returns:
            Cancel confirmation

        Raises:
            ACPBridgeError: If sessionId not provided or cancel fails
        """
        session_id = params.get("sessionId")
        if not session_id:
            raise ACPBridgeError("sessionId required")

        # Get current state
        current_state = self.state_machine.get_state(session_id)
        if not current_state:
            raise ACPBridgeError(f"Task not found: {session_id}")

        # Handle based on current state
        if current_state == TaskState.QUEUED:
            # Task not started - mark as cancelled via CLAIMED -> FAILED path
            # First claim it (with cancel context)
            claim_result = self.state_machine.transition(
                session_id, TaskState.CLAIMED, context={"reason": "cancelling"}
            )
            if not claim_result.success:
                # Can't claim it, but that's ok - task is effectively cancelled
                logger.warning(f"Cannot claim task for cancellation: {claim_result.message}")
                return {"sessionId": session_id, "state": "cancelled", "queued": True}

            # Then fail it
            result = self.state_machine.transition(session_id, TaskState.FAILED, context={"reason": "cancelled"})
            final_state = "failed"
        elif current_state == TaskState.IN_PROGRESS:
            # Task running - pause it
            result = self.state_machine.transition(session_id, TaskState.PAUSED)
            final_state = "paused"
        elif current_state == TaskState.CLAIMED:
            # Claimed but not started - fail it
            result = self.state_machine.transition(session_id, TaskState.FAILED, context={"reason": "cancelled"})
            final_state = "failed"
        elif current_state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.PAUSED):
            # Already terminal or paused
            return {"sessionId": session_id, "state": current_state.value}
        else:
            # Unknown state
            raise ACPBridgeError(f"Cannot cancel task in state: {current_state.value}")

        if not result.success:
            raise ACPBridgeError(f"Cannot cancel task: {result.message}")

        logger.info(f"Cancelled ACP session: {session_id}")

        return {"sessionId": session_id, "state": final_state}

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

    # === Terminal API ===

    async def terminal_create(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ACP terminal/create.

        Creates tmux pane in Village session.

        Args:
            params: ACP terminal/create parameters
                - command: Command to execute
                - args: Optional command arguments
                - cwd: Optional working directory
                - env: Optional environment variables
                - output_byte_limit: Optional output limit

        Returns:
            Terminal info with terminal_id

        Raises:
            ACPBridgeError: If sessionId not provided or creation fails
        """
        import uuid

        from village.probes.tmux import create_window

        session_id = params.get("sessionId")
        command = params.get("command", "")
        args = params.get("args", [])
        cwd = params.get("cwd")
        env = params.get("env", [])
        output_byte_limit = params.get("output_byte_limit")

        if not session_id:
            raise ACPBridgeError("sessionId required")

        # Check task is active
        if not self._is_task_active(session_id):
            raise ACPBridgeError(f"Task not active: {session_id}")

        # Generate terminal ID
        terminal_id = f"term-{uuid.uuid4().hex[:8]}"

        # Create tmux window
        window_name = f"{session_id}-{terminal_id}"
        success = create_window(
            self.config.tmux_session,
            window_name,
            command or "",
        )

        if not success:
            raise ACPBridgeError(f"Failed to create terminal: {terminal_id}")

        # Store terminal metadata
        if not hasattr(self, "_terminals"):
            self._terminals = {}

        self._terminals[terminal_id] = {
            "sessionId": session_id,
            "windowName": window_name,
            "command": command,
            "args": args,
            "cwd": cwd,
            "env": env,
            "outputByteLimit": output_byte_limit,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"Created terminal {terminal_id} for session {session_id}")

        return {
            "terminalId": terminal_id,
            "windowName": window_name,
        }

    async def terminal_output(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ACP terminal/output.

        Captures output from tmux pane.

        Args:
            params: ACP terminal/output parameters
                - sessionId: Session ID
                - terminalId: Terminal ID

        Returns:
            Terminal output

        Raises:
            ACPBridgeError: If sessionId/terminalId not provided or terminal not found
        """
        session_id = params.get("sessionId")
        terminal_id = params.get("terminalId")

        if not session_id:
            raise ACPBridgeError("sessionId required")

        if not terminal_id:
            raise ACPBridgeError("terminalId required")

        # Check terminal exists
        if not hasattr(self, "_terminals") or terminal_id not in self._terminals:
            raise ACPBridgeError(f"Terminal not found: {terminal_id}")

        terminal_info = self._terminals[terminal_id]

        if terminal_info["sessionId"] != session_id:
            raise ACPBridgeError(f"Terminal does not belong to session: {terminal_id}")

        # Capture pane output
        from village.probes.tmux import capture_pane

        # Find pane by window name
        window_name = terminal_info["windowName"]

        # Get pane ID from window
        import subprocess

        result = subprocess.run(
            ["tmux", "list-panes", "-t", f"{self.config.tmux_session}:{window_name}", "-F", "#{pane_id}"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise ACPBridgeError(f"Failed to list panes: {result.stderr}")

        pane_id = result.stdout.strip()

        # Capture output
        try:
            output = capture_pane(self.config.tmux_session, pane_id)

            # Apply byte limit if specified
            byte_limit = terminal_info.get("outputByteLimit")
            if byte_limit and len(output) > byte_limit:
                output = output[:byte_limit]
                truncated = True
            else:
                truncated = False

            logger.debug(f"Captured {len(output)} bytes from terminal {terminal_id}")

            return {
                "terminalId": terminal_id,
                "output": output,
                "truncated": truncated,
            }
        except Exception as e:
            raise ACPBridgeError(f"Failed to capture output: {e}") from e

    async def terminal_kill(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ACP terminal/kill.

        Kills tmux pane.

        Args:
            params: ACP terminal/kill parameters
                - sessionId: Session ID
                - terminalId: Terminal ID

        Returns:
            Kill confirmation

        Raises:
            ACPBridgeError: If sessionId/terminalId not provided or terminal not found
        """
        session_id = params.get("sessionId")
        terminal_id = params.get("terminalId")

        if not session_id:
            raise ACPBridgeError("sessionId required")

        if not terminal_id:
            raise ACPBridgeError("terminalId required")

        # Check terminal exists
        if not hasattr(self, "_terminals") or terminal_id not in self._terminals:
            raise ACPBridgeError(f"Terminal not found: {terminal_id}")

        terminal_info = self._terminals[terminal_id]

        if terminal_info["sessionId"] != session_id:
            raise ACPBridgeError(f"Terminal does not belong to session: {terminal_id}")

        # Kill window
        from village.probes.tmux import kill_session

        window_name = terminal_info["windowName"]
        success = kill_session(f"{self.config.tmux_session}:{window_name}")

        if not success:
            logger.warning(f"Failed to kill terminal window: {window_name}")

        # Remove from tracking
        del self._terminals[terminal_id]

        logger.info(f"Killed terminal {terminal_id} for session {session_id}")

        return {"terminalId": terminal_id, "killed": True}

    async def terminal_release(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ACP terminal/release.

        Releases terminal (keeps window alive butbut stops tracking).

        Args:
            params: ACP terminal/release parameters
                - sessionId: Session ID
                - terminalId: Terminal ID

        Returns:
            Release confirmation

        Raises:
            ACPBridgeError: If sessionId/terminalId not provided or terminal not found
        """
        session_id = params.get("sessionId")
        terminal_id = params.get("terminalId")

        if not session_id:
            raise ACPBridgeError("sessionId required")

        if not terminal_id:
            raise ACPBridgeError("terminalId required")

        # Check terminal exists
        if not hasattr(self, "_terminals") or terminal_id not in self._terminals:
            raise ACPBridgeError(f"Terminal not found: {terminal_id}")

        terminal_info = self._terminals[terminal_id]

        if terminal_info["sessionId"] != session_id:
            raise ACPBridgeError(f"Terminal does not belong to session: {terminal_id}")

        # Remove from tracking (window stays alive)
        del self._terminals[terminal_id]

        logger.info(f"Released terminal {terminal_id} for session {session_id}")

        return {"terminalId": terminal_id, "released": True}

    async def terminal_wait_for_exit(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ACP terminal/wait_for_exit.

        Waits for terminal command to exit.

        Args:
            params: ACP terminal/wait_for_exit parameters
                - sessionId: Session ID
                - terminalId: Terminal ID
                - timeout: Optional timeout in seconds

        Returns:
            Exit status

        Raises:
            ACPBridgeError: If sessionId/terminalId not provided or terminal not found
        """
        import asyncio

        session_id = params.get("sessionId")
        terminal_id = params.get("terminalId")
        timeout = params.get("timeout", 60)

        if not session_id:
            raise ACPBridgeError("sessionId required")

        if not terminal_id:
            raise ACPBridgeError("terminalId required")

        # Check terminal exists
        if not hasattr(self, "_terminals") or terminal_id not in self._terminals:
            raise ACPBridgeError(f"Terminal not found: {terminal_id}")

        terminal_info = self._terminals[terminal_id]

        if terminal_info["sessionId"] != session_id:
            raise ACPBridgeError(f"Terminal does not belong to session: {terminal_id}")

        # Wait for pane to to window_name = terminal_info["windowName"]
        start_time = asyncio.get_event_loop().time()

        while True:
            # Check if window still exists
            import subprocess

            result = subprocess.run(
                ["tmux", "list-windows", "-t", self.config.tmux_session, "-F", "#{window_name}"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                # Window no longer exists - command exited
                elapsed = asyncio.get_event_loop().time() - start_time
                return {
                    "terminalId": terminal_id,
                    "exitStatus": 0,  # Assume success
                    "elapsed": elapsed,
                }

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                return {
                    "terminalId": terminal_id,
                    "exitStatus": None,
                    "timeout": True,
                    "elapsed": elapsed,
                }

            # Wait before checking again
            await asyncio.sleep(0.5)

    # === Notification Streaming ===

    async def stream_notifications(
        self,
        session_id: str,
        poll_interval: float = 0.5,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream notifications for session in real-time.

        Async generator that watches for new events and yields
        ACP notifications as they occur.

        Args:
            session_id: Session ID to stream notifications for
            poll_interval: How often to check for new events (seconds)

        Yields:
            ACP session/update notifications
        """
        import asyncio

        last_event_ts = ""

        logger.info(f"Starting notification stream for session {session_id}")

        while True:
            try:
                # Read all events
                all_events = read_events(self.config.village_dir)

                # Filter for this session
                session_events = [e for e in all_events if e.task_id == session_id]

                # Find new events since last check
                new_events = []
                if last_event_ts:
                    for event in session_events:
                        if event.ts > last_event_ts:
                            new_events.append(event)
                else:
                    # First run - get most recent event timestamp
                    if session_events:
                        last_event_ts = max(e.ts for e in session_events)

                # Convert new events to notifications and yield
                for event in new_events:
                    notification = self._event_to_notification(event)
                    last_event_ts = event.ts
                    logger.debug(f"Streaming notification: {event.cmd} for {session_id}")
                    yield notification

                # Wait before next check
                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Error streaming notifications: {e}")
                # Continue streaming despite errors
                await asyncio.sleep(poll_interval)

    def _collect_recent_events(self, task_id: str, config: Config | None = None, limit: int = 100) -> list[Event]:
        """Collect recent events for task.

        Args:
            task_id: Task ID
            config: Config to use (uses self.config if not provided)
            limit: Maximum events to collect

        Returns:
            List of recent events
        """
        cfg = config or self.config
        events = read_events(cfg.village_dir)
        task_events = [e for e in events if e.task_id == task_id]
        return task_events[-limit:] if len(task_events) > limit else task_events

    def _event_to_notification(self, event: Event) -> dict[str, Any]:
        """Convert Village event to ACP notification.

        Maps Village event types to ACP notification types:
        - state_transition → state_change
        - file_modified → file_change
        - conflict_detected → conflict
        - queue/resume/cleanup → lifecycle
        - error → error

        Args:
            event: Village event

        Returns:
            ACP session/update notification
        """
        # Map event commands to notification types
        cmd = event.cmd
        notification_type = "event"  # default

        # Check error first (highest priority)
        if event.result == "error":
            notification_type = "error"
        elif cmd == "state_transition":
            notification_type = "state_change"
        elif cmd in ("file_modified", "file_created", "file_deleted"):
            notification_type = "file_change"
        elif cmd in ("conflict_detected", "merge_conflict"):
            notification_type = "conflict"
        elif cmd in ("queue", "resume", "cleanup", "claim", "release"):
            notification_type = "lifecycle"

        # Build update dict
        update: dict[str, Any] = {
            "type": notification_type,
            "cmd": cmd,
            "ts": event.ts,
        }

        # Add optional fields
        if event.result:
            update["result"] = event.result
        if event.error:
            update["error"] = event.error
        if event.pane:
            update["pane"] = event.pane

        # Build notification
        notification = {
            "method": "session/update",
            "params": {
                "sessionId": event.task_id or "",
                "update": update,
            },
        }

        return notification

    # === Helper Methods ===

    def _get_agent_for_session(self, session_id: str, config: Config) -> str | None:
        """Get agent name for session based on model override.

        If session has a model override, finds agent with matching llm_model.
        Returns None if no match found, allowing fallback to default.

        Args:
            session_id: Session ID
            config: Config for this session

        Returns:
            Agent name if found, None otherwise
        """
        model_id = self._session_models.get(session_id)
        if not model_id:
            return None

        # Search for agent with matching llm_model
        for agent_name, agent_config in config.agents.items():
            if agent_config.llm_model == model_id:
                logger.debug(f"Found agent '{agent_name}' matching model '{model_id}'")
                return agent_name

        logger.warning(f"No agent found with llm_model='{model_id}', using default")
        return None

    def _get_lock(self, task_id: str, config: Config | None = None) -> Lock | None:
        """Get lock for task.

        Args:
            task_id: Task ID
            config: Config to use (uses self.config if not provided)

        Returns:
            Lock if exists, None otherwise
        """
        cfg = config or self.config
        lock_path = cfg.locks_dir / f"{task_id}.lock"
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

    def _is_task_active(self, task_id: str, config: Config | None = None) -> bool:
        """Check if task is active (has lock and pane).

        Args:
            task_id: Task ID
            config: Config to use (uses self.config if not provided)

        Returns:
            True if task is active
        """
        cfg = config or self.config
        lock = self._get_lock(task_id, cfg)
        if not lock:
            return False

        # Check if pane exists
        from village.locks import is_active

        return is_active(lock, cfg.tmux_session)

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
