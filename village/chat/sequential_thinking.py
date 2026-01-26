"""Sequential Thinking integration for task breakdown."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from village.chat.baseline import BaselineReport
from village.config import Config
from village.llm import get_llm_client
from village.llm.tools import SEQUENTIAL_THINKING_TOOL

logger = logging.getLogger(__name__)


@dataclass
class TaskBreakdownItem:
    """
    Single task from Sequential Thinking breakdown.

    Attributes:
        title: Task title
        description: Detailed description
        estimated_effort: Effort estimate (hours|days|weeks)
        success_criteria: List of success criteria
        blockers: List of blockers
        dependencies: List of dependency indices (in breakdown list)
        tags: List of tags
    """

    title: str
    description: str
    estimated_effort: str
    success_criteria: list[str]
    blockers: list[str]
    dependencies: list[int]
    tags: list[str]

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []


@dataclass
class TaskBreakdown:
    """
    Complete task breakdown from Sequential Thinking.

    Attributes:
        items: List of task breakdown items
        summary: Summary of breakdown
        created_at: Timestamp of breakdown
        title_original: User-provided title
        title_suggested: LLM-suggested better title
    """

    items: list[TaskBreakdownItem]
    summary: str
    created_at: str
    title_original: Optional[str] = None
    title_suggested: Optional[str] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


def generate_task_breakdown(
    baseline: BaselineReport,
    config: Config,
    beads_state: Optional[str] = None,
) -> TaskBreakdown:
    """
    Call LLM with Sequential Thinking tool request.

    Build prompt with baseline info, invoke LLM, parse response.

    Args:
        baseline: Collected baseline information
        config: Village configuration
        beads_state: Optional current Beads tasks (for context)

    Returns:
        TaskBreakdown with parsed task list

    Raises:
        ValueError: If response is invalid or missing required fields
        json.JSONDecodeError: If response is not valid JSON
    """
    prompt = _build_sequential_thinking_prompt(baseline, beads_state)

    logger.info("Invoking Sequential Thinking via LLM")

    llm_client = get_llm_client(config)

    response = llm_client.call(
        prompt,
        timeout=config.llm.timeout,
        max_tokens=config.llm.max_tokens,
        tools=[SEQUENTIAL_THINKING_TOOL] if llm_client.supports_tools else None,
    )

    logger.debug(f"LLM output length: {len(response)}")

    return _parse_task_breakdown(response)


def _build_sequential_thinking_prompt(
    baseline: BaselineReport,
    beads_state: Optional[str] = None,
) -> str:
    """
    Build prompt for Sequential Thinking invocation.

    Explicitly instructs OpenCode to use Sequential Thinking MCP tool
    and return task breakdown in structured format.

    Args:
        baseline: Collected baseline information
        beads_state: Optional current Beads tasks (for context)

    Returns:
        Prompt string
    """
    prompt = f"""Use Sequential Thinking MCP tool to break down the following task into manageable subtasks:

USER PROVIDED:
  Title: {baseline.title}
  Reasoning: {baseline.reasoning}
"""

    if baseline.parent_task_id:
        prompt += f"  Parent task: {baseline.parent_task_id}\n"

    if baseline.tags:
        prompt += f"  Tags: {', '.join(baseline.tags)}\n"

    prompt += """

TASK:
"""

    if beads_state:
        prompt += f"""
CONTEXT: Consider these existing Beads tasks:
{beads_state}

Use this context to:
- Determine if any existing tasks should be parent/related to new tasks
- Avoid creating duplicate tasks with similar titles
- Reference related tasks where appropriate
"""

    prompt += """
1. Break down into 3-7 concrete, actionable tasks
2. Evaluate if the user's title is precise and descriptive enough
3. If the title is vague, suggest a more specific/recognizable alternative
4. Each task should be independently completable
5. Identify dependencies between tasks (by index)
6. Provide success criteria for each task
7. Estimate effort (hours|days|weeks)
8. Identify potential blockers

OUTPUT FORMAT:
Return a JSON object with the following structure:
{
  "title_original": "User-provided title (as-is)",
  "title_suggested": "More precise/recognizable title (or same if no better option)",
  "items": [
    {
      "title": "Task title (inferred by LLM based on breakdown logic)",
      "description": "Detailed description (what to do)",
      "estimated_effort": "X hours|days|weeks",
      "success_criteria": ["criterion 1", "criterion 2"],
      "blockers": ["blocker 1"],
      "dependencies": [0, 1],
      "tags": ["tag1", "tag2"]
    }
  ],
  "summary": "Brief summary of breakdown"
}

IMPORTANT: Use metamcp_Sequential-Thinking-Tools__sequentialthinking_tools MCP tool to generate this breakdown.
"""

    return prompt


def _parse_task_breakdown(output: str) -> TaskBreakdown:
    """
    Parse OpenCode output into TaskBreakdown.

    Extracts JSON from output (handles markdown code fences).

    Args:
        output: Raw stdout from OpenCode

    Returns:
        TaskBreakdown with parsed items

    Raises:
        ValueError: If JSON is invalid or missing required fields
        json.JSONDecodeError: If output is not valid JSON
    """
    import re

    json_str = output.strip()

    if "```json" in json_str:
        json_match = re.search(r"```json\s+(.*?)\s*```", json_str, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
    elif "```" in json_str:
        json_match = re.search(r"```\s+(.*?)\s*```", json_str, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON output: {e}")

    if "items" not in data:
        raise ValueError("Missing 'items' field in output")

    items = []
    for i, item_data in enumerate(data["items"]):
        try:
            item = TaskBreakdownItem(
                title=item_data.get("title", f"Task {i + 1}"),
                description=item_data.get("description", ""),
                estimated_effort=item_data.get("estimated_effort", "unknown"),
                success_criteria=item_data.get("success_criteria", []),
                blockers=item_data.get("blockers", []),
                dependencies=item_data.get("dependencies", []),
                tags=item_data.get("tags", []),
            )
            items.append(item)
        except Exception as e:
            raise ValueError(f"Failed to parse task {i}: {e}")

    summary = data.get("summary", "")
    title_original = data.get("title_original")
    title_suggested = data.get("title_suggested")
    created_at = datetime.now().isoformat()

    return TaskBreakdown(
        items=items,
        summary=summary,
        title_original=title_original,
        title_suggested=title_suggested,
        created_at=created_at,
    )


def validate_dependencies(breakdown: TaskBreakdown) -> bool:
    """
    Validate that all dependency indices are valid.

    Args:
        breakdown: Task breakdown to validate

    Returns:
        True if all dependencies are valid, False otherwise
    """
    num_items = len(breakdown.items)

    for i, item in enumerate(breakdown.items):
        for dep in item.dependencies:
            if dep < 0 or dep >= num_items or dep == i:
                logger.error(f"Invalid dependency in task {i}: {dep}")
                return False

    return True
