"""Task extraction and Beads integration."""

import json
import logging
from dataclasses import dataclass
from typing import Optional

from village.chat.baseline import BaselineReport, generate_batch_id
from village.chat.sequential_thinking import TaskBreakdown
from village.config import Config
from village.probes.tools import SubprocessError, run_command_output
from village.release import BumpType

logger = logging.getLogger(__name__)


@dataclass
class BeadsTaskSpec:
    """
    Specification for creating a Beads task.

    Attributes:
        title: Task title
        description: Detailed description
        estimate: Effort estimate (hours|days|weeks)
        success_criteria: List of success criteria
        blockers: List of blockers
        depends_on: List of task IDs in Beads
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

    def __post_init__(self) -> None:
        if self.depends_on is None:
            self.depends_on = []
        if self.success_criteria is None:
            self.success_criteria = []
        if self.blockers is None:
            self.blockers = []
        if self.custom_fields is None:
            self.custom_fields = {}


def extract_beads_specs(
    baseline: BaselineReport,
    breakdown: TaskBreakdown,
    session_id: str,
) -> list[BeadsTaskSpec]:
    """
    Convert TaskBreakdown items into Beads create commands.

    - Generate batch ID from session_id
    - Link dependencies using indices
    - Prepare custom fields for parent/batch tracking

    Args:
        baseline: Collected baseline information
        breakdown: Sequential Thinking breakdown
        session_id: Current chat session ID

    Returns:
        List of BeadsTaskSpec ready for creation
    """
    batch_id = generate_batch_id(session_id)

    specs = []

    for item in breakdown.items:
        bump = _extract_bump_from_tags(item.tags) if item.tags else "patch"

        spec = BeadsTaskSpec(
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
        )

        if item.tags:
            spec.custom_fields["tags"] = ",".join(item.tags)

        specs.append(spec)

    _resolve_dependencies(specs, breakdown)

    logger.info(f"Extracted {len(specs)} Beads task specs for batch {batch_id}")

    return specs


def _resolve_dependencies(
    specs: list[BeadsTaskSpec],
    breakdown: TaskBreakdown,
) -> None:
    """
    Resolve dependency indices to task IDs.

    After task creation, update specs with actual Beads task IDs.

    Note: This is a placeholder. Actual ID resolution happens after creation
    when we have the mapping from index → task_id.

    Args:
        specs: BeadsTaskSpec list (will be mutated)
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
    specs: list[BeadsTaskSpec],
    config: Config,
) -> dict[str, str]:
    """
    Create draft tasks in Beads.

    For each spec, calls `bd create --status draft --json`.

    Args:
        specs: List of BeadsTaskSpec to create
        config: Village configuration

    Returns:
        Mapping of spec title → task ID

    Raises:
        SubprocessError: If Beads command fails
    """

    created_tasks = {}

    for spec in specs:
        try:
            task_id = await _create_single_draft(spec, config)
            created_tasks[spec.title] = task_id
            logger.info(f"Created draft task {task_id}: {spec.title}")
        except Exception as e:
            logger.error(f"Failed to create draft task '{spec.title}': {e}")
            raise

    _resolve_task_ids(created_tasks, specs)

    return created_tasks


async def _create_single_draft(
    spec: BeadsTaskSpec,
    config: Config,
) -> str:
    """
    Create a single draft task in Beads.

    Args:
        spec: Task specification
        config: Village configuration

    Returns:
        Created task ID

    Raises:
        SubprocessError: If creation fails
    """
    cmd = [
        "bd",
        "create",
        "--json",
        "--title",
        spec.title,
        "--description",
        spec.description,
    ]

    if spec.estimate and spec.estimate != "unknown":
        # Convert estimate to minutes (Beads expects integer minutes)
        estimate_map = {
            "minutes": "60",
            "hours": "60",
            "hour": "60",
            "days": "480",  # 8 hours
            "day": "480",
            "weeks": "2400",  # 5 days
            "week": "2400",
        }
        estimate_minutes = estimate_map.get(spec.estimate.lower(), spec.estimate)
        cmd.extend(["--estimate", estimate_minutes])

    if spec.batch_id:
        cmd.extend(["--tag", f"batch:{spec.batch_id}"])

    if spec.bump and spec.bump != "none":
        cmd.extend(["--label", f"bump:{spec.bump}"])

    if spec.parent_task_id:
        cmd.extend(["--relates-to", spec.parent_task_id])

    if spec.custom_fields.get("tags"):
        for tag in spec.custom_fields["tags"].split(","):
            if tag.strip():
                cmd.extend(["--tag", tag.strip()])

    result = run_command_output(cmd)

    try:
        response = json.loads(result)
        task_id = response.get("id") or response.get("task_id")
        if not task_id:
            raise ValueError("No task ID in response")
        return str(task_id)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Beads response: {result}")
        raise ValueError(f"Invalid Beads response: {e}")


def _resolve_task_ids(
    created_tasks: dict[str, str],
    specs: list[BeadsTaskSpec],
) -> None:
    """
    Update specs with actual Beads task IDs for dependencies.

    This replaces placeholder "index-X" dependencies with real task IDs.

    Args:
        created_tasks: Mapping of title → task ID
        specs: BeadsTaskSpec list (will be mutated)
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
            _update_task_dependencies(created_tasks[spec.title], resolved_deps)


def _update_task_dependencies(task_id: str, dependencies: list[str]) -> None:
    """
    Update task dependencies in Beads.

    Args:
        task_id: Task to update
        dependencies: List of task IDs to depend on

    Raises:
        SubprocessError: If update fails
    """
    if not dependencies:
        return

    dep_str = ",".join(dependencies)

    try:
        run_command_output(
            [
                "bd",
                "set-state",
                task_id,
                f"depends_on={dep_str}",
            ]
        )
        logger.debug(f"Updated dependencies for {task_id}: {dep_str}")
    except SubprocessError as e:
        logger.error(f"Failed to update dependencies for {task_id}: {e}")
        raise


async def update_task_status(
    task_id: str,
    from_status: str,
    to_status: str,
) -> None:
    """
    Update task status in Beads.

    Args:
        task_id: Task ID to update
        from_status: Current status (for idempotency)
        to_status: Target status

    Raises:
        SubprocessError: If update fails
    """
    logger.debug(f"Transitioning {task_id}: {from_status} → {to_status}")

    try:
        run_command_output(
            [
                "bd",
                "set-state",
                task_id,
                f"status={from_status}",
                f"status={to_status}",
            ]
        )
    except SubprocessError as e:
        logger.error(f"Failed to update status for {task_id}: {e}")
        raise


async def delete_task(task_id: str) -> None:
    """
    Delete a task in Beads.

    Args:
        task_id: Task ID to delete

    Raises:
        SubprocessError: If deletion fails
    """
    logger.warning(f"Deleting task {task_id}")

    try:
        run_command_output(["bd", "delete", task_id])
    except SubprocessError as e:
        logger.error(f"Failed to delete task {task_id}: {e}")
        raise
