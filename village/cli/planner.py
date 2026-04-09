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
    """Design and manage workflows."""
    if ctx.invoked_subcommand is not None:
        return
    run_role_chat("planner")


@planner_group.command("workflows")
def list_workflows() -> None:
    """List available workflows."""
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
            click.echo(f"     traits: {resolved.traits}")
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
