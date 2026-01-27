"""Test event query functionality."""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from village.config import Config
from village.event_log import Event, append_event
from village.event_query import (
    EventFilters,
    QueryResult,
    _apply_filters,
    _parse_timestamp,
    _render_table,
    query_events,
    query_result_to_dict,
    query_result_to_json,
)


def test_event_filters_defaults():
    """Test EventFilters has correct defaults."""
    filters = EventFilters()

    assert filters.task_id is None
    assert filters.status is None
    assert filters.since is None
    assert filters.last is None


def test_event_filters_with_values():
    """Test EventFilters with values."""
    since = datetime(2026, 1, 24, 10, 0, 0, tzinfo=timezone.utc)
    last = timedelta(hours=1)

    filters = EventFilters(
        task_id="bd-a3f8",
        status="ok",
        since=since,
        last=last,
    )

    assert filters.task_id == "bd-a3f8"
    assert filters.status == "ok"
    assert filters.since == since
    assert filters.last == last


def test_query_result_dataclass():
    """Test QueryResult dataclass."""
    events = [
        Event(
            ts="2026-01-24T10:00:00",
            cmd="queue",
            task_id="bd-a3f8",
        )
    ]

    result = QueryResult(
        events=events,
        total_count=10,
        filtered_count=1,
        query_time="2026-01-24T10:00:00",
    )

    assert len(result.events) == 1
    assert result.total_count == 10
    assert result.filtered_count == 1
    assert result.query_time == "2026-01-24T10:00:00"


def test_query_events_no_filters_json(tmp_path: Path):
    """Test query_events with no filters returns all events as JSON."""
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
        error="Test error",
    )

    append_event(event1, config.village_dir)
    append_event(event2, config.village_dir)

    filters = EventFilters()
    result = query_events(filters, "json", config.village_dir)

    assert isinstance(result, QueryResult)
    assert len(result.events) == 2
    assert result.total_count == 2
    assert result.filtered_count == 2


def test_query_events_filter_by_task_id(tmp_path: Path):
    """Test query_events filters by task_id."""
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
    )

    append_event(event1, config.village_dir)
    append_event(event2, config.village_dir)

    filters = EventFilters(task_id="bd-a3f8")
    result = query_events(filters, "json", config.village_dir)

    assert len(result.events) == 1
    assert result.events[0].task_id == "bd-a3f8"
    assert result.filtered_count == 1


def test_query_events_filter_by_status(tmp_path: Path):
    """Test query_events filters by status."""
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
        error="Test error",
    )

    event3 = Event(
        ts="2026-01-24T10:10:00",
        cmd="queue",
        task_id="bd-5678",
        pane="%14",
        result="ok",
    )

    append_event(event1, config.village_dir)
    append_event(event2, config.village_dir)
    append_event(event3, config.village_dir)

    filters = EventFilters(status="ok")
    result = query_events(filters, "json", config.village_dir)

    assert len(result.events) == 2
    assert all(e.result == "ok" for e in result.events)
    assert result.filtered_count == 2


def test_query_events_filter_by_since(tmp_path: Path):
    """Test query_events filters by since timestamp."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    now = datetime.now(timezone.utc)

    event1 = Event(
        ts=(now - timedelta(hours=2)).isoformat(),
        cmd="queue",
        task_id="bd-a3f8",
        result="ok",
    )

    event2 = Event(
        ts=(now - timedelta(minutes=30)).isoformat(),
        cmd="resume",
        task_id="bd-1234",
        result="error",
    )

    append_event(event1, config.village_dir)
    append_event(event2, config.village_dir)

    since = now - timedelta(hours=1)
    filters = EventFilters(since=since)
    result = query_events(filters, "json", config.village_dir)

    assert len(result.events) == 1
    assert result.events[0].task_id == "bd-1234"
    assert result.filtered_count == 1


def test_query_events_filter_by_last(tmp_path: Path):
    """Test query_events filters by last timedelta."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    now = datetime.now(timezone.utc)

    event1 = Event(
        ts=(now - timedelta(hours=2)).isoformat(),
        cmd="queue",
        task_id="bd-a3f8",
        result="ok",
    )

    event2 = Event(
        ts=(now - timedelta(minutes=30)).isoformat(),
        cmd="resume",
        task_id="bd-1234",
        result="error",
    )

    append_event(event1, config.village_dir)
    append_event(event2, config.village_dir)

    filters = EventFilters(last=timedelta(hours=1))
    result = query_events(filters, "json", config.village_dir)

    assert len(result.events) == 1
    assert result.events[0].task_id == "bd-1234"
    assert result.filtered_count == 1


