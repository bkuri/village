"""Event query module for filtering and querying events.log."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from village.event_log import Event, read_events

logger = logging.getLogger(__name__)


@dataclass
class EventFilters:
    """Filters for event queries."""

    task_id: str | None = None
    status: str | None = None
    since: datetime | None = None
    last: timedelta | None = None


@dataclass
class QueryResult:
    """Result of event query."""

    events: list[Event]
    total_count: int
    filtered_count: int
    query_time: str


def query_events(
    filters: EventFilters,
    format: Literal["json", "table"],
    config_path: Path,
) -> QueryResult | str:
    """
    Query events from log with optional filters.

    Args:
        filters: Event filters to apply
        format: Output format ("json" or "table")
        config_path: Path to village directory

    Returns:
        QueryResult if format is "json", formatted table string if format is "table"

    Raises:
        IOError: If unable to read event log
    """
    events = read_events(config_path)
    query_time = datetime.now(timezone.utc).isoformat()

    filtered_events = _apply_filters(events, filters)

    result = QueryResult(
        events=filtered_events,
        total_count=len(events),
        filtered_count=len(filtered_events),
        query_time=query_time,
    )

    if format == "json":
        return result
    else:
        return _render_table(result)


def _apply_filters(events: list[Event], filters: EventFilters) -> list[Event]:
    """
    Apply filters to event list.

    Args:
        events: List of events to filter
        filters: Filters to apply

    Returns:
        Filtered list of events
    """
    filtered = events

    if filters.task_id:
        filtered = [e for e in filtered if e.task_id == filters.task_id]

    if filters.status:
        filtered = [e for e in filtered if e.result == filters.status]

    if filters.since:
        try:
            since_dt = filters.since
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)

            filtered = [
                e
                for e in filtered
                if (event_ts := _parse_timestamp(e.ts)) is not None and event_ts >= since_dt
            ]
        except (ValueError, AttributeError) as e:
            logger.warning(f"Invalid 'since' filter: {e}")

    if filters.last:
        try:
            cutoff_time = datetime.now(timezone.utc) - filters.last
            filtered = [
                e
                for e in filtered
                if (event_ts := _parse_timestamp(e.ts)) is not None and event_ts >= cutoff_time
            ]
        except (ValueError, AttributeError) as e:
            logger.warning(f"Invalid 'last' filter: {e}")

    return filtered


def _parse_timestamp(ts: str) -> datetime | None:
    """
    Parse ISO timestamp string to datetime.

    Args:
        ts: ISO timestamp string

    Returns:
        Datetime object or None if parsing fails
    """
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


def _render_table(result: QueryResult) -> str:
    """
    Render query result as formatted table.

    Args:
        result: Query result to render

    Returns:
        Formatted table string
    """
    if not result.events:
        return "No events found matching filters"

    headers = ["TS", "CMD", "TASK_ID", "PANE", "RESULT", "ERROR"]
    rows = []

    for event in result.events:
        rows.append(
            [
                event.ts[:19],
                event.cmd,
                event.task_id or "-",
                event.pane or "-",
                event.result or "-",
                (event.error or "-")[:30],
            ]
        )

    col_widths = [max(len(str(row[i])) for row in [headers] + rows) for i in range(len(headers))]

    separator = "  "
    lines = []

    header_line = separator.join(f"{headers[i]:<{col_widths[i]}}" for i in range(len(headers)))
    lines.append(header_line)

    separator_line = separator.join("-" * col_widths[i] for i in range(len(headers)))
    lines.append(separator_line)

    for row in rows:
        row_line = separator.join(f"{str(row[i]):<{col_widths[i]}}" for i in range(len(row)))
        lines.append(row_line)

    lines.append("")
    lines.append(f"Showing {result.filtered_count}/{result.total_count} events")
    lines.append(f"Query time: {result.query_time}")

    return "\n".join(lines)


def query_result_to_dict(result: QueryResult) -> dict[str, object]:
    """
    Convert QueryResult to JSON-serializable dict.

    Args:
        result: Query result to convert

    Returns:
        JSON-serializable dict
    """
    return {
        "events": [
            {
                "ts": e.ts,
                "cmd": e.cmd,
                "task_id": e.task_id,
                "pane": e.pane,
                "result": e.result,
                "error": e.error,
            }
            for e in result.events
        ],
        "total_count": result.total_count,
        "filtered_count": result.filtered_count,
        "query_time": result.query_time,
    }


def query_result_to_json(result: QueryResult) -> str:
    """
    Convert QueryResult to JSON string.

    Args:
        result: Query result to convert

    Returns:
        JSON string
    """
    return json.dumps(query_result_to_dict(result), sort_keys=True)
