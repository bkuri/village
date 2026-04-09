"""Test builder state tracking for workflow runs."""

import json
import threading
from pathlib import Path

from village.builder_state import (
    RunManifest,
    RunState,
    RunStatus,
    RunStepEvent,
    StepEventType,
    generate_run_id,
)


def test_create_run_creates_manifest_file(tmp_path: Path):
    """Test that create_run writes a manifest JSON file."""
    state = RunState(tmp_path / "runs")
    manifest = state.create_run("run-abc1", "build", steps_total=3)

    assert (tmp_path / "runs" / "run-abc1.json").exists()
    assert manifest.run_id == "run-abc1"
    assert manifest.workflow_name == "build"
    assert manifest.status == RunStatus.PENDING
    assert manifest.started_at != ""


def test_create_run_with_inputs_and_steps_total(tmp_path: Path):
    """Test create_run stores inputs and steps_total."""
    state = RunState(tmp_path / "runs")
    inputs = {"repo": "myrepo", "branch": "main"}
    manifest = state.create_run("run-abc2", "deploy", inputs=inputs, steps_total=5)

    assert manifest.inputs == inputs
    assert manifest.steps_total == 5
    assert manifest.steps_completed == 0
    assert manifest.current_step == ""


def test_get_run_returns_manifest(tmp_path: Path):
    """Test get_run reads back a persisted manifest."""
    state = RunState(tmp_path / "runs")
    state.create_run("run-abc3", "test")

    manifest = state.get_run("run-abc3")

    assert manifest is not None
    assert manifest.run_id == "run-abc3"
    assert manifest.workflow_name == "test"


def test_get_run_returns_none_for_missing(tmp_path: Path):
    """Test get_run returns None when run does not exist."""
    state = RunState(tmp_path / "runs")

    assert state.get_run("run-nonexistent") is None


def test_update_status_changes_status(tmp_path: Path):
    """Test update_status persists the new status."""
    state = RunState(tmp_path / "runs")
    state.create_run("run-abc4", "build")

    manifest = state.update_status("run-abc4", RunStatus.RUNNING)

    assert manifest is not None
    assert manifest.status == RunStatus.RUNNING

    # Verify persisted
    reloaded = state.get_run("run-abc4")
    assert reloaded is not None
    assert reloaded.status == RunStatus.RUNNING


def test_update_status_sets_completed_at_for_terminal_states(tmp_path: Path):
    """Test completed_at is set for COMPLETED, FAILED, and STOPPED."""
    state = RunState(tmp_path / "runs")

    for status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.STOPPED):
        run_id = f"run-{status.value}"
        state.create_run(run_id, "build")
        manifest = state.update_status(run_id, status)

        assert manifest is not None
        assert manifest.completed_at != ""


def test_update_status_no_completed_at_for_non_terminal(tmp_path: Path):
    """Test completed_at is not set for PENDING or RUNNING."""
    state = RunState(tmp_path / "runs")
    state.create_run("run-abc5", "build")

    manifest = state.update_status("run-abc5", RunStatus.RUNNING)

    assert manifest is not None
    assert manifest.completed_at == ""


def test_update_status_returns_none_for_missing(tmp_path: Path):
    """Test update_status returns None for nonexistent run."""
    state = RunState(tmp_path / "runs")

    assert state.update_status("run-missing", RunStatus.RUNNING) is None


def test_advance_step_increments_steps_completed(tmp_path: Path):
    """Test advance_step increments steps_completed and sets current_step."""
    state = RunState(tmp_path / "runs")
    state.create_run("run-abc6", "build", steps_total=3)

    manifest = state.advance_step("run-abc6", "checkout")

    assert manifest is not None
    assert manifest.steps_completed == 1
    assert manifest.current_step == "checkout"

    state.advance_step("run-abc6", "compile")
    reloaded = state.get_run("run-abc6")
    assert reloaded is not None
    assert reloaded.steps_completed == 2
    assert reloaded.current_step == "compile"


