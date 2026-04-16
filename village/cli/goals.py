"""Standalone goals command — show and edit goal hierarchy from GOALS.md."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

import click

from village.goals import (
    Goal,
    get_active_goals,
    get_goal_chain,
    get_objective_coverage_from_file,
    parse_goals,
)

if TYPE_CHECKING:
    from village.config import Config


@click.command()
@click.option("--edit", "edit_mode", is_flag=True, help="Interactive refinement mode")
@click.option("--coverage", "show_coverage", is_flag=True, help="Show objective coverage")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def goals(edit_mode: bool, show_coverage: bool, json_output: bool) -> None:
    """Show goal hierarchy from GOALS.md."""
    from village.config import get_config

    config = get_config()
    goals_path = config.git_root / "GOALS.md"
    all_goals = parse_goals(goals_path)

    if not all_goals:
        click.echo("No GOALS.md found. Run 'village scribe curate' to bootstrap.")
        return

    if show_coverage:
        _render_coverage(all_goals, goals_path, json_output)
        return

    if edit_mode:
        _interactive_edit(all_goals, goals_path, config)
        return

    if json_output:
        _render_json(all_goals)
        return

    _render_tree(all_goals)


def _render_tree(all_goals: list[Goal]) -> None:
    root_goals = [g for g in all_goals if g.parent is None]
    child_map: dict[str, list[Goal]] = {}
    for g in all_goals:
        if g.parent:
            child_map.setdefault(g.parent, []).append(g)

    for goal in root_goals:
        _render_goal_node(goal, child_map, indent=0)


def _render_goal_node(goal: Goal, child_map: dict[str, list[Goal]], indent: int) -> None:
    prefix = "  " * indent
    status_icon = {"active": "●", "completed": "✓", "dropped": "✗"}.get(goal.status, "?")
    obj_count = len(goal.objectives)
    click.echo(f"{prefix}{status_icon} {goal.id}: {goal.title} [{goal.status}]")
    if goal.description and indent == 0:
        for line in goal.description.split("\n")[:3]:
            click.echo(f"{prefix}  {line}")
    if obj_count > 0:
        click.echo(f"{prefix}  Objectives: {obj_count} defined")
    for child in child_map.get(goal.id, []):
        _render_goal_node(child, child_map, indent + 1)


def _render_coverage(all_goals: list[Goal], goals_path: Path, json_output: bool) -> None:
    coverage = get_objective_coverage_from_file(goals_path)

    if json_output:
        output = {}
        for goal in all_goals:
            if goal.id in coverage:
                completed, total, ratio = coverage[goal.id]
                output[goal.id] = {
                    "title": goal.title,
                    "completed": completed,
                    "total": total,
                    "percentage": round(ratio * 100, 1),
                }
        click.echo(json.dumps(output, sort_keys=True, indent=2))
        return

    active = get_active_goals(all_goals)
    total_completed = 0
    total_objectives = 0

    for goal in active:
        chain = get_goal_chain(all_goals, goal.id)
        chain_str = " → ".join(g.id for g in chain)
        if goal.id in coverage:
            completed, total, ratio = coverage[goal.id]
            total_completed += completed
            total_objectives += total
            pct = round(ratio * 100, 1)
            click.echo(f"  {chain_str} {goal.title}: {completed}/{total} ({pct}%)")
        else:
            click.echo(f"  {chain_str} {goal.title}: no objectives")

    if total_objectives > 0:
        overall_pct = round(total_completed / total_objectives * 100, 1)
        click.echo(f"\nOverall: {total_completed}/{total_objectives} completed ({overall_pct}%)")


def _render_json(all_goals: list[Goal]) -> None:
    output = []
    for goal in all_goals:
        output.append(
            {
                "id": goal.id,
                "title": goal.title,
                "status": goal.status,
                "priority": goal.priority,
                "parent": goal.parent,
                "children": goal.children,
                "objectives": goal.objectives,
                "source": goal.source,
            }
        )
    click.echo(json.dumps(output, sort_keys=True, indent=2))


def _interactive_edit(all_goals: list[Goal], goals_path: Path, config: "Config") -> None:
    from village.goals import write_goals

    click.echo("Goal refinement mode")
    click.echo(f"Found {len(all_goals)} goal(s) in {goals_path}")
    click.echo("")

    for goal in all_goals:
        click.echo(f"  {goal.id}: {goal.title} [{goal.status}]")
    click.echo("")

    from village.errors import GracefulExit
    from village.prompt import InterruptGuard

    guard = InterruptGuard()

    while True:
        try:
            action = input("Action (add/edit/done/quit): ").strip().lower()
        except EOFError:
            click.echo("")
            break
        except KeyboardInterrupt:
            try:
                guard.check_interrupt()
            except GracefulExit:
                click.echo("")
                break
            continue

        if action in ("done", "quit", "q"):
            break
        elif action == "add":
            _add_goal_interactive(all_goals, goals_path)
        elif action == "edit":
            goal_id = input("Goal ID to edit: ").strip()
            _edit_goal_interactive(all_goals, goal_id)
        else:
            click.echo(f"Unknown action: {action}")

    write_goals(all_goals, goals_path)
    click.echo(f"Goals saved to {goals_path}")


def _add_goal_interactive(all_goals: list[Goal], goals_path: Path) -> None:
    from village.goals import write_goals

    next_num = len(all_goals) + 1
    goal_id = f"G{next_num}"

    try:
        title = input("Title: ").strip()
        if not title:
            click.echo("Canceled.")
            return

        description = input("Description: ").strip()
        objectives_raw = input("Objectives (comma-separated): ").strip()
    except (EOFError, KeyboardInterrupt):
        click.echo("")
        return
    objectives = [o.strip() for o in objectives_raw.split(",") if o.strip()] if objectives_raw else []

    new_goal = Goal(
        id=goal_id,
        title=title,
        description=description,
        status="active",
        objectives=objectives,
    )

    all_goals.append(new_goal)
    write_goals(all_goals, goals_path)
    click.echo(f"Added {goal_id}: {title}")


def _edit_goal_interactive(all_goals: list[Goal], goal_id: str) -> None:
    goal_map = {g.id: g for g in all_goals}
    goal = goal_map.get(goal_id)
    if goal is None:
        click.echo(f"Goal {goal_id} not found.")
        return

    click.echo(f"Editing {goal_id}: {goal.title}")
    click.echo(f"  Current status: {goal.status}")
    try:
        new_status = input("New status (active/completed/dropped): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        click.echo("")
        return
    if new_status in ("active", "completed", "dropped"):
        goal.status = new_status
        click.echo(f"  Status updated to {new_status}")
    else:
        click.echo("  No change.")
