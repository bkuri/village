"""Tests for release queue management."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from village.release import (
    BumpType,
    PendingBump,
    ReleaseQueue,
    ReleaseRecord,
    aggregate_bumps,
    clear_pending_bumps,
    format_release_dashboard,
    get_pending_bumps,
    get_release_history,
    queue_bump,
    record_release,
    scope_to_bump,
)


@pytest.fixture
def tmp_village_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create temporary village directory."""
    village_path = tmp_path / ".village"
    village_path.mkdir(parents=True)

    class MockConfig:
        village_dir = village_path

    monkeypatch.setattr("village.release.get_config", lambda: MockConfig())
    return village_path


class TestScopeToBump:
    """Tests for scope_to_bump function."""

    def test_fix_scope_returns_patch(self) -> None:
        assert scope_to_bump("fix") == "patch"

    def test_feature_scope_returns_minor(self) -> None:
        assert scope_to_bump("feature") == "minor"

    def test_docs_scope_returns_none(self) -> None:
        assert scope_to_bump("docs") == "none"

    def test_test_scope_returns_none(self) -> None:
        assert scope_to_bump("test") == "none"

    def test_refactor_scope_returns_none(self) -> None:
        assert scope_to_bump("refactor") == "none"

    def test_config_scope_returns_patch(self) -> None:
        assert scope_to_bump("config") == "patch"

    def test_unknown_scope_returns_none(self) -> None:
        assert scope_to_bump("unknown") == "none"


class TestAggregateBumps:
    """Tests for aggregate_bumps function."""

    def test_empty_list_returns_none(self) -> None:
        assert aggregate_bumps([]) == "none"

    def test_single_patch(self) -> None:
        assert aggregate_bumps(["patch"]) == "patch"

    def test_single_minor(self) -> None:
        assert aggregate_bumps(["minor"]) == "minor"

    def test_single_major(self) -> None:
        assert aggregate_bumps(["major"]) == "major"

    def test_major_wins_over_minor(self) -> None:
        assert aggregate_bumps(["minor", "major"]) == "major"
        assert aggregate_bumps(["major", "minor"]) == "major"

    def test_minor_wins_over_patch(self) -> None:
        assert aggregate_bumps(["patch", "minor"]) == "minor"
        assert aggregate_bumps(["minor", "patch"]) == "minor"

    def test_multiple_patches(self) -> None:
        assert aggregate_bumps(["patch", "patch", "patch"]) == "patch"

    def test_mixed_with_none(self) -> None:
        assert aggregate_bumps(["none", "patch", "none"]) == "patch"

    def test_all_none(self) -> None:
        assert aggregate_bumps(["none", "none"]) == "none"


class TestQueueBump:
    """Tests for queue_bump function."""

    def test_queue_single_bump(self, tmp_village_dir: Path) -> None:
        queue_bump("bd-a3f8", "minor", "Test task")

        bumps = get_pending_bumps()
        assert len(bumps) == 1
        assert bumps[0].task_id == "bd-a3f8"
        assert bumps[0].bump == "minor"
        assert bumps[0].title == "Test task"

    def test_queue_multiple_bumps(self, tmp_village_dir: Path) -> None:
        queue_bump("bd-a3f8", "minor", "Task 1")
        queue_bump("bd-b4e2", "patch", "Task 2")
        queue_bump("bd-c5d9", "major", "Task 3")

        bumps = get_pending_bumps()
        assert len(bumps) == 3

        task_ids = [b.task_id for b in bumps]
        assert "bd-a3f8" in task_ids
        assert "bd-b4e2" in task_ids
        assert "bd-c5d9" in task_ids


class TestClearPendingBumps:
    """Tests for clear_pending_bumps function."""

    def test_clear_returns_task_ids(self, tmp_village_dir: Path) -> None:
        queue_bump("bd-a3f8", "minor", "Task 1")
        queue_bump("bd-b4e2", "patch", "Task 2")

        cleared = clear_pending_bumps()
        assert len(cleared) == 2
        assert "bd-a3f8" in cleared
        assert "bd-b4e2" in cleared

        bumps = get_pending_bumps()
        assert len(bumps) == 0

    def test_clear_empty_queue(self, tmp_village_dir: Path) -> None:
        cleared = clear_pending_bumps()
        assert cleared == []


class TestRecordRelease:
    """Tests for record_release function."""

    def test_record_single_release(self, tmp_village_dir: Path) -> None:
        record = ReleaseRecord(
            version="1.2.0",
            released_at=datetime.now(timezone.utc),
            aggregate_bump="minor",
            tasks=["bd-a3f8", "bd-b4e2"],
            changelog_entry="### Added\n- New feature",
        )

        record_release(record)

        history = get_release_history()
        assert len(history) == 1
        assert history[0].version == "1.2.0"
        assert history[0].aggregate_bump == "minor"
        assert len(history[0].tasks) == 2

    def test_record_multiple_releases(self, tmp_village_dir: Path) -> None:
        for i, (version, bump) in enumerate([("1.0.0", "patch"), ("1.1.0", "minor")]):
            record = ReleaseRecord(
                version=version,
                released_at=datetime.now(timezone.utc),
                aggregate_bump=bump,
                tasks=[f"bd-{i}"],
                changelog_entry="",
            )
            record_release(record)

        history = get_release_history()
        assert len(history) == 2


class TestFormatReleaseDashboard:
    """Tests for format_release_dashboard function."""

    def test_empty_dashboard(self) -> None:
        output = format_release_dashboard([], [], [])
        assert "No pending releases" in output

    def test_dashboard_with_pending(self) -> None:
        pending = [
            PendingBump(
                task_id="bd-a3f8",
                bump="minor",
                completed_at=datetime.now(timezone.utc),
                title="Test task",
            )
        ]

        output = format_release_dashboard([], pending, [])
        assert "Pending Release" in output
        assert "bd-a3f8" in output
        assert "minor" in output

    def test_dashboard_with_history(self) -> None:
        history = [
            ReleaseRecord(
                version="1.2.0",
                released_at=datetime.now(timezone.utc),
                aggregate_bump="minor",
                tasks=["bd-a3f8"],
                changelog_entry="",
            )
        ]

        output = format_release_dashboard(history, [], [])
        assert "Last Releases" in output
        assert "1.2.0" in output

    def test_dashboard_with_open_tasks(self) -> None:
        open_tasks = [
            {
                "task_id": "bd-a3f8",
                "title": "Test task",
                "bump": "minor",
                "status": "open",
            }
        ]

        output = format_release_dashboard([], [], open_tasks)
        assert "Open Tasks with Bump Labels" in output
        assert "bd-a3f8" in output
