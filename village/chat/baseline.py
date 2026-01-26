"""Baseline collection for brainstorm mode."""

import logging
from dataclasses import dataclass
from typing import Any, Optional

from village.probes.tools import SubprocessError, run_command_output

logger = logging.getLogger(__name__)


@dataclass
class BaselineReport:
    """
    Baseline information collected for task breakdown.

    Attributes:
        title: What task/project to break down
        reasoning: Why this needs breaking down
        parent_task_id: Optional existing task to relate to
        tags: Optional batch tags for grouping
    """

    title: str
    reasoning: str
    parent_task_id: Optional[str] = None
    tags: Optional[list[str]] = None

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []


def collect_baseline(
    initial_title: Optional[str] = None,
    max_followups: int = 3,
) -> BaselineReport:
    """
    Collect baseline information from user.

    Interactive collection of:
    1. Title (required) - what's task/project?
    2. Reasoning (required) - why break it down?
    3. Parent (optional) - relate to existing task?

    Validates inputs and returns structured report.

    Args:
        initial_title: Pre-filled title if provided
        max_followups: Maximum adaptive follow-up questions

    Returns:
        BaselineReport with collected information

    Raises:
        ValueError: If required fields are missing or invalid
    """
    logger.info("Starting baseline collection")

    title = _collect_title(initial_title)
    reasoning = _collect_reasoning(title)

    optional_fields = _collect_optional_fields(title, max_followups)

    logger.info(f"Baseline collected: {title}")

    return BaselineReport(
        title=title,
        reasoning=reasoning,
        parent_task_id=optional_fields.get("parent_task_id"),
        tags=optional_fields.get("tags", []),
    )


def _collect_title(initial_title: Optional[str] = None) -> str:
    """
    Collect task title from user.

    Args:
        initial_title: Pre-filled title if provided

    Returns:
        Validated title string

    Raises:
        ValueError: If title is invalid length
    """
    import click

    if initial_title:
        click.echo(f"Title: {initial_title}")
        title = initial_title
    else:
        title = str(
            click.prompt(
                "What do you want to break down? (brief, max 100 chars)",
                show_default=False,
            )
        )

    if not title or len(title.strip()) < 3:
        raise ValueError("Title must be at least 3 characters")
    if len(title) > 100:
        raise ValueError("Title must be max 100 characters")

    return title.strip()


def _collect_reasoning(title: str) -> str:
    """
    Collect reasoning from user.

    Args:
        title: Task title for context

    Returns:
        Validated reasoning string

    Raises:
        ValueError: If reasoning is empty or too short
    """
    import click

    reasoning = str(click.prompt(f"Why break down '{title}'?", show_default=False))

    if not reasoning or len(reasoning.strip()) < 10:
        raise ValueError("Reasoning must be at least 10 characters")

    return reasoning.strip()


def _collect_optional_fields(title: str, max_followups: int) -> dict[str, Any]:
    """
    Collect optional fields with adaptive follow-ups.

    Args:
        title: Task title for context
        max_followups: Maximum follow-up questions to ask

    Returns:
        Dict with optional fields (parent_task_id, tags)
    """
    import click

    optional_fields: dict[str, Any] = {}
    followups_asked = 0

    if followups_asked < max_followups:
        parent = click.prompt("Parent task ID (leave empty): ", show_default=False, default="")
        if parent:
            optional_fields["parent_task_id"] = parent
            followups_asked += 1

    if followups_asked < max_followups:
        tags_input = click.prompt(
            "Batch tags (comma-separated, leave empty): ", show_default=False, default=""
        )
        if tags_input:
            optional_fields["tags"] = [t.strip() for t in tags_input.split(",") if t.strip()]
            followups_asked += 1

    return optional_fields


def validate_task_id(task_id: str) -> bool:
    """
    Validate that a task ID exists in Beads.

    Args:
        task_id: Task ID to validate

    Returns:
        True if task exists, False otherwise
    """
    try:
        output = run_command_output(["bd", "show", task_id])
        return output is not None
    except SubprocessError:
        return False


def generate_batch_id(session_id: str) -> str:
    """
    Generate a batch ID for task grouping.

    Args:
        session_id: Current chat session ID

    Returns:
        Batch ID string
    """
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"batch-{session_id}-{timestamp}"
