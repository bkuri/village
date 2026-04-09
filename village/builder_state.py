import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class StepEventType(str, Enum):
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    STEP_ERROR = "step_error"


@dataclass
class RunManifest:
    run_id: str
    workflow_name: str
    status: RunStatus
    inputs: dict[str, str] = field(default_factory=dict)
    steps_total: int = 0
    steps_completed: int = 0
    current_step: str = ""
    started_at: str = ""
    completed_at: str = ""


@dataclass
class RunStepEvent:
    timestamp: str
    event_type: StepEventType
    step_name: str
    output: str = ""
    error: str = ""
    sequence: int = 0


class RunState:
    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir

    def _manifest_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.json"

    def _events_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.jsonl"

    def create_run(
        self,
        run_id: str,
        workflow_name: str,
        inputs: dict[str, str] | None = None,
        steps_total: int = 0,
    ) -> RunManifest:
        manifest = RunManifest(
            run_id=run_id,
            workflow_name=workflow_name,
            status=RunStatus.PENDING,
            inputs=inputs or {},
            steps_total=steps_total,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._write_manifest(manifest)
        return manifest

    def update_status(self, run_id: str, status: RunStatus) -> RunManifest | None:
        manifest = self.get_run(run_id)
        if manifest is None:
            return None
        manifest.status = status
        if status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.STOPPED):
            manifest.completed_at = datetime.now(timezone.utc).isoformat()
        self._write_manifest(manifest)
        return manifest

    def advance_step(self, run_id: str, step_name: str) -> RunManifest | None:
        manifest = self.get_run(run_id)
        if manifest is None:
            return None
        manifest.current_step = step_name
        manifest.steps_completed += 1
        self._write_manifest(manifest)
        return manifest

    def append_step_event(self, run_id: str, event: RunStepEvent) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        event_dict = {
            "timestamp": event.timestamp,
            "event_type": event.event_type.value,
            "step_name": event.step_name,
            "output": event.output,
            "error": event.error,
            "sequence": event.sequence,
        }
        with open(self._events_path(run_id), "a", encoding="utf-8") as f:
            f.write(json.dumps(event_dict, sort_keys=True) + "\n")

    def get_run(self, run_id: str) -> RunManifest | None:
        path = self._manifest_path(run_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return RunManifest(
            run_id=data["run_id"],
            workflow_name=data["workflow_name"],
            status=RunStatus(data["status"]),
            inputs=data.get("inputs", {}),
            steps_total=data.get("steps_total", 0),
            steps_completed=data.get("steps_completed", 0),
            current_step=data.get("current_step", ""),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
        )

    def get_events(self, run_id: str) -> list[RunStepEvent]:
        path = self._events_path(run_id)
        if not path.exists():
            return []
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            events.append(
                RunStepEvent(
                    timestamp=data["timestamp"],
                    event_type=StepEventType(data["event_type"]),
                    step_name=data["step_name"],
                    output=data.get("output", ""),
                    error=data.get("error", ""),
                    sequence=data.get("sequence", 0),
                )
            )
        return events

    def list_runs(self) -> list[RunManifest]:
        if not self.runs_dir.exists():
            return []
        runs = []
        for path in sorted(self.runs_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            runs.append(
                RunManifest(
                    run_id=data["run_id"],
                    workflow_name=data["workflow_name"],
                    status=RunStatus(data["status"]),
                    inputs=data.get("inputs", {}),
                    steps_total=data.get("steps_total", 0),
                    steps_completed=data.get("steps_completed", 0),
                    current_step=data.get("current_step", ""),
                    started_at=data.get("started_at", ""),
                    completed_at=data.get("completed_at", ""),
                )
            )
        return runs

    def stop_run(self, run_id: str) -> RunManifest | None:
        return self.update_status(run_id, RunStatus.STOPPED)

    def get_last_successful_step(self, run_id: str) -> str:
        events = self.get_events(run_id)
        last_complete = ""
        for event in events:
            if event.event_type == StepEventType.STEP_COMPLETE:
                last_complete = event.step_name
        return last_complete

    def _write_manifest(self, manifest: RunManifest) -> None:
        data = {
            "run_id": manifest.run_id,
            "workflow_name": manifest.workflow_name,
            "status": manifest.status.value,
            "inputs": manifest.inputs,
            "steps_total": manifest.steps_total,
            "steps_completed": manifest.steps_completed,
            "current_step": manifest.current_step,
            "started_at": manifest.started_at,
            "completed_at": manifest.completed_at,
        }
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._manifest_path(manifest.run_id).with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self._manifest_path(manifest.run_id))


def generate_run_id() -> str:
    import uuid

    return f"run-{uuid.uuid4().hex[:8]}"
