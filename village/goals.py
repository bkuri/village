"""Goal hierarchy with GOALS.md support."""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Goal:
    id: str
    title: str
    description: str
    status: str = "active"
    priority: int = 2
    parent: str | None = None
    children: list[str] = field(default_factory=list)
    source: str = ""
    objectives: list[str] = field(default_factory=list)


_GOAL_HEADING_RE = re.compile(r"^##\s+(?P<id>G\d+):\s+(?P<title>.+?)\s*\[(?P<status>\w+)\]\s*$")
_OBJECTIVE_RE = re.compile(r"^-\s+\[(?P<check>[ xX])\]\s+(?P<text>.+)$")
_CHILD_RE = re.compile(r"^-\s+(?P<id>G\d+)\s*$")
_HR_RE = re.compile(r"^---+\s*$")


def parse_goals(goals_path: Path) -> list[Goal]:
    """Parse GOALS.md into Goal objects.

    Returns empty list if file is missing or empty.
    """
    if not goals_path.exists():
        return []

    content = goals_path.read_text(encoding="utf-8")
    if not content.strip():
        return []

    goals: list[Goal] = []
    current_goal: Goal | None = None
    current_section: str = ""

    for line in content.splitlines():
        goal_match = _GOAL_HEADING_RE.match(line)
        if goal_match:
            if current_goal is not None:
                goals.append(current_goal)
            current_goal = Goal(
                id=goal_match.group("id"),
                title=goal_match.group("title").strip(),
                description="",
                status=goal_match.group("status").strip().lower(),
            )
            current_section = "description"
            continue

        if current_goal is None:
            continue

        if line.strip() == "" and current_section == "description":
            continue

        if line.strip().startswith("### Objectives"):
            current_section = "objectives"
            continue

        if line.strip().startswith("### Children"):
            current_section = "children"
            continue

        if _HR_RE.match(line):
            continue

        if current_section == "description" and line.strip():
            if current_goal.description:
                current_goal.description += "\n" + line.strip()
            else:
                current_goal.description = line.strip()

        obj_match = _OBJECTIVE_RE.match(line)
        if current_section == "objectives" and obj_match:
            checked = obj_match.group("check").lower() == "x"
            text = obj_match.group("text").strip()
            if checked:
                current_goal.objectives.append(text)

        child_match = _CHILD_RE.match(line)
        if current_section == "children" and child_match:
            current_goal.children.append(child_match.group("id"))

    if current_goal is not None:
        goals.append(current_goal)

    _resolve_parents(goals)
    return goals


def _resolve_parents(goals: list[Goal]) -> None:
    """Set parent references from children lists."""
    goal_map = {g.id: g for g in goals}
    for goal in goals:
        for child_id in goal.children:
            child = goal_map.get(child_id)
            if child is not None:
                child.parent = goal.id


def get_goal_chain(goals: list[Goal], goal_id: str) -> list[Goal]:
    """Get chain from root ancestor to the given goal."""
    goal_map = {g.id: g for g in goals}
    target = goal_map.get(goal_id)
    if target is None:
        return []

    chain: list[Goal] = []
    current: Goal | None = target
    while current is not None:
        chain.append(current)
        current = goal_map.get(current.parent) if current.parent else None

    chain.reverse()
    return chain


def get_active_goals(goals: list[Goal]) -> list[Goal]:
    """Get all goals with active status."""
    return [g for g in goals if g.status == "active"]


def get_objective_coverage(goals: list[Goal]) -> dict[str, float]:
    """Calculate completion percentage per goal.

    Returns a dict mapping goal ID to coverage ratio (0.0 to 1.0).
    Goals with no objectives get 0.0.
    """
    coverage: dict[str, float] = {}
    for goal in goals:
        total = len(goal.objectives)
        if total == 0:
            coverage[goal.id] = 0.0
        else:
            completed = sum(1 for obj in goal.objectives if not obj.startswith("☐"))
            coverage[goal.id] = completed / total
    return coverage


def _parse_objectives_raw(goals_path: Path) -> dict[str, tuple[list[str], list[str]]]:
    """Parse completed and incomplete objectives per goal from raw file.

    Returns dict mapping goal ID to (completed_list, incomplete_list).
    """
    if not goals_path.exists():
        return {}

    content = goals_path.read_text(encoding="utf-8")
    result: dict[str, tuple[list[str], list[str]]] = {}
    current_goal_id: str | None = None
    current_section: str = ""

    for line in content.splitlines():
        goal_match = _GOAL_HEADING_RE.match(line)
        if goal_match:
            current_goal_id = goal_match.group("id")
            current_section = ""
            continue

        if current_goal_id is None:
            continue

        if line.strip().startswith("### Objectives"):
            current_section = "objectives"
            continue

        if line.strip().startswith("### Children"):
            current_section = ""
            continue

        if current_section == "objectives":
            obj_match = _OBJECTIVE_RE.match(line)
            if obj_match:
                checked = obj_match.group("check").lower() == "x"
                text = obj_match.group("text").strip()
                completed, incomplete = result.get(current_goal_id, ([], []))
                if checked:
                    completed.append(text)
                else:
                    incomplete.append(text)
                result[current_goal_id] = (completed, incomplete)

    return result


def get_objective_coverage_from_file(goals_path: Path) -> dict[str, tuple[int, int, float]]:
    """Calculate objective coverage from raw file, preserving incomplete items.

    Returns dict mapping goal ID to (completed_count, total_count, ratio).
    """
    raw = _parse_objectives_raw(goals_path)
    coverage: dict[str, tuple[int, int, float]] = {}
    for goal_id, (completed, incomplete) in raw.items():
        total = len(completed) + len(incomplete)
        ratio = len(completed) / total if total > 0 else 0.0
        coverage[goal_id] = (len(completed), total, ratio)
    return coverage


def write_goals(
    goals: list[Goal], path: Path, raw_objectives: dict[str, tuple[list[str], list[str]]] | None = None
) -> None:
    """Write goals back to GOALS.md format.

    If raw_objectives is provided, uses it to preserve checked/unchecked state.
    Otherwise, all objectives in Goal.objectives are written as checked.
    """
    lines: list[str] = ["# Project Goals", ""]

    for i, goal in enumerate(goals):
        if i > 0:
            lines.append("")
            lines.append("---")
            lines.append("")

        lines.append(f"## {goal.id}: {goal.title} [{goal.status}]")
        lines.append("")

        if goal.description:
            lines.append(goal.description)
            lines.append("")

        if raw_objectives and goal.id in raw_objectives:
            completed, incomplete = raw_objectives[goal.id]
            if completed or incomplete:
                lines.append("### Objectives")
                for obj in completed:
                    lines.append(f"- [x] {obj}")
                for obj in incomplete:
                    lines.append(f"- [ ] {obj}")
                lines.append("")
        elif goal.objectives:
            lines.append("### Objectives")
            for obj in goal.objectives:
                lines.append(f"- [x] {obj}")
            lines.append("")

        if goal.children:
            lines.append("### Children")
            for child_id in goal.children:
                lines.append(f"- {child_id}")
            lines.append("")

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
