import logging
from typing import Any

logger = logging.getLogger(__name__)


class Planner:
    def __init__(self, llm_call_fn: Any | None = None) -> None:
        self._llm_call = llm_call_fn

    def design(self, goal: str, existing_workflows: list[str] | None = None) -> str:
        prompt = self._build_planning_prompt(goal, existing_workflows or [])
        if self._llm_call:
            result = self._llm_call(prompt)
            if hasattr(result, "__await__"):
                import asyncio

                return str(asyncio.get_event_loop().run_until_complete(result))
            return str(result)
        return prompt

    def _build_planning_prompt(self, goal: str, existing: list[str]) -> str:
        existing_section = ""
        if existing:
            existing_section = "\nExisting workflows that may be relevant: " + ", ".join(existing)

        return (
            f"Design a workflow YAML for this goal:\n\n{goal}\n\n"
            f"The workflow should use these step types:\n"
            f"- prompt: Basic LLM call\n"
            f"- critique: Critical analysis using sequential thinking\n"
            f"- decompose: Break down into subtasks\n"
            f"- research: Web search via Perplexity\n"
            f"- synthesize: Combine prior outputs\n"
            f"- beads: Create trackable subtasks\n\n"
            f"Each step needs: name, type, and either prompt (inline text) or policy (PPC file path).\n"
            f"Optional: traits (dict), tools (list), target (str), input_from (list), async (bool).\n"
            f"Step type is a preset that auto-configures tools and traits.\n"
            f"{existing_section}\n\n"
            f"Output valid YAML only."
        )

    def refine(self, workflow_yaml: str, feedback: str) -> str:
        prompt = (
            f"Refine this workflow based on feedback.\n\n"
            f"Current workflow:\n{workflow_yaml}\n\n"
            f"Feedback:\n{feedback}\n\n"
            f"Output the refined workflow YAML only."
        )
        if self._llm_call:
            result = self._llm_call(prompt)
            if hasattr(result, "__await__"):
                import asyncio

                return str(asyncio.get_event_loop().run_until_complete(result))
            return str(result)
        return prompt
