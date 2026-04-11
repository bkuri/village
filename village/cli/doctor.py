"""Doctor command - project health diagnostics."""

import json
import subprocess
from dataclasses import asdict
from pathlib import Path

import click

from village.config import get_config
from village.doctor import format_report, run_analyzers
from village.doctor.base import Finding
from village.doctor.builtins import BUILTIN_ANALYZERS
from village.logging import get_logger

logger = get_logger(__name__)


def _run_diagnose(
    ctx: click.Context,
    json_output: bool,
    output: str | None,
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

    config.village_dir.mkdir(parents=True, exist_ok=True)
    diagnosis_path = config.village_dir / "diagnosis.json"
    diagnosis_data = {
        "results": [asdict(r) for r in results],
        "summary": {
            "total_findings": sum(len(r.findings) for r in results),
            "analyzers_run": len(results),
            "analyzers_with_errors": sum(1 for r in results if r.error),
        },
    }
    diagnosis_path.write_text(json.dumps(diagnosis_data, indent=2), encoding="utf-8")

    fmt = "json" if json_output else "text"
    report = format_report(results, format=fmt)

    if output:
        Path(output).write_text(report)
        click.echo(f"Report written to {output}")
    else:
        click.echo(report)


@click.group(invoke_without_command=True)
@click.pass_context
def doctor_group(ctx: click.Context) -> None:
    """Run project health diagnostics."""
    if ctx.invoked_subcommand is not None:
        return
    ctx.invoke(
        diagnose,
        json_output=False,
        output=None,
        only=None,
        sequential=False,
    )


@doctor_group.command("diagnose")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--output", type=click.Path(), help="Write report to file")
@click.option("--only", type=str, help="Only run specified analyzers (comma-separated)")
@click.option("--sequential", is_flag=True, help="Run analyzers sequentially (not in parallel)")
@click.pass_context
def diagnose(
    ctx: click.Context,
    json_output: bool,
    output: str | None,
    only: str | None,
    sequential: bool,
) -> None:
    """Run project health diagnostics.

    Analyzes the project for issues and writes results to .village/diagnosis.json.

    \b
    Examples:
        village doctor                  # Run all analyzers
        village doctor diagnose         # Run all analyzers
        village doctor --json           # JSON output
        village doctor diagnose --only tests     # Only run test analyzer
        village doctor diagnose --sequential      # Run analyzers one at a time
    """
    _run_diagnose(ctx, json_output, output, only, sequential)


@doctor_group.command()
@click.option("--fix", is_flag=True, help="Auto-apply fixable recommendations")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def prescribe(ctx: click.Context, fix: bool, json_output: bool) -> None:
    """Generate recommendations from diagnosis results.

    Reads .village/diagnosis.json (runs diagnose first if missing).
    Use --fix to auto-apply fixable items (ruff, stale branch cleanup).

    \b
    Examples:
        village doctor prescribe              # Show recommendations
        village doctor prescribe --fix        # Apply fixable items
        village doctor prescribe --fix --json # JSON output with fixes
    """
    config = ctx.obj.get("config") if ctx.obj else get_config()
    diagnosis_path = config.village_dir / "diagnosis.json"

    if not diagnosis_path.exists():
        click.echo("No diagnosis found. Running diagnose first...")
        ctx.invoke(diagnose, json_output=False, output=None, only=None, sequential=False)

    if not diagnosis_path.exists():
        click.echo("Error: diagnosis still not available.")
        raise SystemExit(1)

    data = json.loads(diagnosis_path.read_text(encoding="utf-8"))
    findings: list[Finding] = []
    for result_data in data.get("results", []):
        for f in result_data.get("findings", []):
            findings.append(
                Finding(
                    id=f["id"],
                    title=f["title"],
                    description=f["description"],
                    severity=f["severity"],
                    category=f["category"],
                    file=f.get("file"),
                    line=f.get("line"),
                    metadata=f.get("metadata"),
                )
            )

    if not findings:
        click.echo("No findings to address.")
        return

    recommendations: list[dict[str, str | bool]] = []
    fixable_groups: dict[str, list[str]] = {}

    for finding in findings:
        category = finding.category
        if category == "quality":
            recommendations.append(
                {
                    "finding": finding.title,
                    "action": "Auto-fixable: run `ruff check --fix`",
                    "fixable": True,
                    "category": category,
                }
            )
            fixable_groups.setdefault("ruff", [])
        elif category == "git" and finding.metadata and finding.metadata.get("type") == "merged":
            branch = finding.metadata.get("branch", "")
            recommendations.append(
                {
                    "finding": finding.title,
                    "action": f"Auto-fixable: run `git branch -d {branch}`",
                    "fixable": True,
                    "category": category,
                }
            )
            fixable_groups.setdefault("git-branch", []).append(branch)
        elif category == "test":
            recommendations.append(
                {
                    "finding": finding.title,
                    "action": "Investigate: review test failure and fix the underlying issue",
                    "fixable": False,
                    "category": category,
                }
            )
        else:
            recommendations.append(
                {
                    "finding": finding.title,
                    "action": f"Review: {finding.description[:100]}",
                    "fixable": False,
                    "category": category,
                }
            )

    fixable_count = (
        sum(len(v) for v in fixable_groups.values())
        if fixable_groups
        else len([r for r in recommendations if r["fixable"]])
    )

    if json_output:
        click.echo(json.dumps({"recommendations": recommendations, "fixable_count": fixable_count}, indent=2))
        return

    click.echo(f"\n{len(recommendations)} recommendation(s):\n")
    for i, rec in enumerate(recommendations, 1):
        fixable_marker = "[FIX]" if rec["fixable"] else "[MANUAL]"
        click.echo(f"  {i}. {fixable_marker} {rec['finding']}")
        click.echo(f"     {rec['action']}")

    if not fix:
        click.echo(f"\n{fixable_count} item(s) can be auto-fixed. Use --fix to apply.")
        return

    click.echo("\nApplying auto-fix(es)...")
    applied = 0

    if "ruff" in fixable_groups:
        result = subprocess.run(["ruff", "check", "--fix", "."], capture_output=True, text=True)
        if result.returncode == 0 or result.returncode == 1:
            click.echo("  Applied ruff --fix")
            applied += 1
        else:
            click.echo(f"  Failed ruff --fix: {result.stderr.strip()}")

    for branch in fixable_groups.get("git-branch", []):
        result = subprocess.run(["git", "branch", "-d", branch], capture_output=True, text=True)
        if result.returncode == 0:
            click.echo(f"  Deleted branch: {branch}")
            applied += 1
        else:
            click.echo(f"  Failed to delete {branch}: {result.stderr.strip()}")

    click.echo(f"\nApplied {applied} fix(es).")
