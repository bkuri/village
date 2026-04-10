import click

from village.logging import get_logger
from village.roles import run_role_chat
from village.workflow.loader import WorkflowLoader

logger = get_logger(__name__)


def _get_loader() -> WorkflowLoader:
    return WorkflowLoader()


@click.group(invoke_without_command=True)
@click.pass_context
def builder_group(ctx: click.Context) -> None:
    """Execute and manage spec-driven builds."""
    if ctx.invoked_subcommand is not None:
        return
    run_role_chat("builder")


@builder_group.command("run")
@click.option("--specs-dir", type=click.Path(), default="specs", help="Directory containing spec files")
@click.option("--agent", "-a", default="worker", help="Agent to use for building")
@click.option("--model", "-m", default=None, help="Model override for the agent")
@click.option("--parallel", "-p", "parallel", default=1, type=int, help="Number of parallel worktrees")
@click.option("--max-iterations", "-n", default=None, type=int, help="Max iterations (default: unlimited)")
@click.option("--dry-run", is_flag=True, help="Show plan without executing")
@click.pass_context
def run_loop(
    ctx: click.Context,
    specs_dir: str,
    agent: str,
    model: str | None,
    parallel: int,
    max_iterations: int | None,
    dry_run: bool,
) -> None:
    """Run the autonomous spec-driven build loop."""

    from village.config import get_config
    from village.loop import find_incomplete_specs, find_specs
    from village.loop import run_loop as _run_loop

    config = get_config()
    specs_path = config.git_root / specs_dir

    if not specs_path.is_dir():
        raise click.ClickException(f"Specs directory not found: {specs_path}")

    all_specs = find_specs(specs_path)
    if not all_specs:
        raise click.ClickException(f"No specs found in {specs_path}")

    incomplete = find_incomplete_specs(specs_path)
    completed = len(all_specs) - len(incomplete)

    click.echo(f"Specs: {len(all_specs)} total, {completed} complete, {len(incomplete)} remaining")
    if incomplete:
        click.echo(f"Next: {incomplete[0].name}")
    if dry_run:
        click.echo("Dry run: no changes will be made")
        return

    click.echo(f"Starting build loop (max_iterations={max_iterations or 'unlimited'})...")
    click.echo("Press Ctrl+C to stop.\n")

    try:
        result = _run_loop(
            specs_dir=specs_path,
            agent=agent,
            model=model,
            max_iterations=max_iterations,
            dry_run=dry_run,
            config=config,
        )

        click.echo(f"\nBuild loop finished ({result.iterations} iterations)")
        click.echo(f"Completed: {result.completed_specs} / {result.total_specs}")
        if result.remaining:
            click.echo(f"Remaining: {', '.join(result.remaining)}")
            click.echo("\nRun again to continue.")
        else:
            click.echo("All specs complete!")
    except KeyboardInterrupt:
        click.echo("\nBuild loop stopped by user.")
    except Exception as e:
        raise click.ClickException(str(e))


@builder_group.command("status")
@click.argument("run_id", required=False)
def run_status(run_id: str | None) -> None:
    """Show build loop status."""

    from village.config import get_config
    from village.loop import find_specs

    config = get_config()
    specs_path = config.git_root / "specs"

    if not specs_path.is_dir():
        click.echo("No specs directory found.")
        return

    specs = find_specs(specs_path)
    if not specs:
        click.echo("No specs found.")
        return

    complete = sum(1 for s in specs if s.is_complete)
    incomplete = [s for s in specs if not s.is_complete]

    click.echo(f"Specs: {len(specs)} total, {complete} complete, {len(incomplete)} remaining")
    if incomplete:
        click.echo("\nIncomplete specs:")
        for s in incomplete:
            click.echo(f"  - {s.name}")
    if complete:
        click.echo(f"\nComplete specs: {complete}")


@builder_group.command("stop")
@click.argument("run_id", required=False)
def stop_run(run_id: str | None) -> None:
    """Stop a running build loop."""
    click.echo("Stop not yet implemented. Use Ctrl+C in the running terminal.")


@builder_group.command("cancel", hidden=True)
@click.argument("run_id", required=False)
def cancel_run(run_id: str | None) -> None:
    """Alias for stop."""
    from click import Context

    ctx = Context(stop_run)
    ctx.invoke(stop_run, run_id=run_id)


@builder_group.command("logs")
@click.argument("run_id", required=False)
@click.option("--follow", is_flag=True, help="Follow log output")
def show_logs(run_id: str | None, follow: bool) -> None:
    """Show build loop logs."""
    click.echo("Log viewing not yet implemented.")


@builder_group.command("resume")
@click.argument("run_id", required=False)
def resume_run(run_id: str | None) -> None:
    """Resume a stopped build loop."""

    from village.config import get_config
    from village.loop import find_incomplete_specs

    config = get_config()
    specs_path = config.git_root / "specs"

    if not specs_path.is_dir():
        raise click.ClickException("No specs directory found.")

    incomplete = find_incomplete_specs(specs_path)
    if not incomplete:
        click.echo("All specs complete. Nothing to resume.")
        return

    click.echo(f"Resuming: {len(incomplete)} incomplete specs")
    click.echo("Use 'builder run' to continue.")
