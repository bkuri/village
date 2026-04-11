"""Test agent event parsing for completion detection."""

import json
from pathlib import Path

from village.agent_events import check_agent_completion, parse_agent_events


def test_parse_events_file_not_found(tmp_path: Path):
    result = parse_agent_events(tmp_path / "nonexistent.jsonl")
    assert result is None


def test_parse_events_empty_file(tmp_path: Path):
    trace = tmp_path / "bd-test-agent.jsonl"
    trace.write_text("")
    result = parse_agent_events(trace)
    assert result is None


def test_parse_events_tool_calls(tmp_path: Path):
    trace = tmp_path / "bd-test-agent.jsonl"
    events = [
        {"type": "tool_call", "tool": "read", "path": "foo.py"},
        {"type": "tool_call", "tool": "write", "path": "bar.py"},
    ]
    trace.write_text("\n".join(json.dumps(e) for e in events))
    result = parse_agent_events(trace)
    assert result is not None
    assert result.tool_calls == 2
    assert result.completed is False
    assert result.success is True


def test_parse_events_completion(tmp_path: Path):
    trace = tmp_path / "bd-test-agent.jsonl"
    events = [
        {"type": "tool_call", "tool": "read"},
        {"type": "result", "content": "done"},
    ]
    trace.write_text("\n".join(json.dumps(e) for e in events))
    result = parse_agent_events(trace)
    assert result is not None
    assert result.completed is True
    assert result.success is True


def test_parse_events_error(tmp_path: Path):
    trace = tmp_path / "bd-test-agent.jsonl"
    events = [
        {"type": "error", "message": "something went wrong"},
    ]
    trace.write_text("\n".join(json.dumps(e) for e in events))
    result = parse_agent_events(trace)
    assert result is not None
    assert result.success is False
    assert result.error == "something went wrong"


def test_parse_events_mixed(tmp_path: Path):
    trace = tmp_path / "bd-test-agent.jsonl"
    lines = [
        json.dumps({"type": "tool_call", "tool": "read"}),
        "not json",
        json.dumps({"type": "tool_call", "tool": "write"}),
        json.dumps({"type": "done"}),
    ]
    trace.write_text("\n".join(lines))
    result = parse_agent_events(trace)
    assert result is not None
    assert result.events_parsed == 3
    assert result.tool_calls == 2
    assert result.completed is True


def test_check_agent_completion(tmp_path: Path):
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    trace = traces_dir / "bd-abc-agent.jsonl"
    trace.write_text(json.dumps({"type": "done"}))
    result = check_agent_completion("bd-abc", traces_dir)
    assert result is not None
    assert result.completed is True
    assert result.task_id == "bd-abc"


def test_check_agent_completion_not_found(tmp_path: Path):
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    result = check_agent_completion("bd-missing", traces_dir)
    assert result is None
