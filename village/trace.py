"""Structured trace/audit trail for task execution."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class TraceEventType(str, Enum):
    """Trace event types for audit trail."""

    TASK_CHECKOUT = "task_checkout"
    TOOL_CALL = "tool_call"
    DECISION = "decision"
    FILE_MODIFIED = "file_modified"
    TASK_COMPLETE = "task_complete"
    STATE_TRANSITION = "state_transition"
    ERROR = "error"


@dataclass
class TraceEvent:
    """Single trace event in audit trail."""

    timestamp: str
    event_type: TraceEventType
    task_id: str
    agent: str
    data: dict[str, object]
    sequence: int = 0


class TraceWriter:
    """Appends trace events to a per-task JSONL file."""

    def __init__(self, task_id: str, traces_dir: Path) -> None:
        self.task_id = task_id
        self.traces_dir = traces_dir
        self._sequence = 0

    def _trace_path(self) -> Path:
        return self.traces_dir / f"{self.task_id}.jsonl"

    def record(self, event_type: TraceEventType, agent: str = "", **data: object) -> None:
        """Record a trace event (append to JSONL file)."""
        self._sequence += 1
        event = TraceEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            task_id=self.task_id,
            agent=agent,
            data=data,
            sequence=self._sequence,
        )
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        with open(self._trace_path(), "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "timestamp": event.timestamp,
                        "event_type": event.event_type.value,
                        "task_id": event.task_id,
                        "agent": event.agent,
                        "data": event.data,
                        "sequence": event.sequence,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            f.flush()


class TraceReader:
    """Reads trace events from per-task JSONL files."""

    def __init__(self, traces_dir: Path) -> None:
        self.traces_dir = traces_dir

    def read(self, task_id: str) -> list[TraceEvent]:
        """Read all trace events for a task."""
        path = self.traces_dir / f"{task_id}.jsonl"
        if not path.exists():
            return []
        events: list[TraceEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                events.append(
                    TraceEvent(
                        timestamp=raw["timestamp"],
                        event_type=TraceEventType(raw["event_type"]),
                        task_id=raw["task_id"],
                        agent=raw.get("agent", ""),
                        data=raw.get("data", {}),
                        sequence=raw.get("sequence", 0),
                    )
                )
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Skipping corrupted trace line: {e}")
        return events

    def list_traced_tasks(self) -> list[str]:
        """List all task IDs that have traces."""
        if not self.traces_dir.exists():
            return []
        return sorted(p.stem for p in self.traces_dir.glob("*.jsonl"))


def format_trace(events: list[TraceEvent]) -> str:
    """Format trace events as readable text."""
    if not events:
        return "No trace events"
    lines: list[str] = []
    for event in events:
        parts = [
            f"[{event.sequence}]",
            event.timestamp,
            event.event_type.value,
        ]
        if event.agent:
            parts.append(f"agent={event.agent}")
        if event.data:
            data_str = " ".join(f"{k}={v}" for k, v in event.data.items())
            parts.append(data_str)
        lines.append(" ".join(parts))
    return "\n".join(lines)
