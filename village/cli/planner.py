import click

from village.logging import get_logger
from village.roles import run_role_chat
from village.workflow.loader import WorkflowLoader, WorkflowLoadError
from village.workflow.planner import Planner

logger = get_logger(__name__)


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
def list_workflows() -> None:
    """List available workflow templates."""
    loader = _get_loader()
    names = loader.list_workflows()
    if not names:
        click.echo("No workflows found.")
        return
    for name in names:
        click.echo(name)


@planner_group.command("show")
@click.argument("name", required=False)
@click.pass_context
def show_workflow(ctx: click.Context, name: str | None) -> None:
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
        choice = click.prompt("Which workflow?", type=int)
        if choice < 1 or choice > len(names):
            raise click.ClickException("Invalid selection")
        name = names[choice - 1]

    assert name is not None
    try:
        wf = loader.load(name)
    except WorkflowLoadError as e:
        raise click.ClickException(str(e))

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
        goal = click.prompt("Describe the workflow goal")

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
        choice = click.prompt("Select workflow number", type=int)
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
        feedback = click.prompt("Feedback (empty to finish)", default="")
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
