"""Test event logging functionality."""

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from village.config import Config
from village.event_log import (
    Event,
    append_event,
    get_event_log_path,
    is_task_recent,
    log_task_error,
    log_task_start,
    log_task_success,
    read_events,
)


def test_get_event_log_path():
    """Test event log path resolution."""
    config_path = Path("/tmp/test/.village")
    event_log_path = get_event_log_path(config_path)

    assert event_log_path == config_path / "events.log"


def test_append_event_creates_file(tmp_path: Path):
    """Test append_event creates log file if it doesn't exist."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    event = Event(
        ts="2026-01-24T10:00:00",
        cmd="queue",
        task_id="bd-a3f8",
        pane="%12",
        result="ok",
    )

    append_event(event, config.village_dir)

    event_log_path = get_event_log_path(config.village_dir)
    assert event_log_path.exists()


def test_append_event_appends(tmp_path: Path):
    """Test append_event appends to existing log file."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    event1 = Event(
        ts="2026-01-24T10:00:00",
        cmd="queue",
        task_id="bd-a3f8",
        pane="%12",
        result="ok",
    )

    event2 = Event(
        ts="2026-01-24T10:05:00",
        cmd="queue",
        task_id="bd-1234",
        pane="%13",
        result="error",
        error="Test error",
    )

    append_event(event1, config.village_dir)
    append_event(event2, config.village_dir)

    events = read_events(config.village_dir)
    assert len(events) == 2
    assert events[0].task_id == "bd-a3f8"
    assert events[1].task_id == "bd-1234"


def test_append_event_json_format(tmp_path: Path):
    """Test append_event writes correct JSON format."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    event = Event(
        ts="2026-01-24T10:00:00",
        cmd="queue",
        task_id="bd-a3f8",
        pane="%12",
        result="ok",
    )

    append_event(event, config.village_dir)

    event_log_path = get_event_log_path(config.village_dir)
    content = event_log_path.read_text(encoding="utf-8")

    assert '"cmd": "queue"' in content
    assert '"task_id": "bd-a3f8"' in content
    assert '"pane": "%12"' in content
    assert '"result": "ok"' in content
    assert '"ts": "2026-01-24T10:00:00"' in content


def test_read_events_empty_log(tmp_path: Path):
    """Test read_events returns empty list for non-existent log."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    events = read_events(config.village_dir)

    assert events == []


def test_read_events_populated_log(tmp_path: Path):
    """Test read_events parses events from log file."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    event1 = Event(
        ts="2026-01-24T10:00:00",
        cmd="queue",
        task_id="bd-a3f8",
        pane="%12",
        result="ok",
    )

    event2 = Event(
        ts="2026-01-24T10:05:00",
        cmd="resume",
        task_id="bd-1234",
        pane="%13",
        result="error",
        error="Failed to resume",
    )

    append_event(event1, config.village_dir)
    append_event(event2, config.village_dir)

    events = read_events(config.village_dir)

    assert len(events) == 2
    assert events[0].cmd == "queue"
    assert events[0].task_id == "bd-a3f8"
    assert events[0].pane == "%12"
    assert events[0].result == "ok"

    assert events[1].cmd == "resume"
    assert events[1].task_id == "bd-1234"
    assert events[1].pane == "%13"
    assert events[1].result == "error"
    assert events[1].error == "Failed to resume"


def test_read_events_skips_blank_lines(tmp_path: Path):
    """Test read_events skips blank lines in log file."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    event = Event(
        ts="2026-01-24T10:00:00",
        cmd="queue",
        task_id="bd-a3f8",
        pane="%12",
        result="ok",
    )

    append_event(event, config.village_dir)

    event_log_path = get_event_log_path(config.village_dir)
    with open(event_log_path, "a", encoding="utf-8") as f:
        f.write("\n\n")

    events = read_events(config.village_dir)

    assert len(events) == 1


