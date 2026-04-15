"""Wave-based label evolution.

Waves are triggered when a task completes (DONE). The wave evaluates all
tasks in the current plan and proposes label refinements based on:
- Actual implementation complexity discovered
- Logical groupings that emerge during development
- Dependency relationships that become clearer

The agent owns label evolution. Users review/accept/reject proposals.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from village.stack.labels import parse_stack_labels


@dataclass
class LabelProposal:
    """A proposed label change for a task."""

    task_id: str
    current_labels: list[str] = field(default_factory=list)
    proposed_labels: list[str] = field(default_factory=list)
    reason: str = ""
    layer_change: int = 0
    group_change: str | None = None


@dataclass
class Wave:
    """A wave of label evolution proposals."""

    wave_number: int
    created_at: datetime = field(default_factory=datetime.now)
    proposals: list[LabelProposal] = field(default_factory=list)
    status: str = "pending"  # pending, accepted, rejected, superseded


@dataclass
class WaveResult:
    """Result of a wave evaluation."""

    wave: Wave
    accepted: bool
    accepted_proposals: list[LabelProposal] = field(default_factory=list)
    rejected_reason: str | None = None


def analyze_task_complexity(
    task: dict[str, Any],
    all_tasks: list[dict[str, Any]],
) -> int:
    """Analyze a task and estimate its stack layer based on complexity.

    Returns suggested layer number (1 = closest to trunk).
    """
    deps = task.get("depends_on", [])
    has_dependencies = len(deps) > 0

    labels = task.get("labels", [])
    label_info = parse_stack_labels(task["id"], labels)
    base_layer = label_info.layer

    if has_dependencies:
        return base_layer + 1
    return base_layer


def suggest_group_assignment(
    task: dict[str, Any],
    all_tasks: list[dict[str, Any]],
) -> str | None:
    """Suggest a group name based on task characteristics.

    Returns suggested stack:group value or None for auto-grouping.
    """
    title = task.get("title", "").lower()

    if any(word in title for word in ["auth", "login", "password", "session", "token"]):
        return "auth"
    if any(word in title for word in ["api", "endpoint", "route", "controller"]):
        return "api"
    if any(word in title for word in ["db", "database", "model", "schema", "migration"]):
        return "database"
    if any(word in title for word in ["ui", "frontend", "component", "page", "view"]):
        return "frontend"
    if any(word in title for word in ["test", "spec"]):
        return "tests"
    if any(word in title for word in ["config", "setting", "env"]):
        return "config"

    return None


def evaluate_wave(
    tasks: list[dict[str, Any]],
    wave_number: int = 1,
) -> Wave:
    """Evaluate tasks and create label evolution proposals.

    This is the main entry point for wave evaluation. It analyzes all tasks
    and creates proposals for label refinements.
    """
    wave = Wave(wave_number=wave_number)

    for task in tasks:
        label_info = parse_stack_labels(task["id"], task.get("labels", []))
        current = task.get("labels", [])

        suggested_layer = analyze_task_complexity(task, tasks)
        suggested_group = suggest_group_assignment(task, tasks)

        proposed = []
        if suggested_layer != label_info.layer:
            proposed.append(f"stack:layer:{suggested_layer}")
        if suggested_group and label_info.group_name is None:
            proposed.append(f"stack:group:{suggested_group}")
        elif suggested_group and label_info.group_name != suggested_group:
            proposed.append(f"stack:group:{suggested_group}")

        if proposed and proposed != [label for label in current if label.startswith("stack:")]:
            proposal = LabelProposal(
                task_id=task["id"],
                current_labels=current,
                proposed_labels=current + [p for p in proposed if p not in current],
                reason=f"Suggested layer {suggested_layer}, group {suggested_group}",
                layer_change=suggested_layer - label_info.layer,
                group_change=suggested_group if label_info.group_name != suggested_group else None,
            )
            wave.proposals.append(proposal)

    return wave


def apply_proposals(
    tasks: list[dict[str, Any]],
    proposals: list[LabelProposal],
) -> list[dict[str, Any]]:
    """Apply accepted proposals to tasks.

    Returns updated task list.
    """
    updated = []
    proposal_map = {p.task_id: p for p in proposals}

    for task in tasks:
        if task["id"] in proposal_map:
            proposal = proposal_map[task["id"]]
            updated_task = task.copy()
            updated_task["labels"] = proposal.proposed_labels
            updated.append(updated_task)
        else:
            updated.append(task)

    return updated


def format_wave_summary(wave: Wave) -> str:
    """Format a wave as a human-readable summary."""
    lines = [f"## Wave {wave.wave_number}"]
    lines.append(f"Proposals: {len(wave.proposals)}")

    if not wave.proposals:
        lines.append("No changes suggested.")
        return "\n".join(lines)

    lines.append("")
    for proposal in wave.proposals:
        lines.append(f"### {proposal.task_id}")
        if proposal.layer_change:
            lines.append(f"  Layer: {proposal.layer_change:+d}")
        if proposal.group_change:
            lines.append(f"  Group: {proposal.group_change}")
        lines.append(f"  Reason: {proposal.reason}")

    lines.append("")
    lines.append("Accept these proposals? (yes/no)")
    lines.append("If no, explain why and suggest alternatives:")

    return "\n".join(lines)
