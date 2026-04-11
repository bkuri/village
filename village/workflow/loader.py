from pathlib import Path
from typing import Any

import yaml

from village.workflow.schema import RetryConfig, StepConfig, StepType, WorkflowSchema


class WorkflowLoadError(Exception):
    pass


_BUILTIN_DIR = Path(__file__).parent.parent.parent / "workflows"


def _parse_step(raw: dict[str, Any]) -> StepConfig:
    if "name" not in raw:
        raise WorkflowLoadError("Step missing required field 'name'")

    step_type_str = str(raw.get("type", "prompt"))
    try:
        step_type = StepType(step_type_str)
    except ValueError:
        raise WorkflowLoadError(f"Unknown step type: {step_type_str}")

    if "prompt" in raw and "policy" in raw:
        raise WorkflowLoadError(f"Step '{raw['name']}' has both 'prompt' and 'policy' (mutually exclusive)")

    retry_raw = raw.get("retry", {})
    retry = RetryConfig(
        max_attempts=int(retry_raw.get("max_attempts", 1)),
        backoff_seconds=float(retry_raw.get("backoff_seconds", 1.0)),
    )

    return StepConfig(
        name=str(raw["name"]),
        type=step_type,
        prompt=raw.get("prompt"),
        policy=raw.get("policy"),
        traits=raw.get("traits", {}),
        tools=raw.get("tools", []),
        target=raw.get("target"),
        input_from=raw.get("input_from"),
        async_exec=bool(raw.get("async", False)),
        retry=retry,
    )


def _parse_workflow(data: dict[str, Any]) -> WorkflowSchema:
    if "name" not in data:
        raise WorkflowLoadError("Workflow missing required field 'name'")

    steps = [_parse_step(s) for s in data.get("steps", [])]
    return WorkflowSchema(
        name=str(data["name"]),
        description=str(data.get("description", "")),
        steps=steps,
        inputs=data.get("inputs", []),
        version=int(data.get("version", 1)),
    )


class WorkflowLoader:
    def __init__(self, search_paths: list[Path] | None = None) -> None:
        if search_paths is None:
            search_paths = [_BUILTIN_DIR]
        self._search_paths = search_paths

    def _find_file(self, name: str) -> Path:
        for search_path in self._search_paths:
            candidate = search_path / f"{name}.yml"
            if candidate.exists():
                return candidate
            candidate = search_path / f"{name}.yaml"
            if candidate.exists():
                return candidate
        raise WorkflowLoadError(f"Workflow not found: {name}")

    def load(self, name: str) -> WorkflowSchema:
        path = self._find_file(name)
        return self.load_file(path)

    def load_file(self, path: Path) -> WorkflowSchema:
        if not path.exists():
            raise WorkflowLoadError(f"Workflow file not found: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                data: dict[str, Any] = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise WorkflowLoadError(f"Invalid YAML in {path}: {e}") from e

        if not isinstance(data, dict):
            raise WorkflowLoadError(f"Workflow file must contain a mapping: {path}")

        return _parse_workflow(data)

    def list_workflows(self) -> list[str]:
        names: set[str] = set()
        for search_path in self._search_paths:
            if not search_path.exists():
                continue
            for f in search_path.iterdir():
                if f.suffix in (".yml", ".yaml"):
                    names.add(f.stem)
        return sorted(names)
