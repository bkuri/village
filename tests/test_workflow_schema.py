from pathlib import Path

import pytest

from village.workflow.loader import WorkflowLoader, WorkflowLoadError, _parse_step, _parse_workflow
from village.workflow.schema import StepConfig, StepType, WorkflowSchema


class TestStepType:
    def test_all_types(self):
        assert StepType.PROMPT.value == "prompt"
        assert StepType.CRITIQUE.value == "critique"
        assert StepType.DECOMPOSE.value == "decompose"
        assert StepType.RESEARCH.value == "research"
        assert StepType.SYNTHESIZE.value == "synthesize"

    def test_from_string(self):
        assert StepType("prompt") == StepType.PROMPT
        assert StepType("critique") == StepType.CRITIQUE


class TestStepConfig:
    def test_resolve_prompt_type(self):
        s = StepConfig(name="test", type=StepType.PROMPT, prompt="hello")
        resolved = s.resolve()
        assert resolved.tools == []
        assert resolved.traits == {}

    def test_resolve_critique_type(self):
        s = StepConfig(name="crit", type=StepType.CRITIQUE, prompt="critique this")
        resolved = s.resolve()
        assert "sequential_thinking" in resolved.tools
        assert resolved.traits.get("style") == "critical"

    def test_resolve_decompose_type(self):
        s = StepConfig(name="dec", type=StepType.DECOMPOSE, prompt="break down")
        resolved = s.resolve()
        assert "sequential_thinking" in resolved.tools

    def test_resolve_research_type(self):
        s = StepConfig(name="res", type=StepType.RESEARCH, prompt="search for")
        resolved = s.resolve()
        assert "perplexity" in resolved.tools
        assert resolved.retry.max_attempts == 3

    def test_resolve_custom_traits_merge(self):
        s = StepConfig(
            name="test",
            type=StepType.CRITIQUE,
            prompt="x",
            traits={"custom": "value", "style": "override"},
        )
        resolved = s.resolve()
        assert resolved.traits["custom"] == "value"
        assert resolved.traits["style"] == "override"

    def test_resolve_custom_tools_override(self):
        s = StepConfig(name="test", type=StepType.PROMPT, prompt="x", tools=["custom_tool"])
        resolved = s.resolve()
        assert resolved.tools == ["custom_tool"]


class TestWorkflowSchema:
    def test_resolve_steps(self):
        steps = [
            StepConfig(name="s1", type=StepType.PROMPT, prompt="p1"),
            StepConfig(name="s2", type=StepType.CRITIQUE, prompt="p2"),
        ]
        wf = WorkflowSchema(name="test", description="desc", steps=steps)
        resolved = wf.resolve_steps()
        assert len(resolved) == 2
        assert "sequential_thinking" in resolved[1].tools


class TestParseStep:
    def test_minimal(self):
        raw = {"name": "test", "type": "prompt", "prompt": "hello"}
        step = _parse_step(raw)
        assert step.name == "test"
        assert step.type == StepType.PROMPT

    def test_missing_name(self):
        with pytest.raises(WorkflowLoadError, match="missing required field 'name'"):
            _parse_step({"type": "prompt"})

    def test_unknown_type(self):
        with pytest.raises(WorkflowLoadError, match="Unknown step type"):
            _parse_step({"name": "test", "type": "nonexistent"})

    def test_prompt_and_policy_mutually_exclusive(self):
        with pytest.raises(WorkflowLoadError, match="mutually exclusive"):
            _parse_step({"name": "test", "type": "prompt", "prompt": "p", "policy": "file.md"})

    def test_default_type_is_prompt(self):
        raw = {"name": "test", "prompt": "hello"}
        step = _parse_step(raw)
        assert step.type == StepType.PROMPT

    def test_with_retry(self):
        raw = {"name": "test", "prompt": "p", "retry": {"max_attempts": 5, "backoff_seconds": 3.0}}
        step = _parse_step(raw)
        assert step.retry.max_attempts == 5
        assert step.retry.backoff_seconds == 3.0

    def test_with_traits(self):
        raw = {"name": "test", "prompt": "p", "traits": {"style": "bold"}}
        step = _parse_step(raw)
        assert step.traits == {"style": "bold"}

    def test_with_async(self):
        raw = {"name": "test", "prompt": "p", "async": True}
        step = _parse_step(raw)
        assert step.async_exec is True

    def test_with_input_from(self):
        raw = {"name": "test", "prompt": "p", "input_from": ["step1", "step2"]}
        step = _parse_step(raw)
        assert step.input_from == ["step1", "step2"]

    def test_with_target(self):
        raw = {"name": "test", "prompt": "p", "target": "beads"}
        step = _parse_step(raw)
        assert step.target == "beads"