def test_advance_step_returns_none_for_missing(tmp_path: Path):
    """Test advance_step returns None for nonexistent run."""
    state = RunState(tmp_path / "runs")

    assert state.advance_step("run-missing", "step1") is None


def test_append_step_event_creates_jsonl(tmp_path: Path):
    """Test append_step_event creates a JSONL file with correct content."""
    state = RunState(tmp_path / "runs")
    state.create_run("run-abc7", "build")

    event = RunStepEvent(
        timestamp="2026-04-09T10:00:00Z",
        event_type=StepEventType.STEP_START,
        step_name="checkout",
        sequence=1,
    )
    state.append_step_event("run-abc7", event)

    events_path = tmp_path / "runs" / "run-abc7.jsonl"
    assert events_path.exists()

    line = events_path.read_text(encoding="utf-8").strip()
    data = json.loads(line)
    assert data["event_type"] == "step_start"
    assert data["step_name"] == "checkout"
    assert data["sequence"] == 1


def test_append_step_event_appends_multiple(tmp_path: Path):
    """Test append_step_event appends multiple events to the same file."""
    state = RunState(tmp_path / "runs")
    state.create_run("run-abc8", "build")

    for i, step in enumerate(["checkout", "compile", "test"]):
        event = RunStepEvent(
            timestamp=f"2026-04-09T10:0{i}:00Z",
            event_type=StepEventType.STEP_START,
            step_name=step,
            sequence=i,
        )
        state.append_step_event("run-abc8", event)

    events_path = tmp_path / "runs" / "run-abc8.jsonl"
    lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3


def test_get_events_reads_all_events_back(tmp_path: Path):
    """Test get_events returns all events in order."""
    state = RunState(tmp_path / "runs")
    state.create_run("run-abc9", "build")

    state.append_step_event(
        "run-abc9",
        RunStepEvent(
            timestamp="2026-04-09T10:00:00Z",
            event_type=StepEventType.STEP_START,
            step_name="checkout",
            sequence=0,
        ),
    )
    state.append_step_event(
        "run-abc9",
        RunStepEvent(
            timestamp="2026-04-09T10:01:00Z",
            event_type=StepEventType.STEP_COMPLETE,
            step_name="checkout",
            output="done",
            sequence=1,
        ),
    )

    events = state.get_events("run-abc9")

    assert len(events) == 2
    assert events[0].step_name == "checkout"
    assert events[0].event_type == StepEventType.STEP_START
    assert events[1].event_type == StepEventType.STEP_COMPLETE
    assert events[1].output == "done"


def test_get_events_returns_empty_for_missing(tmp_path: Path):
    """Test get_events returns empty list when no events file exists."""
    state = RunState(tmp_path / "runs")

    assert state.get_events("run-nonexistent") == []


def test_list_runs_returns_all_sorted(tmp_path: Path):
    """Test list_runs returns all manifests sorted by filename."""
    state = RunState(tmp_path / "runs")
    state.create_run("run-alpha", "build")
    state.create_run("run-beta", "deploy")
    state.create_run("run-gamma", "test")

    runs = state.list_runs()

    assert len(runs) == 3
    assert runs[0].run_id == "run-alpha"
    assert runs[1].run_id == "run-beta"
    assert runs[2].run_id == "run-gamma"


def test_list_runs_returns_empty_for_missing_dir(tmp_path: Path):
    """Test list_runs returns empty list when runs dir doesn't exist."""
    state = RunState(tmp_path / "nonexistent")

    assert state.list_runs() == []


def test_stop_run_updates_status_to_stopped(tmp_path: Path):
    """Test stop_run sets status to STOPPED."""
    state = RunState(tmp_path / "runs")
    state.create_run("run-abc10", "build")

    manifest = state.stop_run("run-abc10")

    assert manifest is not None
    assert manifest.status == RunStatus.STOPPED
    assert manifest.completed_at != ""


def test_stop_run_returns_none_for_missing(tmp_path: Path):
    """Test stop_run returns None for nonexistent run."""
    state = RunState(tmp_path / "runs")

    assert state.stop_run("run-missing") is None