def test_read_events_handles_corrupted_lines(tmp_path: Path):
    """Test read_events skips corrupted JSON lines."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    event = Event(
        ts="2026-01-24T10:00:00",
        cmd="queue",
        task_id="bd-a3f8",
        pane="%12",
        result="ok",
    )

    append_event(event, config.village_dir)

    event_log_path = get_event_log_path(config.village_dir)
    with open(event_log_path, "a", encoding="utf-8") as f:
        f.write('{"invalid": json}\n')

    events = read_events(config.village_dir)

    assert len(events) == 1
    assert events[0].task_id == "bd-a3f8"


def test_is_task_recent_no_events():
    """Test is_task_recent returns False when no events exist."""
    is_recent, last_event = is_task_recent([], "bd-a3f8", 5)

    assert is_recent is False
    assert last_event is None


def test_is_task_recent_no_matching_task():
    """Test is_task_recent returns False when task not found."""
    events = [
        Event(
            ts="2026-01-24T10:00:00",
            cmd="queue",
            task_id="bd-1234",
            pane="%13",
            result="ok",
        )
    ]

    is_recent, last_event = is_task_recent(events, "bd-a3f8", 5)

    assert is_recent is False
    assert last_event is None


def test_is_task_recent_within_ttl():
    """Test is_task_recent returns True when within TTL."""
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(minutes=2)).isoformat()

    events = [
        Event(
            ts=ts,
            cmd="queue",
            task_id="bd-a3f8",
            pane="%12",
            result="ok",
        )
    ]

    is_recent, last_event = is_task_recent(events, "bd-a3f8", 5)

    assert is_recent is True
    assert last_event.task_id == "bd-a3f8"


def test_is_task_recent_outside_ttl():
    """Test is_task_recent returns False when outside TTL."""
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(minutes=10)).isoformat()

    events = [
        Event(
            ts=ts,
            cmd="queue",
            task_id="bd-a3f8",
            pane="%12",
            result="ok",
        )
    ]

    is_recent, last_event = is_task_recent(events, "bd-a3f8", 5)

    assert is_recent is False
    assert last_event.task_id == "bd-a3f8"


def test_is_task_recent_returns_most_recent():
    """Test is_task_recent returns most recent event for task."""
    now = datetime.now(timezone.utc)
    ts1 = (now - timedelta(minutes=10)).isoformat()
    ts2 = (now - timedelta(minutes=2)).isoformat()

    events = [
        Event(
            ts=ts1,
            cmd="queue",
            task_id="bd-a3f8",
            pane="%12",
            result="error",
            error="First attempt",
        ),
        Event(
            ts=ts2,
            cmd="queue",
            task_id="bd-a3f8",
            pane="%13",
            result="ok",
        ),
    ]

    is_recent, last_event = is_task_recent(events, "bd-a3f8", 5)

    assert is_recent is True
    assert last_event.pane == "%13"
    assert last_event.result == "ok"


def test_is_task_recent_handles_invalid_timestamp():
    """Test is_task_recent handles invalid timestamp format."""
    events = [
        Event(
            ts="invalid-timestamp",
            cmd="queue",
            task_id="bd-a3f8",
            pane="%12",
            result="ok",
        )
    ]

    is_recent, last_event = is_task_recent(events, "bd-a3f8", 5)

    assert is_recent is False
    assert last_event is None


def test_log_task_start(tmp_path: Path):
    """Test log_task_start creates event with current timestamp."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    log_task_start("bd-a3f8", "queue", config.village_dir)

    events = read_events(config.village_dir)
    assert len(events) == 1
    assert events[0].cmd == "queue"
    assert events[0].task_id == "bd-a3f8"
    assert events[0].result is None


def test_log_task_success(tmp_path: Path):
    """Test log_task_success creates event with result='ok'."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    log_task_success("bd-a3f8", "queue", "%12", config.village_dir)

    events = read_events(config.village_dir)
    assert len(events) == 1
    assert events[0].cmd == "queue"
    assert events[0].task_id == "bd-a3f8"
    assert events[0].pane == "%12"
    assert events[0].result == "ok"
    assert events[0].error is None


def test_log_task_error(tmp_path: Path):
    """Test log_task_error creates event with result='error'."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    log_task_error("bd-a3f8", "queue", "Task failed", config.village_dir)

    events = read_events(config.village_dir)
    assert len(events) == 1
    assert events[0].cmd == "queue"
    assert events[0].task_id == "bd-a3f8"
    assert events[0].result == "error"
    assert events[0].error == "Task failed"
    assert events[0].pane is None


def test_log_task_lifecycle(tmp_path: Path):
    """Test complete task lifecycle logging."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    task_id = "bd-a3f8"
    cmd = "queue"

    log_task_start(task_id, cmd, config.village_dir)
    log_task_success(task_id, cmd, "%12", config.village_dir)

    events = read_events(config.village_dir)
    assert len(events) == 2

    assert events[0].result is None
    assert events[1].result == "ok"
    assert events[1].pane == "%12"


def test_event_dataclass_defaults():
    """Test Event dataclass has correct defaults."""
    event = Event(
        ts="2026-01-24T10:00:00",
        cmd="queue",
    )

    assert event.ts == "2026-01-24T10:00:00"
    assert event.cmd == "queue"
    assert event.task_id is None
    assert event.pane is None
    assert event.result is None
    assert event.error is None
