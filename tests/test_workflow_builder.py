import pytest

from village.workflow.builder import Builder, StepExecutor, StepResult
from village.workflow.planner import Planner
from village.workflow.schema import StepConfig, StepType, WorkflowSchema


class TestStepResult:
    def test_success(self):
        r = StepResult(name="s1", output="result", success=True)
        assert r.success
        assert r.error is None
        assert r.attempts == 1

    def test_failure(self):
        r = StepResult(name="s1", output="", success=False, error="boom")
        assert not r.success
        assert r.error == "boom"


class TestStepExecutor:
    @pytest.mark.asyncio
    async def test_execute_prompt_step(self):
        def mock_llm(prompt: str, step: StepConfig) -> str:
            return f"LLM response to: {step.name}"

        executor = StepExecutor(llm_call_fn=mock_llm)
        step = StepConfig(name="test", type=StepType.PROMPT, prompt="hello")
        result = await executor.execute(step, {})
        assert result.success
        assert "test" in result.output

    @pytest.mark.asyncio
    async def test_execute_with_context(self):
        def mock_llm(prompt: str, step: StepConfig) -> str:
            return "saw context"

        executor = StepExecutor(llm_call_fn=mock_llm)
        step = StepConfig(name="s2", type=StepType.PROMPT, prompt="use context")
        result = await executor.execute(step, {"s1": "previous output"})
        assert result.success

    @pytest.mark.asyncio
    async def test_execute_with_input_from(self):
        def mock_llm(prompt: str, step: StepConfig) -> str:
            return prompt

        executor = StepExecutor(llm_call_fn=mock_llm)
        step = StepConfig(name="s2", type=StepType.PROMPT, prompt="analyze", input_from=["s1"])
        result = await executor.execute(step, {"s1": "data", "s3": "ignored"})
        assert "data" in result.output
        assert "ignored" not in result.output

    @pytest.mark.asyncio
    async def test_execute_no_llm_fallback(self):
        executor = StepExecutor()
        step = StepConfig(name="test", type=StepType.PROMPT, prompt="hello")
        result = await executor.execute(step, {})
        assert result.success
        assert "hello" in result.output

    @pytest.mark.asyncio
    async def test_execute_retry_on_failure(self):
        call_count = 0

        def flaky_llm(prompt: str, step: StepConfig) -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient error")
            return "success"

        executor = StepExecutor(llm_call_fn=flaky_llm)
        step = StepConfig(
            name="test",
            type=StepType.PROMPT,
            prompt="hello",
            retry={"max_attempts": 3, "backoff_seconds": 0.01},
        )
        step = StepConfig(
            name="test",
            type=StepType.PROMPT,
            prompt="hello",
        )
        from village.workflow.schema import RetryConfig

        step = StepConfig(
            name="test",
            type=StepType.PROMPT,
            prompt="hello",
            retry=RetryConfig(max_attempts=3, backoff_seconds=0.01),
        )
        result = await executor.execute(step, {})
        assert result.success
        assert result.attempts == 3

    @pytest.mark.asyncio
    async def test_execute_exhausted_retries(self):
        def always_fail(prompt: str, step: StepConfig) -> str:
            raise RuntimeError("permanent error")

        executor = StepExecutor(llm_call_fn=always_fail)
        from village.workflow.schema import RetryConfig

        step = StepConfig(
            name="test",
            type=StepType.PROMPT,
            prompt="hello",
            retry=RetryConfig(max_attempts=2, backoff_seconds=0.01),
        )
        result = await executor.execute(step, {})
        assert not result.success
        assert "permanent error" in result.error
        assert result.attempts == 2


class TestBuilder:
    def test_run_sync_simple(self):
        def mock_llm(prompt: str, step: StepConfig) -> str:
            return f"output from {step.name}"

        wf = WorkflowSchema(
            name="test",
            description="test",
            steps=[
                StepConfig(name="s1", type=StepType.PROMPT, prompt="p1"),
                StepConfig(name="s2", type=StepType.PROMPT, prompt="p2"),
            ],
        )
        builder = Builder(llm_call_fn=mock_llm)
        result = builder.run_sync(wf)
        assert result.success
        assert "s1" in result.outputs
        assert "s2" in result.outputs

    def test_run_sync_with_inputs(self):
        def mock_llm(prompt: str, step: StepConfig) -> str:
            return f"saw: {prompt[:30]}"

        wf = WorkflowSchema(
            name="test",
            description="test",
            inputs=["topic"],
            steps=[
                StepConfig(name="s1", type=StepType.PROMPT, prompt="about {{topic}}"),
            ],
        )
        builder = Builder(llm_call_fn=mock_llm)
        result = builder.run_sync(wf, inputs={"topic": "AI agents"})
        assert result.success

    def test_run_sync_stops_on_failure(self):
        def fail_llm(prompt: str, step: StepConfig) -> str:
            if step.name == "s2":
                raise RuntimeError("step 2 failed")
            return "ok"

        wf = WorkflowSchema(
            name="test",
            description="test",
            steps=[
                StepConfig(name="s1", type=StepType.PROMPT, prompt="p1"),
                StepConfig(name="s2", type=StepType.PROMPT, prompt="p2"),
                StepConfig(name="s3", type=StepType.PROMPT, prompt="p3"),
            ],
        )
        builder = Builder(llm_call_fn=fail_llm)
        result = builder.run_sync(wf)
        assert not result.success
        assert len(result.step_results) == 2
        assert result.step_results[1].name == "s2"

    @pytest.mark.asyncio
    async def test_run_async(self):
        async def mock_llm(prompt: str, step: StepConfig) -> str:
            return f"async output from {step.name}"

        wf = WorkflowSchema(
            name="test",
            description="test",
            steps=[
                StepConfig(name="s1", type=StepType.PROMPT, prompt="p1"),
            ],
        )
        builder = Builder(llm_call_fn=mock_llm)
        result = await builder.run(wf)
        assert result.success

    def test_context_accumulation(self):
        outputs_seen: list[str] = []

        def mock_llm(prompt: str, step: StepConfig) -> str:
            outputs_seen.append(prompt)
            return f"output_{step.name}"

        wf = WorkflowSchema(
            name="test",
            description="test",
            steps=[
                StepConfig(name="s1", type=StepType.PROMPT, prompt="step 1"),
                StepConfig(name="s2", type=StepType.PROMPT, prompt="step 2"),
            ],
        )
        builder = Builder(llm_call_fn=mock_llm)
        result = builder.run_sync(wf)
        assert result.success
        assert "output_s1" in outputs_seen[1]


class TestPlanner:
    def test_design_returns_prompt_without_llm(self):
        planner = Planner()
        result = planner.design("Create a naming workflow")
        assert "naming workflow" in result
        assert "step types" in result.lower() or "Step" in result

    def test_refine_without_llm(self):
        planner = Planner()
        result = planner.refine("name: test\nsteps: []", "add more steps")
        assert "test" in result
        assert "add more steps" in result

    def test_design_with_mock_llm(self):
        def mock_llm(prompt: str) -> str:
            return "name: generated\nsteps:\n  - name: s1\n    type: prompt\n    prompt: test"

        planner = Planner(llm_call_fn=mock_llm)
        result = planner.design("goal")
        assert "generated" in result

    def test_design_with_existing_workflows(self):
        planner = Planner()
        result = planner.design("goal", ["name-design", "slogan-design"])
        assert "name-design" in result