def test_get_last_successful_step_returns_last_completed(tmp_path: Path):
    """Test get_last_successful_step returns the last completed step name."""
    state = RunState(tmp_path / "runs")
    state.create_run("run-abc11", "build")

    state.append_step_event(
        "run-abc11",
        RunStepEvent(
            timestamp="2026-04-09T10:00:00Z",
            event_type=StepEventType.STEP_START,
            step_name="checkout",
            sequence=0,
        ),
    )
    state.append_step_event(
        "run-abc11",
        RunStepEvent(
            timestamp="2026-04-09T10:01:00Z",
            event_type=StepEventType.STEP_COMPLETE,
            step_name="checkout",
            sequence=1,
        ),
    )
    state.append_step_event(
        "run-abc11",
        RunStepEvent(
            timestamp="2026-04-09T10:02:00Z",
            event_type=StepEventType.STEP_START,
            step_name="compile",
            sequence=2,
        ),
    )
    state.append_step_event(
        "run-abc11",
        RunStepEvent(
            timestamp="2026-04-09T10:03:00Z",
            event_type=StepEventType.STEP_COMPLETE,
            step_name="compile",
            sequence=3,
        ),
    )

    assert state.get_last_successful_step("run-abc11") == "compile"


def test_get_last_successful_step_returns_empty_if_none_completed(tmp_path: Path):
    """Test get_last_successful_step returns empty string when no steps completed."""
    state = RunState(tmp_path / "runs")
    state.create_run("run-abc12", "build")

    state.append_step_event(
        "run-abc12",
        RunStepEvent(
            timestamp="2026-04-09T10:00:00Z",
            event_type=StepEventType.STEP_START,
            step_name="checkout",
            sequence=0,
        ),
    )
    state.append_step_event(
        "run-abc12",
        RunStepEvent(
            timestamp="2026-04-09T10:01:00Z",
            event_type=StepEventType.STEP_ERROR,
            step_name="checkout",
            error="fail",
            sequence=1,
        ),
    )

    assert state.get_last_successful_step("run-abc12") == ""


def test_get_last_successful_step_empty_for_no_events(tmp_path: Path):
    """Test get_last_successful_step returns empty when no events exist."""
    state = RunState(tmp_path / "runs")

    assert state.get_last_successful_step("run-nonexistent") == ""


def test_generate_run_id_starts_with_run():
    """Test generate_run_id produces IDs with 'run-' prefix."""
    run_id = generate_run_id()

    assert run_id.startswith("run-")
    # 8 hex chars after "run-"
    suffix = run_id[4:]
    assert len(suffix) == 8
    int(suffix, 16)  # Must be valid hex


def test_concurrent_creates_dont_overwrite(tmp_path: Path):
    """Test that concurrent create_run calls with different IDs don't overwrite each other."""
    state = RunState(tmp_path / "runs")
    results: dict[str, RunManifest | None] = {}
    errors: list[Exception] = []

    def create(run_id: str) -> None:
        try:
            manifest = state.create_run(run_id, "build")
            results[run_id] = manifest
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=create, args=(f"run-thread{i}",)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(results) == 10

    # All runs should be persisted
    for i in range(10):
        run_id = f"run-thread{i}"
        manifest = state.get_run(run_id)
        assert manifest is not None
        assert manifest.run_id == run_id


def test_append_step_event_with_error_field(tmp_path: Path):
    """Test append_step_event preserves error field in JSONL."""
    state = RunState(tmp_path / "runs")
    state.create_run("run-err1", "build")

    event = RunStepEvent(
        timestamp="2026-04-09T10:00:00Z",
        event_type=StepEventType.STEP_ERROR,
        step_name="compile",
        error="compilation failed: syntax error",
        sequence=2,
    )
    state.append_step_event("run-err1", event)

    events = state.get_events("run-err1")
    assert len(events) == 1
    assert events[0].error == "compilation failed: syntax error"
    assert events[0].event_type == StepEventType.STEP_ERROR
