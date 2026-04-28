from __future__ import annotations

import json
import pathlib

import click

from village.logging import get_logger
from village.prompt import sync_prompt
from village.roles import run_role_chat
from village.workflow.loader import WorkflowLoader, WorkflowLoadError
from village.workflow.planner import Planner

logger = get_logger(__name__)


def _get_plan_slugs() -> list[str]:
    """Get list of plan slugs for shell completion."""
    try:
        from village.config import get_config
        from village.plans.store import FilePlanStore

        config = get_config()
        plans_dir = config.git_root / ".village" / "plans"
        store = FilePlanStore(plans_dir)
        plans = store.list()
        return [p.slug for p in plans]
    except Exception:
        return []


def _complete_slug(ctx: click.Context, param: click.Parameter, incomplete: str) -> list[str]:
    """Shell completion for plan slugs."""
    return [s for s in _get_plan_slugs() if s.startswith(incomplete)]


def _get_loader() -> WorkflowLoader:
    return WorkflowLoader()


@click.group(invoke_without_command=True)
@click.pass_context
def planner_group(ctx: click.Context) -> None:
    """Design and manage specs."""
    if ctx.invoked_subcommand is not None:
        return
    run_role_chat("planner")


@planner_group.command("workflows")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def list_workflows(json_output: bool) -> None:
    """List available workflow templates."""
    loader = _get_loader()
    names = loader.list_workflows()
    if json_output:
        click.echo(json.dumps(names, indent=2))
        return
    if not names:
        click.echo("No workflows found.")
        return
    for name in names:
        click.echo(name)


