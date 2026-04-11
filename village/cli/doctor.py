"""Doctor command - project health diagnostics."""

import asyncio
from pathlib import Path

import click

from village.config import get_config
from village.doctor import (
    create_tasks_from_findings,
    format_report,
    interactive_select,
    run_analyzers,
)
from village.doctor.builtins import BUILTIN_ANALYZERS
from village.logging import get_logger

logger = get_logger(__name__)


def _run_check(
    ctx: click.Context,
    json_output: bool,
    output: str | None,
    prescribe: bool,
    preselect: str | None,
    only: str | None,
    sequential: bool,
) -> None:
    config = ctx.obj.get("config") if ctx.obj else get_config()

    analyzers = []
    only_list = [x.strip() for x in only.split(",")] if only else None

    for analyzer_cls in BUILTIN_ANALYZERS:
        analyzer = analyzer_cls()
        if not analyzer.is_available():
            logger.debug(f"Skipping {analyzer.name}: not available")
            continue
        if only_list and analyzer.name not in only_list:
            continue
        analyzers.append(analyzer)

    if not analyzers:
        click.echo("No analyzers available to run.")
        return

    click.echo(f"Running {len(analyzers)} analyzers...")

    results = run_analyzers(analyzers, parallel=not sequential)

    fmt = "json" if json_output else "text"
    report = format_report(results, format=fmt)

    if output:
        Path(output).write_text(report)
        click.echo(f"Report written to {output}")
    else:
        click.echo(report)

    if prescribe:
        selected = interactive_select(results, preselect=preselect)
        if selected:
            click.echo(f"\nCreating {len(selected)} tasks...")
            created = asyncio.run(create_tasks_from_findings(selected, config))
            for title, task_id in created.items():
                click.echo(f"  {task_id}: {title}")


@click.group(invoke_without_command=True)
@click.pass_context
def doctor_group(ctx: click.Context) -> None:
    """Run project health diagnostics."""
    if ctx.invoked_subcommand is not None:
        return
    ctx.invoke(
        check,
        json_output=False,
        output=None,
        prescribe=False,
        preselect=None,
        only=None,
        sequential=False,
    )


@doctor_group.command("check")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--output", type=click.Path(), help="Write report to file")
@click.option("--prescribe", is_flag=True, help="Interactively create tasks from findings")
@click.option(
    "--preselect",
    type=click.Choice(["all", "high", "medium"]),
    default=None,
    help="Pre-select findings by severity: all, high, or medium (includes high)",
)
@click.option("--only", type=str, help="Only run specified analyzers (comma-separated)")
@click.option("--sequential", is_flag=True, help="Run analyzers sequentially (not in parallel)")
@click.pass_context
def check(
    ctx: click.Context,
    json_output: bool,
    output: str | None,
    prescribe: bool,
    preselect: str | None,
    only: str | None,
    sequential: bool,
) -> None:
    """Run project health diagnostics.

    Analyzes the project for issues and optionally creates tasks to fix them.

    \b
    Examples:
        village doctor                  # Run all analyzers
        village doctor --json           # JSON output
        village doctor --prescribe      # Select findings to create as tasks
        village doctor --prescribe --preselect all     # Pre-select all findings
        village doctor --prescribe --preselect high    # Pre-select high severity
        village doctor --prescribe --preselect medium  # Pre-select medium+high
        village doctor --only tests     # Only run test analyzer
    """
    _run_check(ctx, json_output, output, prescribe, preselect, only, sequential)
