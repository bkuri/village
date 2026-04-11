import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from village.workflow.schema import StepConfig, StepType, WorkflowSchema

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    name: str
    output: str
    success: bool
    error: str | None = None
    attempts: int = 1


@dataclass
class WorkflowResult:
    workflow_name: str
    outputs: dict[str, str] = field(default_factory=dict)
    step_results: list[StepResult] = field(default_factory=list)
    success: bool = True


class StepExecutor:
    def __init__(self, llm_call_fn: Any | None = None, mcp_fn: Any | None = None) -> None:
        self._llm_call = llm_call_fn
        self._mcp_call = mcp_fn

    async def execute(self, step: StepConfig, context: dict[str, str]) -> StepResult:
        resolved = step.resolve()
        prompt_text = self._build_prompt(resolved, context)

        last_error: str | None = None
        for attempt in range(1, resolved.retry.max_attempts + 1):
            try:
                output = await self._run_step(resolved, prompt_text)
                return StepResult(name=step.name, output=output, success=True, attempts=attempt)
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Step '{step.name}' attempt {attempt} failed: {e}")
                if attempt < resolved.retry.max_attempts:
                    delay = resolved.retry.backoff_seconds * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

        return StepResult(
            name=step.name, output="", success=False, error=last_error, attempts=resolved.retry.max_attempts
        )

    def _build_prompt(self, step: StepConfig, context: dict[str, str]) -> str:
        parts: list[str] = []

        if step.prompt:
            parts.append(step.prompt)

        if step.input_from:
            for ref in step.input_from:
                if ref in context:
                    parts.append(f"\n--- Input from {ref} ---\n{context[ref]}")
        elif context:
            for name, output in context.items():
                parts.append(f"\n--- {name} ---\n{output}")

        if step.traits:
            trait_parts = [f"{k}: {v}" for k, v in step.traits.items()]
            parts.append("\n--- Traits ---\n" + "\n".join(trait_parts))

        return "\n".join(parts)

    async def _run_step(self, step: StepConfig, prompt_text: str) -> str:
        if step.type == StepType.RESEARCH and self._mcp_call:
            result = await self._mcp_call("perplexity", prompt_text)
            return str(result)

        if step.type == StepType.CRITIQUE and self._mcp_call:
            result = await self._mcp_call("sequential_thinking", prompt_text)
            return str(result)

        if step.type == StepType.DECOMPOSE and self._mcp_call:
            result = await self._mcp_call("sequential_thinking", prompt_text)
            return str(result)

        if self._llm_call:
            result = self._llm_call(prompt_text, step)
            if asyncio.iscoroutine(result):
                return str(await result)
            return str(result)

        return prompt_text


class Builder:
    def __init__(
        self,
        llm_call_fn: Any | None = None,
        mcp_fn: Any | None = None,
    ) -> None:
        self._executor = StepExecutor(llm_call_fn=llm_call_fn, mcp_fn=mcp_fn)

    async def run(self, workflow: WorkflowSchema, inputs: dict[str, str] | None = None) -> WorkflowResult:
        if inputs is None:
            inputs = {}

        context: dict[str, str] = dict(inputs)
        resolved_steps = workflow.resolve_steps()
        results: list[StepResult] = []

        for step in resolved_steps:
            result = await self._executor.execute(step, context)
            results.append(result)

            if result.success:
                context[step.name] = result.output
            else:
                logger.error(f"Step '{step.name}' failed: {result.error}")
                return WorkflowResult(
                    workflow_name=workflow.name,
                    outputs=context,
                    step_results=results,
                    success=False,
                )

        return WorkflowResult(
            workflow_name=workflow.name,
            outputs=context,
            step_results=results,
            success=True,
        )

    def run_sync(self, workflow: WorkflowSchema, inputs: dict[str, str] | None = None) -> WorkflowResult:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.run(workflow, inputs))
                    return future.result()
        except RuntimeError:
            pass
        return asyncio.run(self.run(workflow, inputs))