class TestParseWorkflow:
    def test_minimal(self):
        raw = {"name": "test", "description": "desc"}
        wf = _parse_workflow(raw)
        assert wf.name == "test"
        assert wf.description == "desc"
        assert wf.steps == []

    def test_missing_name(self):
        with pytest.raises(WorkflowLoadError, match="missing required field 'name'"):
            _parse_workflow({"description": "desc"})

    def test_with_steps(self):
        raw = {
            "name": "test",
            "steps": [
                {"name": "s1", "type": "prompt", "prompt": "p1"},
                {"name": "s2", "type": "critique", "prompt": "p2"},
            ],
        }
        wf = _parse_workflow(raw)
        assert len(wf.steps) == 2

    def test_with_inputs(self):
        raw = {"name": "test", "inputs": ["entity_description", "brand_context"]}
        wf = _parse_workflow(raw)
        assert wf.inputs == ["entity_description", "brand_context"]


class TestWorkflowLoader:
    def test_load_name_design(self, tmp_path: Path) -> None:
        workflow_dir = Path(__file__).parent.parent / "workflows"
        loader = WorkflowLoader(search_paths=[workflow_dir])
        wf = loader.load("name-design")
        assert wf.name == "name-design"
        assert len(wf.steps) == 4
        assert wf.inputs == ["entity_description"]

    def test_load_slogan_design(self, tmp_path: Path) -> None:
        workflow_dir = Path(__file__).parent.parent / "workflows"
        loader = WorkflowLoader(search_paths=[workflow_dir])
        wf = loader.load("slogan-design")
        assert wf.name == "slogan-design"
        assert len(wf.steps) == 3

    def test_load_decomposer(self, tmp_path: Path) -> None:
        workflow_dir = Path(__file__).parent.parent / "workflows"
        loader = WorkflowLoader(search_paths=[workflow_dir])
        wf = loader.load("decomposer")
        assert wf.name == "decomposer"
        assert len(wf.steps) == 3

    def test_list_workflows(self) -> None:
        workflow_dir = Path(__file__).parent.parent / "workflows"
        loader = WorkflowLoader(search_paths=[workflow_dir])
        names = loader.list_workflows()
        assert "name-design" in names
        assert "slogan-design" in names
        assert "decomposer" in names

    def test_not_found(self) -> None:
        loader = WorkflowLoader(search_paths=[Path("/nonexistent")])
        with pytest.raises(WorkflowLoadError, match="Workflow not found"):
            loader.load("nonexistent")

    def test_load_file(self, tmp_path: Path) -> None:
        wf_file = tmp_path / "test.yml"
        wf_file.write_text(
            "name: test\ndescription: test workflow\nsteps:\n  - name: s1\n    type: prompt\n    prompt: hello\n"
        )
        loader = WorkflowLoader()
        wf = loader.load_file(wf_file)
        assert wf.name == "test"

    def test_load_file_not_found(self, tmp_path: Path) -> None:
        loader = WorkflowLoader()
        with pytest.raises(WorkflowLoadError, match="file not found"):
            loader.load_file(tmp_path / "nonexistent.yml")

    def test_load_invalid_yaml(self, tmp_path: Path) -> None:
        wf_file = tmp_path / "bad.yml"
        wf_file.write_text(":\n  :\n    - [\n")
        loader = WorkflowLoader()
        with pytest.raises(WorkflowLoadError, match="Invalid YAML"):
            loader.load_file(wf_file)

    def test_load_non_mapping(self, tmp_path: Path) -> None:
        wf_file = tmp_path / "list.yml"
        wf_file.write_text("- item1\n- item2\n")
        loader = WorkflowLoader()
        with pytest.raises(WorkflowLoadError, match="must contain a mapping"):
            loader.load_file(wf_file)

    def test_yaml_extension(self, tmp_path: Path) -> None:
        wf_file = tmp_path / "test.yaml"
        wf_file.write_text("name: test\ndescription: desc\n")
        loader = WorkflowLoader(search_paths=[tmp_path])
        wf = loader.load("test")
        assert wf.name == "test"

    def test_empty_dir(self, tmp_path: Path) -> None:
        loader = WorkflowLoader(search_paths=[tmp_path])
        assert loader.list_workflows() == []
