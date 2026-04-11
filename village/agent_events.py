"""Agent event parsing for completion detection."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AgentCompletion:
    """Agent completion result parsed from event stream."""

    task_id: str
    completed: bool
    success: bool
    error: str | None = None
    tool_calls: int = 0
    events_parsed: int = 0


def parse_agent_events(trace_path: Path) -> AgentCompletion | None:
    """Parse agent JSON events from trace file.

    Returns None if file doesn't exist or has no parseable events.
    Returns AgentCompletion with completion status.
    """
    if not trace_path.exists():
        return None

    completed = False
    success = True
    error = None
    tool_calls = 0
    events_parsed = 0

    try:
        text = trace_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                events_parsed += 1

                event_type = event.get("type", "")

                if event_type == "tool_call":
                    tool_calls += 1
                elif event_type == "error":
                    success = False
                    error = event.get("message", str(event))
                elif event_type in ("result", "response"):
                    completed = True
                elif event_type == "done":
                    completed = True
            except json.JSONDecodeError:
                continue
    except OSError as e:
        logger.warning(f"Failed to read agent events from {trace_path}: {e}")
        return None

    if events_parsed == 0:
        return None

    return AgentCompletion(
        task_id=trace_path.stem.replace("-agent", ""),
        completed=completed,
        success=success,
        error=error,
        tool_calls=tool_calls,
        events_parsed=events_parsed,
    )


def check_agent_completion(task_id: str, traces_dir: Path) -> AgentCompletion | None:
    """Check if a pi agent has completed for a given task.

    Looks for .village/traces/<task_id>-agent.jsonl.
    """
    trace_path = traces_dir / f"{task_id}-agent.jsonl"
    return parse_agent_events(trace_path)
