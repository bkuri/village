import click

from village.logging import get_logger
from village.workflow.builder import Builder
from village.workflow.loader import WorkflowLoader, WorkflowLoadError

logger = get_logger(__name__)


def _get_loader() -> WorkflowLoader:
    return WorkflowLoader()


@click.group(invoke_without_command=True)
@click.pass_context
def builder_group(ctx: click.Context) -> None:
    """Execute and manage workflow runs."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@builder_group.command("run")
@click.argument("name")
@click.option("--input", "-i", multiple=True, help="Input as KEY=VALUE")
@click.option("--dry-run", is_flag=True, help="Show plan without executing")
def run_workflow(name: str, input: tuple[str, ...], dry_run: bool) -> None:
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


@builder_group.command("status")
@click.argument("run_id")
def run_status(run_id: str) -> None:
    """Show run status."""
    click.echo(f"Run status for: {run_id}")
    click.echo("Status tracking not yet implemented.")


@builder_group.command("stop")
@click.argument("run_id")
def stop_run(run_id: str) -> None:
    """Stop a running workflow."""
    click.echo(f"Stopping run: {run_id}")
    click.echo("Run cancellation not yet implemented.")


@builder_group.command("cancel", hidden=True)
@click.argument("run_id")
def cancel_run(run_id: str) -> None:
    """Alias for stop."""
    from click import Context

    ctx = Context(stop_run)
    ctx.invoke(stop_run, run_id=run_id)


@builder_group.command("logs")
@click.argument("run_id", required=False)
@click.option("--follow", is_flag=True, help="Follow log output")
def show_logs(run_id: str | None, follow: bool) -> None:
    """List past runs or show specific run log."""
    if run_id is None:
        click.echo("No past runs found.")
        return
    click.echo(f"Logs for run: {run_id}")
    if follow:
        click.echo("Follow mode not yet implemented.")


@builder_group.command("resume")
@click.argument("run_id")
def resume_run(run_id: str) -> None:
    """Resume a failed run."""
    click.echo(f"Resuming run: {run_id}")
    click.echo("Run resume not yet implemented.")