def test_query_events_multiple_filters(tmp_path: Path):
    """Test query_events with multiple filters."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    now = datetime.now(timezone.utc)

    event1 = Event(
        ts=(now - timedelta(hours=2)).isoformat(),
        cmd="queue",
        task_id="bd-a3f8",
        pane="%12",
        result="ok",
    )

    event2 = Event(
        ts=(now - timedelta(minutes=30)).isoformat(),
        cmd="queue",
        task_id="bd-a3f8",
        pane="%13",
        result="error",
        error="Test error",
    )

    event3 = Event(
        ts=(now - timedelta(minutes=20)).isoformat(),
        cmd="queue",
        task_id="bd-1234",
        pane="%14",
        result="ok",
    )

    append_event(event1, config.village_dir)
    append_event(event2, config.village_dir)
    append_event(event3, config.village_dir)

    filters = EventFilters(
        task_id="bd-a3f8",
        status="error",
        last=timedelta(hours=1),
    )
    result = query_events(filters, "json", config.village_dir)

    assert len(result.events) == 1
    assert result.events[0].task_id == "bd-a3f8"
    assert result.events[0].result == "error"
    assert result.filtered_count == 1


def test_query_events_no_matches(tmp_path: Path):
    """Test query_events with no matching events."""
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
        result="ok",
    )

    append_event(event, config.village_dir)

    filters = EventFilters(task_id="nonexistent")
    result = query_events(filters, "json", config.village_dir)

    assert len(result.events) == 0
    assert result.total_count == 1
    assert result.filtered_count == 0


def test_query_events_missing_log(tmp_path: Path):
    """Test query_events handles missing event log."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    filters = EventFilters()
    result = query_events(filters, "json", config.village_dir)

    assert isinstance(result, QueryResult)
    assert len(result.events) == 0
    assert result.total_count == 0


def test_query_events_table_format(tmp_path: Path):
    """Test query_events returns table string."""
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

    filters = EventFilters()
    result = query_events(filters, "table", config.village_dir)

    assert isinstance(result, str)
    assert "TS" in result
    assert "CMD" in result
    assert "TASK_ID" in result
    assert "bd-a3f8" in result
    assert "queue" in result


def test_query_events_table_format_empty(tmp_path: Path):
    """Test query_events table format with no events."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )

    filters = EventFilters()
    result = query_events(filters, "table", config.village_dir)

    assert result == "No events found matching filters"


def test_apply_filters_task_id():
    """Test _apply_filters with task_id filter."""
    events = [
        Event(
            ts="2026-01-24T10:00:00",
            cmd="queue",
            task_id="bd-a3f8",
            result="ok",
        ),
        Event(
            ts="2026-01-24T10:05:00",
            cmd="resume",
            task_id="bd-1234",
            result="error",
        ),
    ]

    filters = EventFilters(task_id="bd-a3f8")
    filtered = _apply_filters(events, filters)

    assert len(filtered) == 1
    assert filtered[0].task_id == "bd-a3f8"


def test_apply_filters_status():
    """Test _apply_filters with status filter."""
    events = [
        Event(
            ts="2026-01-24T10:00:00",
            cmd="queue",
            task_id="bd-a3f8",
            result="ok",
        ),
        Event(
            ts="2026-01-24T10:05:00",
            cmd="resume",
            task_id="bd-1234",
            result="error",
        ),
    ]

    filters = EventFilters(status="ok")
    filtered = _apply_filters(events, filters)

    assert len(filtered) == 1
    assert filtered[0].result == "ok"


def test_apply_filters_since():
    """Test _apply_filters with since filter."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=1)

    events = [
        Event(
            ts=(now - timedelta(hours=2)).isoformat(),
            cmd="queue",
            task_id="bd-a3f8",
            result="ok",
        ),
        Event(
            ts=(now - timedelta(minutes=30)).isoformat(),
            cmd="resume",
            task_id="bd-1234",
            result="error",
        ),
    ]

    filters = EventFilters(since=since)
    filtered = _apply_filters(events, filters)

    assert len(filtered) == 1
    assert filtered[0].task_id == "bd-1234"


