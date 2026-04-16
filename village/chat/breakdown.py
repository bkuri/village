"""Task decomposition lifecycle — should_decompose, offer, confirm, refine."""

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from village.chat.chat_session import ChatSession
from village.chat.renderers import breakdown_to_text, render_breakdown, render_decomposition_error
from village.chat.sequential_thinking import TaskBreakdown
from village.chat.task_spec import TaskSpec
from village.extensibility import ExtensionRegistry
from village.extensibility.context import SessionContext
from village.extensibility.task_hooks import TaskCreated
from village.tasks import TaskCreate, TaskStore, TaskStoreError

if TYPE_CHECKING:
    from village.config import Config
    from village.llm.client import LLMClient

logger = logging.getLogger(__name__)


async def should_decompose(
    llm_client: "LLMClient",
    extensions: ExtensionRegistry,
    task_spec: TaskSpec,
) -> tuple[bool, str]:
    prompt = f"""Given this task:
Title: {task_spec.title}
Description: {task_spec.description}
Scope: {task_spec.scope}
Estimate: {task_spec.estimate}

Should this task be decomposed into smaller subtasks?

Consider:
- Can it be completed in one focused session (2-4 hours)?
- Are there natural boundaries or phases?
- Would parallel work by multiple developers help?
- Are there distinct deliverables?
- Is the description vague or broad?

Return JSON with format: {{"should_decompose": true/false, "reasoning": "brief explanation"}}"""

    try:
        adapter = extensions.get_llm_adapter()
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                response: str = llm_client.call(
                    prompt=prompt,
                    system_prompt=(
                        "You are a task analysis expert. Determine if tasks should be broken down into smaller pieces."
                    ),
                )
                break
            except Exception as e:
                last_error = e
                if not await adapter.should_retry(e):
                    raise
                if attempt < 2:
                    delay = await adapter.get_retry_delay(attempt + 1)
                    logger.warning(f"LLM call failed (attempt {attempt + 1}), retrying in {delay:.1f}s: {e}")
                    await asyncio.sleep(delay)
        else:
            raise last_error or Exception("LLM call failed after retries")

        result = json.loads(response)

        should = result.get("should_decompose", False)
        reasoning = result.get("reasoning", "No reasoning provided")

        return should, reasoning

    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.warning(f"Failed to parse complexity detection response: {e}")
        return False, f"Error in complexity detection: {e}"


async def offer_decomposition(
    llm_client: "LLMClient",
    config: "Config | None",
    task_spec: TaskSpec,
    user_input: str,
    extensions: ExtensionRegistry,
) -> tuple[TaskBreakdown | None, str]:
    from village.chat.baseline import BaselineReport
    from village.chat.sequential_thinking import generate_task_breakdown, validate_dependencies

    if not config:
        return None, "❌ Config not available. Cannot generate breakdown."

    try:
        baseline = BaselineReport(
            title=task_spec.title,
            reasoning=f"Task decomposition requested for: {task_spec.description[:100]}...",
            parent_task_id=None,
        )

        breakdown = generate_task_breakdown(
            baseline=baseline,
            config=config,
            tasks_state=None,
            llm_client=llm_client,
        )

        if not validate_dependencies(breakdown):
            return None, render_decomposition_error(
                error_message="Generated breakdown has invalid dependencies",
                task_info=f"Title: {task_spec.title}",
                breakdown=breakdown_to_text(breakdown),
                offer_retry=True,
            )

        return breakdown, render_breakdown(breakdown)

    except Exception as e:
        logger.error(f"Failed to generate breakdown: {e}")
        return None, render_decomposition_error(
            error_message=f"Failed to generate task breakdown: {e}",
            task_info=f"Title: {task_spec.title}\nDescription: {task_spec.description[:100]}...",
            offer_retry=True,
        )