@planner_group.command("show")
@click.argument("name", required=False)
@click.option("--json", "json_output", is_flag=True, help="JSON output")
@click.pass_context
def show_workflow(ctx: click.Context, name: str | None, json_output: bool) -> None:
    """Display workflow steps."""
    loader = _get_loader()

    if name is None:
        names = loader.list_workflows()
        if not names:
            click.echo("No workflows found.")
            return
        click.echo("Available workflows:")
        for i, n in enumerate(names, 1):
            click.echo(f"  {i}. {n}")
        choice = int(sync_prompt("Which workflow?", type=int))
        if choice < 1 or choice > len(names):
            raise click.ClickException("Invalid selection")
        name = names[choice - 1]

    assert name is not None
    try:
        wf = loader.load(name)
    except WorkflowLoadError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e), "name": name}, indent=2, sort_keys=True))
            return
        raise click.ClickException(str(e))

    if json_output:
        steps_data = []
        for step in wf.steps:
            resolved = step.resolve()
            steps_data.append(
                {
                    "name": step.name,
                    "type": step.type.value,
                    "tools": resolved.tools or [],
                    "traits": list(resolved.traits.keys()) if resolved.traits else [],
                    "async": step.async_exec,
                }
            )
        click.echo(
            json.dumps(
                {
                    "name": wf.name,
                    "description": wf.description,
                    "version": wf.version,
                    "inputs": wf.inputs or [],
                    "steps": steps_data,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    click.echo(f"Workflow: {wf.name}")
    click.echo(f"Description: {wf.description}")
    click.echo(f"Version: {wf.version}")
    if wf.inputs:
        click.echo(f"Inputs: {', '.join(wf.inputs)}")
    click.echo(f"\nSteps ({len(wf.steps)}):")
    for i, step in enumerate(wf.steps, 1):
        resolved = step.resolve()
        click.echo(f"  {i}. {step.name} (type: {step.type.value})")
        if resolved.tools:
            click.echo(f"     tools: {', '.join(resolved.tools)}")
        if resolved.traits:
            click.echo(f"     traits: {', '.join(resolved.traits)}")
        if step.async_exec:
            click.echo("     async: true")


@planner_group.command("design")
@click.argument("goal", required=False)
def design_workflow(goal: str | None) -> None:
    """Design a new workflow interactively."""
    if goal is None:
        goal = sync_prompt("Describe the workflow goal")

    assert goal is not None
    loader = _get_loader()
    planner = Planner()
    existing = loader.list_workflows()
    result = planner.design(goal, existing)
    click.echo(result)


@planner_group.command("refine")
@click.argument("goal", required=False)
def refine_workflow(goal: str | None) -> None:
    """Refine an existing workflow interactively."""
    loader = _get_loader()

    if goal is None:
        names = loader.list_workflows()
        if not names:
            click.echo("No workflows found to refine.")
            return
        click.echo("Available workflows:")
        for i, n in enumerate(names, 1):
            click.echo(f"  {i}. {n}")
        choice = int(sync_prompt("Select workflow number", type=int))
        if choice < 1 or choice > len(names):
            raise click.ClickException("Invalid selection")
        goal = names[choice - 1]

    assert goal is not None
    planner = Planner()
    existing = loader.list_workflows()
    result = planner.design(goal, existing)
    click.echo(result)

    click.echo("\n--- Refinement mode ---")
    while True:
        feedback = sync_prompt("Feedback (empty to finish)", default="")
        if not feedback:
            break
        result = planner.refine(result, feedback)
        click.echo(f"\n{result}")


@planner_group.command("inspect")
@click.argument("spec_id", required=False)
@click.option("--fix", "fix_mode", is_flag=True, help="Amend spec files with findings")
@click.option("--specs-dir", type=click.Path(), default="specs", help="Directory containing spec files")
def inspect_specs(spec_id: str | None, fix_mode: bool, specs_dir: str) -> None:
    """Review specs for cross-cutting issues."""

    from village.config import get_config
    from village.loop import find_specs

    config = get_config()
    specs_path = config.git_root / specs_dir

    if not specs_path.is_dir():
        raise click.ClickException(f"Specs directory not found: {specs_path}")

    all_specs = find_specs(specs_path)
    if not all_specs:
        raise click.ClickException("No specs found.")

    if spec_id:
        target_specs = [s for s in all_specs if spec_id in s.name]
        if not target_specs:
            raise click.ClickException(f"Spec '{spec_id}' not found.")
    else:
        target_specs = all_specs

    click.echo(f"Reviewing {len(target_specs)} spec(s)...")

    spec_contents: list[dict[str, str]] = []
    for spec in target_specs:
        try:
            content = spec.path.read_text(encoding="utf-8")
            spec_contents.append({"name": spec.name, "content": content})
        except (IOError, OSError) as e:
            click.echo(f"Warning: Could not read {spec.name}: {e}")

    if not spec_contents:
        raise click.ClickException("No spec contents to review.")

    all_specs_text = "\n\n---\n\n".join(f"## {s['name']}\n\n{s['content']}" for s in spec_contents)

    inspector_md = config.git_root / "inspector.md"
    inspector_context = ""
    if inspector_md.exists():
        inspector_context = inspector_md.read_text(encoding="utf-8")

    voice_md = config.git_root / "VOICE.md"
    voice_context = ""
    if voice_md.exists():
        voice_context = voice_md.read_text(encoding="utf-8")

    fix_note = (
        "\n\n**The --fix flag IS set.** Amend spec files after producing the report."
        if fix_mode
        else "\n\n**The --fix flag is NOT set.** Produce the report only — do NOT modify any spec files."
    )

    inspect_prompt = (
        "# Inspect — Review specs\n\n"
        "You are the **inspector**. You do NOT implement anything.\n\n"
        "## Project Context\n\n"
        f"{voice_context}\n\n"
        "## Project Constraints\n\n"
        f"{inspector_context}\n\n"
        "## Specs to Review\n\n"
        f"{all_specs_text}\n"
        f"{fix_note}\n\n"
        "## Output Format\n\n"
        "Produce a structured report:\n\n"
        "```\n"
        "--- Inspect Report ---\n\n"
        "[OK] spec-name.md — No issues\n\n"
        "[ISSUE] spec-name.md — N finding(s)\n"
        "  IN-1: [Category] [Short title]\n"
        "    [explanation]\n"
        "    Suggestion: [concrete improvement]\n"
        "```\n\n"
        "Categories: Structure, Testability, Completeness, Ambiguity, Cross-cutting\n\n"
        "## Fix Mode\n\n"
        "If --fix was passed, append an '## Inspect Notes' section to each spec with findings.\n"
        "These become hard constraints for the builder.\n\n"
        "Output `<promise>DONE</promise>` when complete.\n"
    )

    click.echo("\nRunning inspection via LLM...\n")

    from village.llm.factory import get_llm_client

    llm = get_llm_client(config, agent_name="planner")

    response = llm.call(
        inspect_prompt, system_prompt="You are a spec inspector. Review specs for quality and cross-cutting issues."
    )

    click.echo(response)

    if fix_mode:
        from village.loop import detect_promise

        if detect_promise(response):
            click.echo("\nInspection complete — checking for amended specs.")
        else:
            click.echo("\nWarning: No completion signal detected. Specs may not have been amended.")

        amended = 0
        for spec in target_specs:
            try:
                content = spec.path.read_text(encoding="utf-8")
                if "Inspect Notes" in content:
                    click.echo(f"  [OK] {spec.name} — inspect notes added")
                    amended += 1
            except (IOError, OSError):
                pass

        if amended == 0:
            click.echo("  No specs were amended.")
        else:
            click.echo(f"\n{amended} spec(s) amended.")


@planner_group.command("list")
@click.option("--all", "filter_state", flag_value="all", default=True, help="Show all plans")
@click.option("--drafts", "filter_state", flag_value="draft", help="Show drafts only")
@click.option("--pending", "filter_state", flag_value="approved", help="Show approved (in progress) plans")
@click.option("--completed", "filter_state", flag_value="landed", help="Show landed plans")
@click.option("--aborted", "filter_state", flag_value="aborted", help="Show aborted plans")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def list_plans(filter_state: str, json_output: bool) -> None:
    """List all plans."""
    from village.config import get_config
    from village.plans.models import PlanState
    from village.plans.store import FilePlanStore

    config = get_config()
    plans_dir = config.git_root / ".village" / "plans"
    store = FilePlanStore(plans_dir)

    state = None if filter_state == "all" else PlanState(filter_state)
    plans = store.list(state=state)

    if not plans:
        if json_output:
            click.echo(json.dumps([], indent=2))
            return
        click.echo("No plans found.")
        return

    if json_output:
        output = [
            {
                "slug": p.slug,
                "state": p.state.value,
                "objective": p.objective,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
                "task_ids": p.task_ids,
                "worktree_path": p.worktree_path,
            }
            for p in plans
        ]
        click.echo(json.dumps(output, indent=2, sort_keys=True, default=str))
        return

    for plan in plans:
        status_icon = {
            PlanState.DRAFT: "○",
            PlanState.APPROVED: "◐",
            PlanState.LANDED: "✓",
            PlanState.ABORTED: "✗",
            PlanState.PURGED: "⊘",
        }.get(plan.state, "?")
        click.echo(f"{status_icon} {plan.slug} [{plan.state.value}]")
        click.echo(f"   {plan.objective[:60]}...")


@planner_group.command("plan")
@click.argument("slug", shell_complete=_complete_slug)
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def show_plan(slug: str, json_output: bool) -> None:
    """Show plan details."""
    from village.config import get_config
    from village.plans.store import FilePlanStore, PlanNotFoundError

    config = get_config()
    plans_dir = config.git_root / ".village" / "plans"
    store = FilePlanStore(plans_dir)

    try:
        plan = store.get(slug)
    except PlanNotFoundError:
        if json_output:
            click.echo(json.dumps({"error": f"Plan '{slug}' not found", "slug": slug}, indent=2, sort_keys=True))
            return
        raise click.ClickException(f"Plan '{slug}' not found")

    if json_output:
        click.echo(
            json.dumps(
                {
                    "slug": plan.slug,
                    "state": plan.state.value,
                    "objective": plan.objective,
                    "created_at": plan.created_at.isoformat(),
                    "updated_at": plan.updated_at.isoformat(),
                    "task_ids": plan.task_ids,
                    "worktree_path": plan.worktree_path,
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
        return

    click.echo(f"# {plan.slug}")
    click.echo(f"State: {plan.state.value}")
    click.echo(f"Objective: {plan.objective}")
    click.echo(f"Created: {plan.created_at}")
    click.echo(f"Tasks: {len(plan.task_ids)}")
    if plan.task_ids:
        click.echo("  - " + "\n  - ".join(plan.task_ids))


@planner_group.command("approve")
@click.argument("slug", shell_complete=_complete_slug)
@click.option("--name", "name_override", default=None, help="Override worktree name")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def approve_plan(slug: str, name_override: str | None, json_output: bool) -> None:
    """Approve a plan and create worktree to start development."""
    from village.config import get_config
    from village.plans.models import PlanState
    from village.plans.store import FilePlanStore, PlanNotFoundError

    config = get_config()
    plans_dir = config.git_root / ".village" / "plans"
    store = FilePlanStore(plans_dir)

    try:
        plan = store.get(slug)
    except PlanNotFoundError:
        if json_output:
            err_data = {"success": False, "slug": slug, "error": "Plan not found"}
            click.echo(json.dumps(err_data, indent=2, sort_keys=True))
            return
        raise click.ClickException(f"Plan '{slug}' not found")

    if plan.state != PlanState.DRAFT:
        if json_output:
            err_msg = f"Not a draft (current: {plan.state.value})"
            err_data = {"success": False, "slug": slug, "error": err_msg}
            click.echo(json.dumps(err_data, indent=2, sort_keys=True))
            return
        raise click.ClickException(f"Plan '{slug}' is not a draft (current state: {plan.state.value})")

    worktree_name = name_override or slug
    worktrees_dir = config.git_root / ".worktrees"
    worktree_path: pathlib.Path | None = worktrees_dir / worktree_name

    import subprocess

    subp_result = subprocess.run(
        ["git", "worktree", "add", "-b", f"plan/{worktree_name}", str(worktree_path), "HEAD"],
        capture_output=True,
        text=True,
    )

    if subp_result.returncode != 0:
        click.echo(f"Warning: worktree creation failed: {subp_result.stderr.strip()}", err=True)
        worktree_path = None

    plan.state = PlanState.APPROVED
    plan.worktree_path = str(worktree_path) if worktree_path else None
    store.update(plan)

    if json_output:
        click.echo(
            json.dumps(
                {
                    "success": True,
                    "slug": slug,
                    "worktree_path": plan.worktree_path,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    click.echo(f"Plan '{slug}' approved.")
    if worktree_path:
        click.echo(f"Worktree created: {worktree_path}")
    click.echo("Development can begin.")


@planner_group.command("delete")
@click.argument("slug", shell_complete=_complete_slug)
@click.option("--force", is_flag=True, help="Force delete non-draft plans")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def delete_plan(slug: str, force: bool, json_output: bool) -> None:
    """Delete a plan."""
    from village.config import get_config
    from village.plans.models import PlanState
    from village.plans.store import FilePlanStore, PlanNotFoundError

    config = get_config()
    plans_dir = config.git_root / ".village" / "plans"
    store = FilePlanStore(plans_dir)

    try:
        plan = store.get(slug)
    except PlanNotFoundError:
        if json_output:
            err_data = {"success": False, "slug": slug, "error": "Plan not found"}
            click.echo(json.dumps(err_data, indent=2, sort_keys=True))
            return
        raise click.ClickException(f"Plan '{slug}' not found")

    if plan.state != PlanState.DRAFT and not force:
        if json_output:
            err_msg = f"Plan is {plan.state.value}. Use --force to delete non-draft plans."
            err_data = {"success": False, "slug": slug, "error": err_msg}
            click.echo(json.dumps(err_data, indent=2, sort_keys=True))
            return
        raise click.ClickException(f"Plan '{slug}' is {plan.state.value}. Use --force to delete non-draft plans.")

    if plan.worktree_path:
        if json_output:
            err_msg = f"Plan has worktree at {plan.worktree_path}"
            err_data = {"success": False, "slug": slug, "error": err_msg}
            click.echo(json.dumps(err_data, indent=2, sort_keys=True))
            return
        click.echo(f"Warning: Plan has worktree at {plan.worktree_path}", err=True)
        click.echo("Delete the worktree manually before deleting the plan.", err=True)
        return

    store.delete(slug)
    if json_output:
        click.echo(json.dumps({"success": True, "slug": slug}, indent=2, sort_keys=True))
        return
    click.echo(f"Plan '{slug}' deleted.")


@planner_group.command("resume")
@click.argument("slug", shell_complete=_complete_slug)
@click.option("--model", default=None, help="Model to use for the interview")
def resume_plan(slug: str, model: str | None) -> None:
    """Resume editing a draft plan with an interactive interview."""
    from village.config import get_config
    from village.llm.factory import get_llm_client
    from village.plans.interview import run_interview_session
    from village.plans.models import PlanState
    from village.plans.store import FilePlanStore, PlanNotFoundError

    config = get_config()
    plans_dir = config.git_root / ".village" / "plans"
    store = FilePlanStore(plans_dir)

    try:
        plan = store.get(slug)
    except PlanNotFoundError:
        raise click.ClickException(f"Plan '{slug}' not found")

    if plan.state != PlanState.DRAFT:
        raise click.ClickException(f"Plan '{slug}' is not a draft (current state: {plan.state.value})")

    plan_dir = plans_dir / "drafts" / slug

    llm_client = get_llm_client(config)

    run_interview_session(plan, plan_dir, llm_client)
    click.echo("Session saved.")
