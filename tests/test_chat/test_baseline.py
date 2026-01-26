"""Unit tests for baseline collection functionality."""

import re
from time import sleep

from village.chat.baseline import BaselineReport, generate_batch_id


def test_generate_batch_id_returns_string() -> None:
    """Test that generate_batch_id returns a string."""
    session_id = "test-session-123"
    batch_id = generate_batch_id(session_id)
    assert isinstance(batch_id, str)


def test_generate_batch_id_unique_ids() -> None:
    """Test that different calls produce different IDs."""
    session_id = "test-session-123"
    batch_id_1 = generate_batch_id(session_id)
    sleep(1.1)  # Delay to ensure different second-based timestamps
    batch_id_2 = generate_batch_id(session_id)

    assert batch_id_1 != batch_id_2


def test_generate_batch_id_format() -> None:
    """Test that IDs follow expected format (batch-{session_id}-{timestamp})."""
    session_id = "test-session-123"
    batch_id = generate_batch_id(session_id)

    # Format: batch-{session_id}-{YYYYMMDD-HHMMSS}
    pattern = r"^batch-test-session-123-\d{8}-\d{6}$"
    assert re.match(pattern, batch_id)


def test_generate_batch_id_with_different_sessions() -> None:
    """Test generate_batch_id with different session IDs."""
    session_1 = "session-1"
    session_2 = "session-2"

    batch_id_1 = generate_batch_id(session_1)
    batch_id_2 = generate_batch_id(session_2)

    assert session_1 in batch_id_1
    assert session_2 in batch_id_2
    assert batch_id_1 != batch_id_2


def test_baseline_report_creation_with_all_fields() -> None:
    """Test creating a BaselineReport with all fields."""
    title = "Build a web application"
    reasoning = "Need to break down into manageable tasks"
    parent_task_id = "bd-a1b2c3d"
    tags = ["frontend", "backend", "api"]

    report = BaselineReport(
        title=title,
        reasoning=reasoning,
        parent_task_id=parent_task_id,
        tags=tags,
    )

    assert report.title == title
    assert report.reasoning == reasoning
    assert report.parent_task_id == parent_task_id
    assert report.tags == tags


def test_baseline_report_defaults() -> None:
    """Test BaselineReport with only required fields."""
    title = "Build a CLI tool"
    reasoning = "Complex project needs breakdown"

    report = BaselineReport(
        title=title,
        reasoning=reasoning,
    )

    assert report.title == title
    assert report.reasoning == reasoning
    assert report.parent_task_id is None
    assert report.tags == []


def test_baseline_report_empty_tags() -> None:
    """Test BaselineReport with empty tags list."""
    title = "Test project"
    reasoning = "Testing purposes"
    tags: list[str] = []

    report = BaselineReport(
        title=title,
        reasoning=reasoning,
        parent_task_id=None,
        tags=tags,
    )

    assert report.tags == []
    assert report.parent_task_id is None


def test_baseline_report_with_tags() -> None:
    """Test BaselineReport with multiple tags."""
    title = "Database migration"
    reasoning = "Need to plan data transfer"
    tags = ["database", "migration", "postgres"]

    report = BaselineReport(
        title=title,
        reasoning=reasoning,
        tags=tags,
    )

    tags_list = report.tags or []
    assert len(tags_list) == 3
    assert "database" in tags_list
    assert "migration" in tags_list
    assert "postgres" in tags_list