async def confirm_breakdown(
    session: ChatSession,
    store: TaskStore,
    extensions: ExtensionRegistry,
    session_id: str,
    session_context: SessionContext | None,
) -> str:
    from village.chat.sequential_thinking import validate_dependencies

    breakdown = session.current_breakdown
    if not breakdown:
        return "❌ No breakdown to confirm."

    items = breakdown.items

    if not validate_dependencies(breakdown):
        return "❌ Task dependencies are invalid. Use /refine or /edit to fix."

    task_id_map: dict[int, str] = {}
    created_tasks: dict[str, str] = {}
    integrator = extensions.get_task_hooks()

    for i, item in enumerate(items):
        blocks = [task_id_map[dep] for dep in item.dependencies if dep in task_id_map]

        spec = TaskSpec(
            title=item.title,
            description=item.description,
            scope="feature",
            blocks=blocks,
            blocked_by=[],
            success_criteria=item.success_criteria or ["Task completed"],
            estimate=item.estimated_effort,
            confidence="medium",
            search_hints=item.search_hints,
        )

        context = {
            "task_spec": spec,
            "breakdown_item": item,
            "item_index": i,
            "breakdown": breakdown,
            "session_id": session_id,
            "session_context": session_context,
            "created_task_ids": task_id_map,
        }

        try:
            task_create = TaskCreate(
                title=item.title,
                description=item.description,
                issue_type="feature",
                priority=2,
                depends_on=[task_id_map[dep] for dep in item.dependencies if dep in task_id_map],
                blocks=blocks,
            )

            if await integrator.should_create_task_hook(context):
                hook_spec = await integrator.create_hook_spec(context)
                task = store.create_task(task_create)
                created_task = TaskCreated(
                    task_id=task.id,
                    parent_id=hook_spec.parent_id,
                    created_at=task.created_at,
                    metadata=hook_spec.metadata,
                )
                await integrator.on_task_created(created_task, context)
                task_id = task.id
            else:
                task = store.create_task(task_create)
                task_id = task.id

            task_id_map[i] = task_id
            created_tasks[item.title] = task_id
            logger.info(f"Created subtask {task_id}: {item.title}")
        except TaskStoreError as e:
            logger.error(f"Failed to create task '{item.title}': {e}")
            return render_decomposition_error(
                error_message=f"Failed to create task '{item.title}': {e}",
                task_info=f"Stopped at task {i + 1}/{len(items)}",
                offer_retry=True,
            )

    session.current_breakdown = None

    lines = [f"✓ Created {len(created_tasks)} subtasks:", ""]
    for title, task_id in created_tasks.items():
        lines.append(f"  {task_id}: {title}")

    if breakdown.summary:
        lines.append("")
        lines.append(breakdown.summary)

    return "\n".join(lines)


async def refine_breakdown(
    llm_client: "LLMClient",
    extensions: ExtensionRegistry,
    session: ChatSession,
    user_input: str,
) -> str:
    from village.chat.sequential_thinking import _parse_task_breakdown, validate_dependencies

    breakdown = session.current_breakdown
    if not breakdown:
        return "❌ No breakdown to refine."

    prompt = f"""Current task breakdown:
{breakdown_to_text(breakdown)}

User refinement: {user_input}

Analyze this feedback and update ENTIRE breakdown accordingly. Consider:
- Should this be a new subtask?
- Should it modify an existing subtask?
- Does it affect dependencies or ordering?
- Are there conflicts or ambiguities?

Return JSON in same breakdown format:
{{
  "title_original": "...",
  "title_suggested": "...",
  "items": [
    {{
      "title": "...",
      "description": "...",
      "estimated_effort": "...",
      "success_criteria": ["..."],
      "blockers": ["..."],
      "dependencies": [0, 1],
      "tags": ["..."]
    }}
  ],
  "summary": "..."
}}
"""

    try:
        adapter = extensions.get_llm_adapter()
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                response = llm_client.call(prompt=prompt)
                break
            except Exception as e:
                last_error = e
                if not await adapter.should_retry(e):
                    raise
                if attempt < 2:
                    delay = await adapter.get_retry_delay(attempt + 1)
                    logger.warning(f"LLM call failed (attempt {attempt + 1}), retrying in {delay:.1f}s: {e}")
                    await asyncio.sleep(delay)
        else:
            raise last_error or Exception("LLM call failed after retries")

        refined_data = json.loads(response)

        refined_breakdown = _parse_task_breakdown(json.dumps(refined_data))

        if not validate_dependencies(refined_breakdown):
            return "❌ Refined breakdown has invalid dependencies. Try different refinement."

        session.current_breakdown = refined_breakdown

        logger.info(f"Refined breakdown: {refined_breakdown.title_original}")

        return render_breakdown(refined_breakdown)

    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Failed to refine breakdown: {e}")
        return render_decomposition_error(
            error_message=f"Failed to refine breakdown: {e}",
            task_info=f"Refinement: {user_input}",
            offer_retry=True,
        )
