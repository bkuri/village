"""Stack label parsing and resolution.

Labels drive PR stacking:
- stack:layer:N - Order in stack (1 = closest to trunk)
- stack:group:<name> - Logical grouping (tasks in same group = one PR)
- stack:flat - Force monolithic PR (escape hatch)
"""

import re
from dataclasses import dataclass, field
from typing import Any

from village.stack.core import Stack, StackGroup

LABEL_LAYER_PATTERN = re.compile(r"^stack:layer:(\d+)$")
LABEL_GROUP_PATTERN = re.compile(r"^stack:group:(.+)$")
LABEL_PROJECT_PATTERN = re.compile(r"^project:(.+)$")
LABEL_FLAT = "stack:flat"


@dataclass
class TaskLabelInfo:
    """Parsed label information for a task."""

    task_id: str
    layer: int = 1
    group_name: str | None = None
    is_flat: bool = False
    project: str | None = None
    raw_labels: list[str] = field(default_factory=list)


def parse_stack_labels(task_id: str, labels: list[str]) -> TaskLabelInfo:
    """Parse stack labels from a task.

    Args:
        task_id: The task ID for error messages
        labels: List of label strings from the task

    Returns:
        TaskLabelInfo with parsed values
    """
    info = TaskLabelInfo(task_id=task_id, raw_labels=labels)

    for label in labels:
        if label == LABEL_FLAT:
            info.is_flat = True
            continue

        match = LABEL_LAYER_PATTERN.match(label)
        if match:
            info.layer = int(match.group(1))
            continue

        match = LABEL_GROUP_PATTERN.match(label)
        if match:
            info.group_name = match.group(1)
            continue

        match = LABEL_PROJECT_PATTERN.match(label)
        if match:
            info.project = match.group(1)
            continue

    return info


def group_tasks_by_label(
    tasks: list[dict[str, Any]],
    flat_override: bool = False,
    project: str | None = None,
) -> Stack:
    """Group tasks into a Stack based on their labels.

    Args:
        tasks: List of task dicts with 'id' and 'labels' keys
        flat_override: If True, force all tasks into one PR
        project: If set, only include tasks matching this project

    Returns:
        Stack with groups ordered by layer
    """
    stack = Stack()
    groups: dict[str | None, StackGroup] = {}
    max_layer = 1

    # Filter by project if specified
    if project:
        project_label = f"project:{project}"
        tasks = [t for t in tasks if project_label in t.get("labels", [])]

    if flat_override:
        stack.add_group(
            StackGroup(
                name=None,
                tasks=[t["id"] for t in tasks],
                layer=1,
            )
        )
        return stack

    for task in tasks:
        label_info = parse_stack_labels(task["id"], task.get("labels", []))
        # Use group_name if specified, otherwise use layer number as key
        key = label_info.group_name
        if key is None:
            key = f"layer:{label_info.layer}"

        # Scope the key by project so tasks from different projects
        # never merge into the same group.
        if label_info.project:
            key = f"project:{label_info.project}/{key}"

        if key not in groups:
            groups[key] = StackGroup(
                name=label_info.group_name,  # Use actual group name (None if unnamed)
                layer=label_info.layer,
                tasks=[],
            )

        groups[key].tasks.append(task["id"])
        max_layer = max(max_layer, label_info.layer)

    for group in groups.values():
        stack.add_group(group)

    return stack


def resolve_stack_order(stack: Stack) -> list[StackGroup]:
    """Resolve the order of groups in a stack by layer.

    Args:
        stack: The stack to resolve

    Returns:
        Groups sorted by layer number (ascending)
    """
    return sorted(stack.groups, key=lambda g: g.layer)


def create_pr_specs(
    tasks: list[dict[str, Any]],
    plan_slug: str,
    flat: bool = False,
    project: str | None = None,
) -> list[dict[str, Any]]:
    """Create PR specifications from tasks.

    Args:
        tasks: List of task dicts
        plan_slug: The plan slug for branch names
        flat: Force single PR
        project: If set, only include tasks matching this project

    Returns:
        List of PR specs with head, base, title, body, layer
    """
    stack = group_tasks_by_label(tasks, flat_override=flat, project=project)
    ordered = resolve_stack_order(stack)

    pr_specs = []
    for i, group in enumerate(ordered):
        layer_num = group.layer
        base = "main" if i == 0 else ordered[i - 1].name

        pr_spec = {
            "head": f"{plan_slug}/{group.name or 'main'}",
            "base": base,
            "title": f"[{layer_num}] {group.name or plan_slug}",
            "body": f"Layer {layer_num} of {plan_slug}\n\nTasks: {', '.join(group.tasks)}",
            "layer": layer_num,
            "tasks": group.tasks,
            "group_name": group.name,
        }
        pr_specs.append(pr_spec)

    return pr_specs
