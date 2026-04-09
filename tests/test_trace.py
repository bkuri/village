"""Test structured trace system."""

import json
from pathlib import Path

import click.testing
import pytest

from village.cli import village
from village.config import Config
from village.trace import (
    TraceEvent,
    TraceEventType,
    TraceReader,
    TraceWriter,
    format_trace,
)


@pytest.fixture
def traces_dir(tmp_path: Path) -> Path:
    d = tmp_path / "traces"
    d.mkdir()
    return d


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    return Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )


@pytest.fixture
def runner() -> click.testing.CliRunner:
    return click.testing.CliRunner()


class TestTraceWriter:
    def test_record_creates_file(self, traces_dir: Path) -> None:
        writer = TraceWriter("bd-a3f8", traces_dir)
        writer.record(TraceEventType.TASK_CHECKOUT, agent="build", pane_id="%12")

        trace_path = traces_dir / "bd-a3f8.jsonl"
        assert trace_path.exists()

    def test_record_appends_events(self, traces_dir: Path) -> None:
        writer = TraceWriter("bd-a3f8", traces_dir)
        writer.record(TraceEventType.TASK_CHECKOUT, agent="build")
        writer.record(TraceEventType.TOOL_CALL, agent="build", tool="edit")

        trace_path = traces_dir / "bd-a3f8.jsonl"
        lines = trace_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    def test_record_sequence_increments(self, traces_dir: Path) -> None:
        writer = TraceWriter("bd-a3f8", traces_dir)
        writer.record(TraceEventType.TASK_CHECKOUT, agent="build")
        writer.record(TraceEventType.DECISION, agent="build")
        writer.record(TraceEventType.FILE_MODIFIED, agent="build")

        reader = TraceReader(traces_dir)
        events = reader.read("bd-a3f8")
        assert events[0].sequence == 1
        assert events[1].sequence == 2
        assert events[2].sequence == 3

    def test_record_event_type_stored(self, traces_dir: Path) -> None:
        writer = TraceWriter("bd-a3f8", traces_dir)
        writer.record(TraceEventType.ERROR, agent="build", message="boom")

        trace_path = traces_dir / "bd-a3f8.jsonl"
        raw = json.loads(trace_path.read_text(encoding="utf-8").strip())
        assert raw["event_type"] == "error"
        assert raw["data"]["message"] == "boom"

    def test_record_data_kwargs(self, traces_dir: Path) -> None:
        writer = TraceWriter("bd-a3f8", traces_dir)
        writer.record(
            TraceEventType.TOOL_CALL,
            agent="build",
            tool="edit",
            file="main.py",
            lines_changed=5,
        )

        trace_path = traces_dir / "bd-a3f8.jsonl"
        raw = json.loads(trace_path.read_text(encoding="utf-8").strip())
        assert raw["data"]["tool"] == "edit"
        assert raw["data"]["file"] == "main.py"
        assert raw["data"]["lines_changed"] == 5

    def test_record_timestamp_present(self, traces_dir: Path) -> None:
        writer = TraceWriter("bd-a3f8", traces_dir)
        writer.record(TraceEventType.TASK_CHECKOUT, agent="build")

        trace_path = traces_dir / "bd-a3f8.jsonl"
        raw = json.loads(trace_path.read_text(encoding="utf-8").strip())
        assert "T" in raw["timestamp"]

    def test_record_creates_traces_dir(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "new_traces"
        writer = TraceWriter("bd-a3f8", new_dir)
        writer.record(TraceEventType.TASK_CHECKOUT, agent="build")

        assert new_dir.exists()
        assert (new_dir / "bd-a3f8.jsonl").exists()


class TestTraceReader:
    def test_read_empty_missing_file(self, traces_dir: Path) -> None:
        reader = TraceReader(traces_dir)
        events = reader.read("bd-nonexistent")
        assert events == []

    def test_read_returns_events(self, traces_dir: Path) -> None:
        writer = TraceWriter("bd-a3f8", traces_dir)
        writer.record(TraceEventType.TASK_CHECKOUT, agent="build")
        writer.record(TraceEventType.TASK_COMPLETE, agent="build")

        reader = TraceReader(traces_dir)
        events = reader.read("bd-a3f8")
        assert len(events) == 2
        assert events[0].event_type == TraceEventType.TASK_CHECKOUT
        assert events[1].event_type == TraceEventType.TASK_COMPLETE

    def test_read_skips_blank_lines(self, traces_dir: Path) -> None:
        trace_path = traces_dir / "bd-a3f8.jsonl"
        writer = TraceWriter("bd-a3f8", traces_dir)
        writer.record(TraceEventType.TASK_CHECKOUT, agent="build")

        with open(trace_path, "a", encoding="utf-8") as f:
            f.write("\n\n")

        reader = TraceReader(traces_dir)
        events = reader.read("bd-a3f8")
        assert len(events) == 1

    def test_read_skips_corrupted_lines(self, traces_dir: Path) -> None:
        trace_path = traces_dir / "bd-a3f8.jsonl"
        writer = TraceWriter("bd-a3f8", traces_dir)
        writer.record(TraceEventType.TASK_CHECKOUT, agent="build")

        with open(trace_path, "a", encoding="utf-8") as f:
            f.write("not json\n")

        reader = TraceReader(traces_dir)
        events = reader.read("bd-a3f8")
        assert len(events) == 1

    def test_list_traced_tasks(self, traces_dir: Path) -> None:
        writer_a = TraceWriter("bd-a3f8", traces_dir)
        writer_a.record(TraceEventType.TASK_CHECKOUT, agent="build")

        writer_b = TraceWriter("bd-b7d2", traces_dir)
        writer_b.record(TraceEventType.TASK_CHECKOUT, agent="test")

        reader = TraceReader(traces_dir)
        task_ids = reader.list_traced_tasks()
        assert task_ids == ["bd-a3f8", "bd-b7d2"]

    def test_list_traced_tasks_empty(self, tmp_path: Path) -> None:
        reader = TraceReader(tmp_path / "nonexistent")
        task_ids = reader.list_traced_tasks()
        assert task_ids == []

    def test_read_event_fields(self, traces_dir: Path) -> None:
        writer = TraceWriter("bd-a3f8", traces_dir)
        writer.record(TraceEventType.TASK_CHECKOUT, agent="build", pane_id="%12")

        reader = TraceReader(traces_dir)
        events = reader.read("bd-a3f8")
        assert len(events) == 1
        event = events[0]
        assert event.task_id == "bd-a3f8"
        assert event.agent == "build"
        assert event.data["pane_id"] == "%12"
        assert event.sequence == 1


class TestFormatTrace:
    def test_format_empty(self) -> None:
        result = format_trace([])
        assert result == "No trace events"

    def test_format_single_event(self) -> None:
        events = [
            TraceEvent(
                timestamp="2026-01-22T10:41:12+00:00",
                event_type=TraceEventType.TASK_CHECKOUT,
                task_id="bd-a3f8",
                agent="build",
                data={"pane_id": "%12"},
                sequence=1,
            )
        ]
        result = format_trace(events)
        assert "[1]" in result
        assert "task_checkout" in result
        assert "agent=build" in result
        assert "pane_id=%12" in result

    def test_format_multiple_events(self) -> None:
        events = [
            TraceEvent(
                timestamp="2026-01-22T10:41:12+00:00",
                event_type=TraceEventType.TASK_CHECKOUT,
                task_id="bd-a3f8",
                agent="build",
                data={},
                sequence=1,
            ),
            TraceEvent(
                timestamp="2026-01-22T10:42:00+00:00",
                event_type=TraceEventType.FILE_MODIFIED,
                task_id="bd-a3f8",
                agent="build",
                data={"file": "main.py"},
                sequence=2,
            ),
        ]
        result = format_trace(events)
        lines = result.splitlines()
        assert len(lines) == 2
        assert "[1]" in lines[0]
        assert "[2]" in lines[1]

    def test_format_no_agent_omits_field(self) -> None:
        events = [
            TraceEvent(
                timestamp="2026-01-22T10:41:12+00:00",
                event_type=TraceEventType.ERROR,
                task_id="bd-a3f8",
                agent="",
                data={"message": "fail"},
                sequence=1,
            )
        ]
        result = format_trace(events)
        assert "agent=" not in result

    def test_format_no_data_omits_field(self) -> None:
        events = [
            TraceEvent(
                timestamp="2026-01-22T10:41:12+00:00",
                event_type=TraceEventType.TASK_COMPLETE,
                task_id="bd-a3f8",
                agent="build",
                data={},
                sequence=1,
            )
        ]
        result = format_trace(events)
        assert "[1]" in result
        assert "task_complete" in result


class TestTraceCLI:
    def test_trace_show_text(self, runner: click.testing.CliRunner, mock_config: Config) -> None:
        writer = TraceWriter("bd-a3f8", mock_config.traces_dir)
        writer.record(TraceEventType.TASK_CHECKOUT, agent="build")

        from unittest.mock import patch

        with patch("village.cli.ledger.get_config", return_value=mock_config):
            result = runner.invoke(village, ["trace", "show", "bd-a3f8"])
            assert result.exit_code == 0
            assert "task_checkout" in result.output

    def test_trace_show_json(self, runner: click.testing.CliRunner, mock_config: Config) -> None:
        writer = TraceWriter("bd-a3f8", mock_config.traces_dir)
        writer.record(TraceEventType.TASK_CHECKOUT, agent="build")

        from unittest.mock import patch

        with patch("village.cli.ledger.get_config", return_value=mock_config):
            result = runner.invoke(village, ["trace", "show", "bd-a3f8", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert len(data) == 1
            assert data[0]["event_type"] == "task_checkout"

    def test_trace_show_missing_task(self, runner: click.testing.CliRunner, mock_config: Config) -> None:
        from unittest.mock import patch

        with patch("village.cli.ledger.get_config", return_value=mock_config):
            result = runner.invoke(village, ["trace", "show", "bd-nonexistent"])
            assert result.exit_code != 0
            assert "No ledger events" in result.output

    def test_trace_list_text(self, runner: click.testing.CliRunner, mock_config: Config) -> None:
        writer = TraceWriter("bd-a3f8", mock_config.traces_dir)
        writer.record(TraceEventType.TASK_CHECKOUT, agent="build")

        writer2 = TraceWriter("bd-b7d2", mock_config.traces_dir)
        writer2.record(TraceEventType.TASK_CHECKOUT, agent="test")

        from unittest.mock import patch

        with patch("village.cli.ledger.get_config", return_value=mock_config):
            result = runner.invoke(village, ["trace", "list"])
            assert result.exit_code == 0
            assert "bd-a3f8" in result.output
            assert "bd-b7d2" in result.output

    def test_trace_list_json(self, runner: click.testing.CliRunner, mock_config: Config) -> None:
        writer = TraceWriter("bd-a3f8", mock_config.traces_dir)
        writer.record(TraceEventType.TASK_CHECKOUT, agent="build")

        from unittest.mock import patch

        with patch("village.cli.ledger.get_config", return_value=mock_config):
            result = runner.invoke(village, ["trace", "list", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "bd-a3f8" in data

    def test_trace_list_empty(self, runner: click.testing.CliRunner, mock_config: Config) -> None:
        from unittest.mock import patch

        with patch("village.cli.ledger.get_config", return_value=mock_config):
            result = runner.invoke(village, ["trace", "list"])
            assert result.exit_code == 0
            assert "No ledgers found" in result.output
