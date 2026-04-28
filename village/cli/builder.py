import json

import click

from village.logging import get_logger
from village.prompt import sync_confirm
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
@click.option("--no-wave", is_flag=True, help="Disable wave triggers")
@click.option("--landing-dry-run", is_flag=True, help="Simulate landing without creating PRs")
@click.option("--plan", "plan_slug", default=None, help="Plan slug for state tracking")
@click.pass_context
def run_loop(
    ctx: click.Context,
    specs_dir: str,
    agent: str,
    model: str | None,
    parallel: int,
    max_iterations: int | None,
    dry_run: bool,
    no_wave: bool,
    landing_dry_run: bool,
    plan_slug: str | None,
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
            parallel=parallel,
            wave_enabled=not no_wave,
            plan_slug=plan_slug,
            landing_dry_run=landing_dry_run,
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
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def run_status(run_id: str | None, json_output: bool) -> None:
    """Show build loop status."""

    from village.config import get_config
    from village.loop import find_specs

    config = get_config()
    specs_path = config.git_root / "specs"

    if not specs_path.is_dir():
        if json_output:
            empty = {"error": "No specs directory found", "total": 0, "complete": 0, "incomplete": []}
            click.echo(json.dumps(empty, indent=2, sort_keys=True))
            return
        click.echo("No specs directory found.")
        return

    specs = find_specs(specs_path)
    if not specs:
        if json_output:
            empty = {"error": "No specs found", "total": 0, "complete": 0, "incomplete": []}
            click.echo(json.dumps(empty, indent=2, sort_keys=True))
            return
        click.echo("No specs found.")
        return

    complete = sum(1 for s in specs if s.is_complete)
    incomplete_names = [s.name for s in specs if not s.is_complete]

    if json_output:
        click.echo(
            json.dumps(
                {
                    "total": len(specs),
                    "complete": complete,
                    "incomplete": incomplete_names,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    click.echo(f"Specs: {len(specs)} total, {complete} complete, {len(incomplete_names)} remaining")
    if incomplete_names:
        click.echo("\nIncomplete specs:")
        for s in incomplete_names:
            click.echo(f"  - {s}")
    if complete:
        click.echo(f"\nComplete specs: {complete}")


@builder_group.command("cancel", hidden=True)
@click.argument("run_id", required=False)
def cancel_run(run_id: str | None) -> None:
    """Cancel a running build loop."""
    click.echo("Stop not yet implemented. Use Ctrl+C in the running terminal.")


@builder_group.command("logs")
@click.argument("task_id", required=False)
@click.option("--follow", is_flag=True, help="Follow log output")
def show_logs(task_id: str | None, follow: bool) -> None:
    """Show build loop logs for a task or all tasks."""
    import time

    from village.config import get_config
    from village.trace import TraceReader, format_trace

    config = get_config()
    reader = TraceReader(config.traces_dir)

    if task_id is None:
        task_ids = reader.list_traced_tasks()
        if not task_ids:
            raise click.ClickException(f"No traces found in {config.traces_dir}")
        click.echo(f"Traced tasks ({len(task_ids)}):")
        for tid in task_ids:
            events = reader.read(tid)
            click.echo(f"  {tid} ({len(events)} events)")
        return

    events = reader.read(task_id)
    if not events:
        raise click.ClickException(f"No traces found for {task_id}")

    if follow:
        try:
            click.echo(format_trace(events))
            click.echo("--- following ---")
            seen = len(events)
            while True:
                time.sleep(1)
                fresh = reader.read(task_id)
                if len(fresh) > seen:
                    click.echo(format_trace(fresh[seen:]))
                    seen = len(fresh)
        except KeyboardInterrupt:
            click.echo("\nStopped following.")
    else:
        click.echo(format_trace(events))


@builder_group.command("resume")
@click.option("--build", is_flag=True, help="Resume stopped build loop")
@click.option("--task", "task_id", default=None, required=False, type=str, help="Resume paused task for execution")
@click.option(
    "--agent",
    type=str,
    help="Agent name (auto-detect from task store if not provided)",
)
@click.option(
    "--detached",
    is_flag=True,
    help="Run in detached mode (no tmux attach)",
)
@click.option(
    "--html",
    is_flag=True,
    help="Output HTML with JSON metadata",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview mode without making changes",
)
@click.option(
    "--select",
    "select_mode",
    is_flag=True,
    help="Select from ready tasks interactively",
)
@click.option("--parallel", "-p", "parallel", default=1, type=int, help="Number of parallel worktrees")
def resume(
    build: bool,
    task_id: str | None,
    agent: str | None,
    detached: bool,
    html: bool,
    dry_run: bool,
    select_mode: bool,
    parallel: int,
) -> None:
    """Resume a build loop or a paused task.

    Use --build to resume the stopped build loop.
    Use --task <id> to resume a paused task for execution.
    """
    if not build and task_id is None and not select_mode:
        raise click.ClickException("specify --build or --task")

    if build:
        _resume_build(parallel=parallel)
    else:
        from village.cli.work import resume as work_resume

        work_resume(
            task_id=task_id,
            agent=agent,
            detached=detached,
            html=html,
            dry_run=dry_run,
            select_mode=select_mode,
        )


def _resume_build(parallel: int = 1) -> None:
    from village.builder_state import BuildRunState, BuildRunStatus
    from village.config import get_config
    from village.loop import find_incomplete_specs
    from village.loop import run_loop as _run_loop

    config = get_config()
    specs_path = config.git_root / "specs"

    if not specs_path.is_dir():
        raise click.ClickException("No specs directory found.")

    build_state = BuildRunState(config.village_dir / "builds")
    prior = build_state.find_latest_run()

    skip_specs: set[str] | None = None
    run_id: str | None = None
    if prior is not None:
        run_id = prior.run_id
        if prior.status == BuildRunStatus.RUNNING:
            skip_specs = set(prior.completed_specs)
            click.echo(f"Resuming run {prior.run_id}")
            click.echo(f"  Prior iterations: {prior.iteration_count}")
            click.echo(f"  Specs completed: {len(prior.completed_specs)}")
        elif prior.status in (BuildRunStatus.COMPLETED,):
            click.echo("Last run completed successfully. Nothing to resume.")
            return
        else:
            click.echo(f"Resuming from stopped run {prior.run_id}")
            skip_specs = set(prior.completed_specs)

    incomplete = find_incomplete_specs(specs_path)
    if skip_specs:
        incomplete = [s for s in incomplete if s.name not in skip_specs]

    if not incomplete:
        click.echo("All specs complete. Nothing to resume.")
        return

    click.echo(f"Incomplete specs: {len(incomplete)}")
    for s in incomplete:
        click.echo(f"  - {s.name}")

    try:
        result = _run_loop(
            specs_dir=specs_path,
            agent="worker",
            model=None,
            max_iterations=None,
            dry_run=False,
            config=config,
            parallel=parallel,
            run_id=run_id,
            skip_specs=skip_specs,
        )

        click.echo(f"\nBuild loop finished ({result.iterations} iterations)")
        click.echo(f"Completed: {result.completed_specs} / {result.total_specs}")
        if result.remaining:
            click.echo(f"Remaining: {', '.join(result.remaining)}")
            click.echo("\nRun 'builder resume --build' to continue.")
        else:
            click.echo("All specs complete!")
    except KeyboardInterrupt:
        click.echo("\nBuild loop stopped by user.")
    except Exception as e:
        raise click.ClickException(str(e))


@builder_group.command("queue")
@click.option("--n", "count", type=int, help="Number of tasks to start")
@click.option("--plan", is_flag=True, help="Generate queue plan")
@click.option("--dry-run", is_flag=True, help="Preview execution")
@click.option("--max-workers", type=int, help="Override concurrency limit")
@click.option("--agent", help="Filter tasks by agent type")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
@click.option("--force", is_flag=True, help="Skip deduplication checks")
@click.option("--approve", "approve_task_id", help="Approve a pending task")
@click.option("--approve-all", is_flag=True, help="Approve all pending tasks")
@click.option("--reject", "reject_task_id", help="Reject a pending task")
def queue(
    count: int | None,
    plan: bool,
    dry_run: bool,
    max_workers: int | None,
    agent: str | None,
    json_output: bool,
    force: bool,
    approve_task_id: str | None,
    approve_all: bool,
    reject_task_id: str | None,
) -> None:
    """
    Queue and execute ready tasks.

    Default: Show queue plan (no execution).
    Use --n N or just N to start N tasks.

    Flags:
      --plan: Show plan only (default behavior)
      --dry-run: Preview what would happen
      --max-workers N: Override concurrency limit
      --agent TYPE: Filter tasks by agent type
      --json: Full JSON output (with --plan)
      --force: Skip deduplication checks

    Examples:
      village builder queue                    # Show plan
      village builder queue --plan --json       # Full JSON plan
      village builder queue 2                 # Start 2 tasks
      village builder queue --n 3             # Start 3 tasks
      village builder queue --agent build        # Start only build tasks
      village builder queue --dry-run 2        # Preview starting 2 tasks
    """
    from village.cli.work import queue as work_queue

    work_queue(
        count=count,
        plan=plan,
        dry_run=dry_run,
        max_workers=max_workers,
        agent=agent,
        json_output=json_output,
        force=force,
        approve_task_id=approve_task_id,
        approve_all=approve_all,
        reject_task_id=reject_task_id,
    )


@builder_group.command("pause")
@click.argument("task_id", default=None, required=False, type=str)
@click.option("--force", is_flag=True, help="Force pause without validation")
@click.option("--select", "select_mode", is_flag=True, help="Select from list interactively")
def pause(task_id: str | None, force: bool, select_mode: bool) -> None:
    """
    Pause an in-progress task.

    Pauses a task that is currently in progress. Only valid from IN_PROGRESS state.

    \b
    Mutating. Updates lock file with PAUSED state.

    Examples:
        village builder pause bd-a3f8
        village builder pause bd-a3f8 --force
        village builder pause --select

    Options:
        --force: Skip state validation (bypass IN_PROGRESS check)
        --select: Select from in-progress tasks interactively

    Exit codes:
        0: Task paused successfully
        4: Task not in IN_PROGRESS state
        5: Task not found
    """
    from village.cli.work import pause as work_pause

    work_pause(task_id=task_id, force=force, select_mode=select_mode)


@builder_group.command("arrange")
@click.option("--plan", default=None, help="Plan slug to arrange")
@click.option("--flat", is_flag=True, help="Force single monolithic PR")
@click.option("--dry-run", is_flag=True, help="Preview without creating PRs")
@click.option("--push/--no-push", default=True, help="Push branches to remote")
@click.option("--project", "project_filter", default=None, help="Filter by project label")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
def arrange(
    plan: str | None,
    flat: bool,
    dry_run: bool,
    push: bool,
    project_filter: str | None,
    json_output: bool,
) -> None:
    """
    Arrange tasks into stacked PRs based on stack labels.

    Reads done tasks from the current plan, groups them by stack:group labels,
    orders by stack:layer, and creates stacked pull requests.

    Examples:
        village builder arrange                # Arrange all done tasks
        village builder arrange --plan auth   # Arrange specific plan
        village builder arrange --flat        # Force single PR
        village builder arrange --dry-run     # Preview only
        village builder arrange --project myapp --dry-run  # Filter by project
    """
    from village.builder.arrange import arrange_landing

    result = arrange_landing(dry_run=dry_run, project_filter=project_filter)

    if json_output:
        click.echo(json.dumps(result, indent=2, sort_keys=True, default=str))
        return

    if dry_run:
        click.echo("Dry run - would create PRs:")
        for spec in result.get("prs", []):
            click.echo(f"  Layer {spec['layer']}: {spec['title']}")
            click.echo(f"    Branch: {spec['head']} -> {spec['base']}")
            click.echo(f"    Tasks: {', '.join(spec['tasks'])}")
    else:
        click.echo("\nArrangement complete!")
        click.echo(f"Created {len(result.get('prs', []))} PRs against {result.get('trunk', 'main')}")


@builder_group.command("rollback")
@click.option("--save", "mode", flag_value="save", default=True, help="Preserve worktree (default)")
@click.option("--purge", "mode", flag_value="purge", help="Delete worktree entirely")
@click.option("--plan", default=None, help="Plan slug to rollback")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def rollback(mode: str, plan: str | None, force: bool) -> None:
    """
    Rollback the current plan (emergency abort).

    Stops all workers, writes abort signal, and either preserves or deletes
    the worktree.

    Examples:
        village builder rollback              # Preserve worktree (default)
        village builder rollback --purge    # Delete worktree
        village builder rollback --force    # Skip confirmation
    """
    import shutil
    import subprocess
    from pathlib import Path

    from village.config import get_config
    from village.plans.models import PlanState
    from village.plans.store import FilePlanStore, PlanNotFoundError

    config = get_config()
    plans_dir = config.git_root / ".village" / "plans"
    store = FilePlanStore(plans_dir)

    slug = plan
    if not slug:
        approved = store.list(PlanState.APPROVED)
        if not approved:
            raise click.ClickException("No active plan to rollback.")
        slug = approved[0].slug

    try:
        plan_obj = store.get(slug)
    except PlanNotFoundError:
        raise click.ClickException(f"Plan '{slug}' not found.")

    if plan_obj.state != PlanState.APPROVED:
        raise click.ClickException(f"Plan '{slug}' is not approved (state: {plan_obj.state.value}).")

    abort_file = plans_dir / plan_obj.slug / "abort"
    abort_file.write_text("aborted", encoding="utf-8")

    click.echo(f"Abort signal written for plan '{slug}'.")

    if not force:
        confirm = sync_confirm("Workers will be signaled to stop. Continue?")
        if not confirm:
            click.echo("Rollback cancelled.")
            return

    if mode == "purge" and plan_obj.worktree_path:
        worktree = Path(plan_obj.worktree_path)
        if worktree.exists():
            shutil.rmtree(worktree)
            click.echo(f"Deleted worktree: {worktree}")

        subprocess.run(["git", "worktree", "prune"], capture_output=True)
        click.echo("Pruned git worktrees.")

    plan_obj.state = PlanState.ABORTED if mode == "save" else PlanState.PURGED
    store.update(plan_obj)

    click.echo(f"Plan '{slug}' marked as {plan_obj.state.value}.")