def test_apply_filters_no_filters():
    """Test _apply_filters with no filters returns all events."""
    events = [
        Event(
            ts="2026-01-24T10:00:00",
            cmd="queue",
            task_id="bd-a3f8",
            result="ok",
        ),
        Event(
            ts="2026-01-24T10:05:00",
            cmd="resume",
            task_id="bd-1234",
            result="error",
        ),
    ]

    filters = EventFilters()
    filtered = _apply_filters(events, filters)

    assert len(filtered) == 2


def test_parse_timestamp_valid():
    """Test _parse_timestamp with valid ISO string."""
    ts = "2026-01-24T10:00:00"
    result = _parse_timestamp(ts)

    assert result is not None
    assert result.year == 2026
    assert result.month == 1
    assert result.day == 24
    assert result.hour == 10


def test_parse_timestamp_with_timezone():
    """Test _parse_timestamp with timezone."""
    ts = "2026-01-24T10:00:00+00:00"
    result = _parse_timestamp(ts)

    assert result is not None
    assert result.tzinfo is not None


def test_parse_timestamp_invalid():
    """Test _parse_timestamp with invalid string."""
    result = _parse_timestamp("invalid-timestamp")

    assert result is None


def test_render_table_with_events():
    """Test _render_table renders events."""
    events = [
        Event(
            ts="2026-01-24T10:00:00",
            cmd="queue",
            task_id="bd-a3f8",
            pane="%12",
            result="ok",
            error=None,
        )
    ]

    result = QueryResult(
        events=events,
        total_count=10,
        filtered_count=1,
        query_time="2026-01-24T10:00:00",
    )

    table = _render_table(result)

    assert "TS" in table
    assert "CMD" in table
    assert "queue" in table
    assert "bd-a3f8" in table
    assert "Showing 1/10 events" in table


def test_render_table_with_error():
    """Test _render_table with error event."""
    events = [
        Event(
            ts="2026-01-24T10:00:00",
            cmd="queue",
            task_id="bd-a3f8",
            pane="%12",
            result="error",
            error="Task failed to complete",
        )
    ]

    result = QueryResult(
        events=events,
        total_count=1,
        filtered_count=1,
        query_time="2026-01-24T10:00:00",
    )

    table = _render_table(result)

    assert "Task failed to complete" in table
    assert "error" in table


def test_render_table_empty():
    """Test _render_table with no events."""
    result = QueryResult(
        events=[],
        total_count=0,
        filtered_count=0,
        query_time="2026-01-24T10:00:00",
    )

    table = _render_table(result)

    assert table == "No events found matching filters"


def test_query_result_to_dict():
    """Test query_result_to_dict converts to JSON dict."""
    events = [
        Event(
            ts="2026-01-24T10:00:00",
            cmd="queue",
            task_id="bd-a3f8",
            pane="%12",
            result="ok",
        )
    ]

    result = QueryResult(
        events=events,
        total_count=1,
        filtered_count=1,
        query_time="2026-01-24T10:00:00",
    )

    result_dict = query_result_to_dict(result)

    assert isinstance(result_dict, dict)
    assert "events" in result_dict
    assert "total_count" in result_dict
    assert "filtered_count" in result_dict
    assert "query_time" in result_dict
    assert result_dict["total_count"] == 1
    assert len(result_dict["events"]) == 1


def test_query_result_to_json():
    """Test query_result_to_json converts to JSON string."""
    events = [
        Event(
            ts="2026-01-24T10:00:00",
            cmd="queue",
            task_id="bd-a3f8",
            pane="%12",
            result="ok",
        )
    ]

    result = QueryResult(
        events=events,
        total_count=1,
        filtered_count=1,
        query_time="2026-01-24T10:00:00",
    )

    json_str = query_result_to_json(result)

    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)
    assert parsed["total_count"] == 1
    assert len(parsed["events"]) == 1


def test_query_result_json_sort_keys():
    """Test query_result_to_json uses sorted keys."""
    events = [Event(ts="2026-01-24T10:00:00", cmd="queue")]

    result = QueryResult(
        events=events,
        total_count=1,
        filtered_count=1,
        query_time="2026-01-24T10:00:00",
    )

    json_str = query_result_to_json(result)
    parsed = json.loads(json_str)

    event_keys = list(parsed["events"][0].keys())
    assert event_keys == sorted(event_keys)
