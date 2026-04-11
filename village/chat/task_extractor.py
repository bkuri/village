"""Task extraction and task store integration."""

import logging
from dataclasses import dataclass, field
from typing import Optional

from village.chat.baseline import BaselineReport, generate_batch_id
from village.chat.sequential_thinking import TaskBreakdown
from village.config import Config
from village.release import BumpType
from village.tasks import TaskCreate, TaskUpdate, get_task_store

logger = logging.getLogger(__name__)


@dataclass
class TaskSubmissionSpec:
    """
    Specification for creating a task.

    Attributes:
        title: Task title
        description: Detailed description
        estimate: Effort estimate (hours|days|weeks)
        success_criteria: List of success criteria
        blockers: List of blockers
        depends_on: List of task IDs
        batch_id: Group ID for tasks from one brainstorm
        parent_task_id: Optional parent task ID
        custom_fields: Additional custom fields
        bump: Version bump type (major|minor|patch|none)
    """

    title: str
    description: str
    estimate: str
    success_criteria: list[str]
    blockers: list[str]
    depends_on: list[str]
    batch_id: str
    parent_task_id: Optional[str]
    custom_fields: dict[str, str]
    bump: BumpType = "patch"
    search_hints: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.depends_on is None:
            self.depends_on = []
        if self.success_criteria is None:
            self.success_criteria = []
        if self.blockers is None:
            self.blockers = []
        if self.custom_fields is None:
            self.custom_fields = {}


def extract_task_specs(
    baseline: BaselineReport,
    breakdown: TaskBreakdown,
    session_id: str,
) -> list[TaskSubmissionSpec]:
    """
    Convert TaskBreakdown items into task create specs.

    - Generate batch ID from session_id
    - Link dependencies using indices
    - Prepare custom fields for parent/batch tracking

    Args:
        baseline: Collected baseline information
        breakdown: Sequential Thinking breakdown
        session_id: Current chat session ID

    Returns:
        List of TaskSubmissionSpec ready for creation
    """
    batch_id = generate_batch_id(session_id)

    specs = []

    for item in breakdown.items:
        bump = _extract_bump_from_tags(item.tags) if item.tags else "patch"

        spec = TaskSubmissionSpec(
            title=item.title,
            description=item.description,
            estimate=item.estimated_effort,
            success_criteria=item.success_criteria,
            blockers=item.blockers,
            depends_on=[],
            batch_id=batch_id,
            parent_task_id=baseline.parent_task_id,
            custom_fields={
                "batch": batch_id,
                "source": "village-brainstorm",
            },
            bump=bump,
            search_hints=item.search_hints,
        )

        if item.tags:
            spec.custom_fields["tags"] = ",".join(item.tags)

        specs.append(spec)

    _resolve_dependencies(specs, breakdown)

    logger.info(f"Extracted {len(specs)} task specs for batch {batch_id}")

    return specs


def _resolve_dependencies(
    specs: list[TaskSubmissionSpec],
    breakdown: TaskBreakdown,
) -> None:
    """
    Resolve dependency indices to task IDs.

    After task creation, update specs with actual task IDs.

    Note: This is a placeholder. Actual ID resolution happens after creation
    when we have the mapping from index → task_id.

    Args:
        specs: TaskSubmissionSpec list (will be mutated)
        breakdown: Original breakdown with index-based dependencies
    """
    for i, item in enumerate(breakdown.items):
        if item.dependencies:
            spec = specs[i]
            spec.depends_on = [f"index-{dep}" for dep in item.dependencies]

    logger.debug(f"Resolved dependencies for {len(specs)} specs")


def _extract_bump_from_tags(tags: list[str]) -> BumpType:
    """
    Extract bump type from tags list.

    Looks for tags in format "bump:major", "bump:minor", "bump:patch", "bump:none".

    Args:
        tags: List of tags

    Returns:
        Bump type if found in tags, otherwise "patch"
    """
    valid_bumps: set[BumpType] = {"major", "minor", "patch", "none"}

    for tag in tags:
        if tag.startswith("bump:"):
            bump_type = tag[5:].lower()
            if bump_type in valid_bumps:
                return bump_type  # type: ignore[return-value]

    return "patch"


async def create_draft_tasks(
    specs: list[TaskSubmissionSpec],
    config: Config,
) -> dict[str, str]:
    store = get_task_store(config=config)
    store.initialize()

    created_tasks = {}

    for spec in specs:
        try:
            task_id = await _create_single_draft(spec, config)
            created_tasks[spec.title] = task_id
            logger.info(f"Created draft task {task_id}: {spec.title}")
        except Exception as e:
            logger.error(f"Failed to create draft task '{spec.title}': {e}")
            raise

    _resolve_task_ids(created_tasks, specs, config)

    return created_tasks


async def _create_single_draft(
    spec: TaskSubmissionSpec,
    config: Config,
) -> str:
    store = get_task_store(config=config)
    store.initialize()

    labels: list[str] = []
    if spec.batch_id:
        labels.append(f"batch:{spec.batch_id}")
    if spec.bump and spec.bump != "none":
        labels.append(f"bump:{spec.bump}")
    if spec.custom_fields.get("tags"):
        for tag in spec.custom_fields["tags"].split(","):
            if tag.strip():
                labels.append(tag.strip())

    depends_on: list[str] = []
    if spec.parent_task_id:
        depends_on.append(spec.parent_task_id)

    task_create = TaskCreate(
        title=spec.title,
        description=spec.description,
        labels=labels,
        depends_on=depends_on,
    )

    task = store.create_task(task_create)
    return task.id


def _resolve_task_ids(
    created_tasks: dict[str, str],
    specs: list[TaskSubmissionSpec],
    config: Config,
) -> None:
    """
    Update specs with actual task IDs for dependencies.

    This replaces placeholder "index-X" dependencies with real task IDs.

    Args:
        created_tasks: Mapping of title → task ID
        specs: TaskSubmissionSpec list (will be mutated)
    """
    title_to_id = {title: tid for title, tid in created_tasks.items()}

    for spec in specs:
        resolved_deps = []
        for dep in spec.depends_on:
            if dep.startswith("index-"):
                try:
                    idx = int(dep.split("-")[1])
                    dep_spec = specs[idx]
                    dep_id = title_to_id.get(dep_spec.title)
                    if dep_id:
                        resolved_deps.append(dep_id)
                except (ValueError, IndexError):
                    logger.warning(f"Invalid dependency index: {dep}")
            else:
                resolved_deps.append(dep)

        spec.depends_on = resolved_deps

        if resolved_deps:
            _update_task_dependencies(created_tasks[spec.title], resolved_deps, config)


def _update_task_dependencies(task_id: str, dependencies: list[str], config: Config) -> None:
    if not dependencies:
        return

    store = get_task_store(config=config)
    store.update_task(task_id, TaskUpdate(add_depends_on=dependencies))
    logger.debug(f"Updated dependencies for {task_id}: {', '.join(dependencies)}")


async def update_task_status(
    task_id: str,
    from_status: str,
    to_status: str,
    config: Config | None = None,
) -> None:
    logger.debug(f"Transitioning {task_id}: {from_status} -> {to_status}")

    store = get_task_store(config=config)
    store.update_task(task_id, TaskUpdate(status=to_status))


async def delete_task(task_id: str, config: Config | None = None) -> None:
    logger.warning(f"Deleting task {task_id}")

    store = get_task_store(config=config)
    store.delete_task(task_id)
