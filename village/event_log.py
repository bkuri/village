"""Event logging for operational observability."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Single event in log."""

    ts: str  # ISO-8601 timestamp
    cmd: str  # Command name: "queue", "resume", "cleanup"
    task_id: Optional[str] = None  # Task ID (if applicable)
    pane: Optional[str] = None  # Pane ID (if applicable)
    result: Optional[Literal["ok", "error"]] = None  # Execution result
    error: Optional[str] = None  # Error details (if result="error")


def get_event_log_path(config_path: Path) -> Path:
    """
    Get event log file path.

    Args:
        config_path: Path to village directory

    Returns:
        Path to events.log file
    """
    return config_path / "events.log"


def append_event(event: Event, config_path: Path) -> None:
    """
    Append event to log file (append-only, atomic).

    Args:
        event: Event to log
        config_path: Path to village directory

    Raises:
        IOError: If unable to write to log file
    """
    event_log_path = get_event_log_path(config_path)

    try:
        # Serialize event to JSON
        event_json = json.dumps(
            {
                "ts": event.ts,
                "cmd": event.cmd,
                "task_id": event.task_id,
                "pane": event.pane,
                "result": event.result,
                "error": event.error,
            },
            sort_keys=True,
        )

        # Ensure directory exists
        event_log_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic append operation
        with open(event_log_path, "a", encoding="utf-8") as f:
            f.write(event_json + "\n")
            f.flush()

        logger.debug(f"Logged event: {event.cmd} {event.task_id or ''} {event.result or ''}")

    except IOError as e:
        logger.error(f"Failed to write event to {event_log_path}: {e}")
        raise


def read_events(config_path: Path) -> list[Event]:
    """
    Read all events from log file.

    Args:
        config_path: Path to village directory

    Returns:
        List of Event objects (empty if file doesn't exist)
    """
    event_log_path = get_event_log_path(config_path)

    if not event_log_path.exists():
        logger.debug(f"Event log does not exist: {event_log_path}")
        return []

    events: list[Event] = []

    try:
        with open(event_log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    event = Event(
                        ts=data.get("ts"),
                        cmd=data.get("cmd"),
                        task_id=data.get("task_id"),
                        pane=data.get("pane"),
                        result=data.get("result"),
                        error=data.get("error"),
                    )
                    events.append(event)
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping corrupted event line: {e}")
                    continue

        logger.debug(f"Read {len(events)} events from log")

    except IOError as e:
        logger.error(f"Failed to read event log {event_log_path}: {e}")
        raise

    return events


def is_task_recent(
    events: list[Event],
    task_id: str,
    ttl_minutes: int,
) -> tuple[bool, Optional[Event]]:
    """
    Check if task was executed recently.

    Args:
        events: List of all events
        task_id: Task ID to check
        ttl_minutes: Time-to-live in minutes

    Returns:
        Tuple of (is_recent, last_event)
        - is_recent: True if task was executed within TTL
        - last_event: Most recent event for this task (if any)
    """
    # Filter events for this task
    task_events = [e for e in events if e.task_id == task_id]

    if not task_events:
        return False, None

    # Get most recent execution (by timestamp)
    last_event = max(task_events, key=lambda e: e.ts)

    # Check if within TTL
    try:
        event_time = datetime.fromisoformat(last_event.ts)
    except ValueError:
        logger.warning(f"Invalid timestamp format: {last_event.ts}")
        return False, None

    now = datetime.now(timezone.utc)
    elapsed = now - event_time
    is_recent = elapsed < timedelta(minutes=ttl_minutes)

    if is_recent:
        logger.debug(f"Task {task_id} was recent ({elapsed.seconds}s ago, TTL={ttl_minutes}m)")

    return is_recent, last_event


def log_task_start(task_id: str, cmd: str, config_path: Path) -> None:
    """
    Convenience function to log task start.

    Args:
        task_id: Task ID being started
        cmd: Command name (e.g., "queue", "resume")
        config_path: Path to village directory
    """
    event = Event(
        ts=datetime.now(timezone.utc).isoformat(),
        cmd=cmd,
        task_id=task_id,
        result=None,  # Task started, not completed yet
    )
    append_event(event, config_path)


def log_task_success(
    task_id: str,
    cmd: str,
    pane: str,
    config_path: Path,
) -> None:
    """
    Convenience function to log successful task completion.

    Args:
        task_id: Task ID completed
        cmd: Command name (e.g., "queue", "resume")
        pane: Pane ID where task ran
        config_path: Path to village directory
    """
    event = Event(
        ts=datetime.now(timezone.utc).isoformat(),
        cmd=cmd,
        task_id=task_id,
        pane=pane,
        result="ok",
        error=None,
    )
    append_event(event, config_path)


def log_task_error(
    task_id: str,
    cmd: str,
    error: str,
    config_path: Path,
) -> None:
    """
    Convenience function to log task failure.

    Args:
        task_id: Task ID that failed
        cmd: Command name (e.g., "queue", "resume")
        error: Error message
        config_path: Path to village directory
    """
    event = Event(
        ts=datetime.now(timezone.utc).isoformat(),
        cmd=cmd,
        task_id=task_id,
        pane=None,
        result="error",
        error=error,
    )
    append_event(event, config_path)
