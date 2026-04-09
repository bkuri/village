import click

from village.logging import get_logger
from village.workflow.builder import Builder
from village.workflow.loader import WorkflowLoader, WorkflowLoadError
from village.workflow.planner import Planner

logger = get_logger(__name__)


def _get_loader() -> WorkflowLoader:
    return WorkflowLoader()


@click.group()
def workflow() -> None:
    """Structured workflow commands."""
    pass


@workflow.command("list")
def list_workflows() -> None:
    """List available workflows."""
    loader = _get_loader()
    names = loader.list_workflows()
    if not names:
        click.echo("No workflows found.")
        return
    for name in names:
        click.echo(name)


@workflow.command("show")
@click.argument("name")
def show_workflow(name: str) -> None:
    """Display workflow steps."""
    loader = _get_loader()
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


@workflow.command("build")
@click.argument("name")
@click.option("--input", "-i", multiple=True, help="Input as KEY=VALUE")
@click.option("--dry-run", is_flag=True, help="Show plan without executing")
def build_workflow(name: str, input: tuple[str, ...], dry_run: bool) -> None:
    """Execute a workflow."""
    loader = _get_loader()
    try:
        wf = loader.load(name)
    except WorkflowLoadError as e:
        raise click.ClickException(str(e))

    inputs: dict[str, str] = {}
    for pair in input:
        if "=" not in pair:
            raise click.ClickException(f"Invalid input format: {pair} (expected KEY=VALUE)")
        key, value = pair.split("=", 1)
        inputs[key] = value

    if dry_run:
        click.echo(f"Workflow: {wf.name}")
        click.echo(f"Inputs: {inputs}")
        click.echo(f"Steps: {len(wf.steps)}")
        for step in wf.resolve_steps():
            click.echo(f"  - {step.name} ({step.type.value})")
        return

    builder = Builder()
    result = builder.run_sync(wf, inputs)

    if result.success:
        click.echo(f"Workflow '{wf.name}' completed successfully.")
        for step_result in result.step_results:
            click.echo(f"\n--- {step_result.name} ---")
            click.echo(step_result.output[:500])
            if len(step_result.output) > 500:
                click.echo("... (truncated)")
    else:
        raise click.ClickException(f"Workflow failed at step: {result.step_results[-1].name}")


@workflow.command("plan")
@click.argument("goal")
@click.option("--refine", is_flag=True, help="Interactive refinement mode")
def plan_workflow(goal: str, refine: bool) -> None:
    """Design a new workflow interactively."""
    loader = _get_loader()
    planner = Planner()
    existing = loader.list_workflows()
    result = planner.design(goal, existing)
    click.echo(result)

    if refine:
        click.echo("\n--- Refinement mode ---")
        while True:
            feedback = click.prompt("Feedback (empty to finish)", default="")
            if not feedback:
                break
            result = planner.refine(result, feedback)
            click.echo(f"\n{result}")


# Aliases
def run_workflow(name: str, inputs: tuple[str, ...], dry_run: bool) -> None:
    """Alias for build command."""
    ctx = click.Context(build_workflow)
    ctx.invoke(build_workflow, name=name, input=inputs, dry_run=dry_run)
