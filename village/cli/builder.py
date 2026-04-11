import os
import sys

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
            parallel=parallel,
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


@builder_group.command("cancel", hidden=True)
@click.argument("run_id", required=False)
def cancel_run(run_id: str | None) -> None:
    """Cancel a running build loop."""
    click.echo("Stop not yet implemented. Use Ctrl+C in the running terminal.")


@builder_group.command("logs", hidden=True)
@click.argument("run_id", required=False)
@click.option("--follow", is_flag=True, help="Follow log output")
def show_logs(run_id: str | None, follow: bool) -> None:
    """Show build loop logs."""
    click.echo("Log viewing not yet implemented.")


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
def resume(
    build: bool,
    task_id: str | None,
    agent: str | None,
    detached: bool,
    html: bool,
    dry_run: bool,
    select_mode: bool,
) -> None:
    """Resume a build loop or a paused task.

    Use --build to resume the stopped build loop.
    Use --task <id> to resume a paused task for execution.
    """
    if not build and task_id is None and not select_mode:
        raise click.ClickException("specify --build or --task")

    if build:
        _resume_build()
    else:
        _resume_task(task_id, agent, detached, html, dry_run, select_mode)


def _resume_build() -> None:
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


def _resume_task(
    task_id: str | None,
    agent: str | None,
    detached: bool,
    html: bool,
    dry_run: bool,
    select_mode: bool,
) -> None:
    from village.config import get_config
    from village.interactive import select_from_list
    from village.queue import generate_queue_plan
    from village.resume import execute_resume, plan_resume
    from village.status import collect_workers

    config = get_config()

    if select_mode and task_id is None:
        from village.state_machine import TaskState, TaskStateMachine

        workers = collect_workers(config.tmux_session)
        state_machine = TaskStateMachine(config)

        in_progress = [w for w in workers if state_machine.get_state(w.task_id) == TaskState.IN_PROGRESS]

        queue_plan = generate_queue_plan(config.tmux_session, config.max_workers, config)

        ready_tasks = queue_plan.ready_tasks

        if not in_progress and not ready_tasks:
            click.echo("No tasks to resume")
            sys.exit(0)

        choices = []
        for w in in_progress:
            choices.append((w.task_id, w.status, "in_progress"))
        for t in ready_tasks:
            choices.append((t.task_id, "READY", t.agent))

        if not choices:
            click.echo("No tasks to resume")
            sys.exit(0)

        selected = select_from_list(
            choices,
            "Select task to resume:",
            formatter=lambda c: f"{c[0]} ({c[1]})",
        )
        if selected is None:
            click.echo("Canceled")
            sys.exit(0)
        task_id = selected[0]

    if task_id is None:
        action = plan_resume(config=config)

        if action.action == "resume":
            click.echo(f"Ready to resume task: {action.meta.get('task_id')}")
        elif action.action == "up":
            click.echo(f"Action: village {action.action}")
            click.echo(f"Reason: {action.reason}")
            click.echo(f"Run: {action.meta.get('command', 'village up')}")
        elif action.action == "status":
            click.echo(f"Action: village {action.action}")
            click.echo(f"Reason: {action.reason}")
            click.echo(f"Run: {action.meta.get('command', 'village status --workers')}")
        elif action.action == "cleanup":
            click.echo(f"Action: village {action.action}")
            click.echo(f"Reason: {action.reason}")
            click.echo(f"Run: {action.meta.get('command', 'village cleanup')}")
        elif action.action == "queue":
            click.echo(f"Action: village {action.action}")
            click.echo(f"Reason: {action.reason}")
            click.echo(f"Run: {action.meta.get('command', 'village queue')}")
        elif action.action == "ready":
            click.echo(f"Action: village {action.action}")
            click.echo(f"Reason: {action.reason}")
            click.echo(f"Run: {action.meta.get('command', 'village ready')}")
        else:
            click.echo(f"Action: {action.action}")
            click.echo(f"Reason: {action.reason}")

        return

    if agent is None:
        agent = config.default_agent

    result = execute_resume(
        task_id=task_id,
        agent=agent,
        detached=detached,
        dry_run=dry_run,
        config=config,
    )

    if result.success:
        click.echo(f"✓ Resume successful: {result.task_id}")
        click.echo(f"  Window: {result.window_name}")
        click.echo(f"  Pane: {result.pane_id}")
        click.echo(f"  Worktree: {result.worktree_path}")
    else:
        click.echo(f"✗ Resume failed: {result.task_id}")
        if result.error:
            click.echo(f"  Error: {result.error}")

    if html and result.success:
        from village.contracts import generate_contract
        from village.render.html import render_resume_html

        contract = generate_contract(result.task_id, result.agent, result.worktree_path, result.window_name, config)

        click.echo(render_resume_html(contract))


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
    count: int,
    plan: bool,
    dry_run: bool,
    max_workers: int,
    agent: str,
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
    import json as _json

    from village.config import get_config
    from village.errors import EXIT_BLOCKED, EXIT_ERROR, EXIT_PARTIAL, EXIT_SUCCESS
    from village.queue import (
        execute_queue_plan,
        generate_queue_plan,
        render_queue_plan,
        render_queue_plan_json,
    )
    from village.state_machine import TaskState, TaskStateMachine

    config = get_config()

    if approve_task_id:
        state_machine = TaskStateMachine(config)
        current = state_machine.get_state(approve_task_id)
        if current == TaskState.PENDING_APPROVAL:
            transition_result = state_machine.transition(
                task_id=approve_task_id,
                new_state=TaskState.QUEUED,
                context={"reason": "user_approved"},
            )
            if transition_result.success:
                click.echo(f"Approved task {approve_task_id}")
            else:
                click.echo(f"Failed to approve: {transition_result.message}", err=True)
                sys.exit(EXIT_ERROR)
        else:
            click.echo(
                f"Task {approve_task_id} is not pending approval (state: {current.value if current else 'none'})",
                err=True,
            )
            sys.exit(EXIT_BLOCKED)
        return

    if approve_all:
        state_machine = TaskStateMachine(config)
        approved_count = 0
        for lock_file in config.locks_dir.glob("*.lock"):
            task_id = lock_file.stem
            current = state_machine.get_state(task_id)
            if current == TaskState.PENDING_APPROVAL:
                transition_result = state_machine.transition(
                    task_id=task_id,
                    new_state=TaskState.QUEUED,
                    context={"reason": "bulk_approved"},
                )
                if transition_result.success:
                    approved_count += 1
        click.echo(f"Approved {approved_count} task(s)")
        return

    if reject_task_id:
        state_machine = TaskStateMachine(config)
        current = state_machine.get_state(reject_task_id)
        if current == TaskState.PENDING_APPROVAL:
            transition_result = state_machine.transition(
                task_id=reject_task_id,
                new_state=TaskState.FAILED,
                context={"reason": "user_rejected"},
            )
            if transition_result.success:
                click.echo(f"Rejected task {reject_task_id}")
            else:
                click.echo(f"Failed to reject: {transition_result.message}", err=True)
                sys.exit(EXIT_ERROR)
        else:
            click.echo(
                f"Task {reject_task_id} is not pending approval (state: {current.value if current else 'none'})",
                err=True,
            )
            sys.exit(EXIT_BLOCKED)
        return

    concurrency_limit = max_workers if max_workers else config.max_workers

    queue_plan = generate_queue_plan(config.tmux_session, concurrency_limit, config, force)

    if agent:
        queue_plan.ready_tasks = [t for t in queue_plan.ready_tasks if t.agent == agent]
        queue_plan.available_tasks = [t for t in queue_plan.available_tasks if t.agent == agent]
        queue_plan.blocked_tasks = [t for t in queue_plan.blocked_tasks if t.agent == agent]

    if plan or count is None:
        pending_approval = [t for t in queue_plan.blocked_tasks if t.skip_reason == "pending_approval"]
        ci_mode = os.environ.get("VILLAGE_CI_MODE", "").lower() in ("1", "true", "yes")
        if ci_mode and pending_approval:
            click.echo(f"Error: {len(pending_approval)} task(s) pending approval in CI mode", err=True)
            sys.exit(EXIT_ERROR)

        if json_output:
            click.echo(render_queue_plan_json(queue_plan))
        else:
            click.echo(render_queue_plan(queue_plan))
        return

    if dry_run:
        click.echo("(dry-run: previewing execution)")
        click.echo(render_queue_plan(queue_plan))
        return

    if count is not None:
        queue_plan.available_tasks = queue_plan.available_tasks[:count]

    if not queue_plan.available_tasks:
        if json_output:
            click.echo(
                _json.dumps(
                    {
                        "tasks_started": 0,
                        "tasks_failed": 0,
                        "results": [],
                        "message": "No tasks available to start",
                    },
                    indent=2,
                )
            )
        else:
            click.echo("No tasks available to start")
        sys.exit(EXIT_BLOCKED)

    if not json_output:
        click.echo(f"Starting {len(queue_plan.available_tasks)} task(s)...")
    results = execute_queue_plan(queue_plan, config.tmux_session, config, force)

    tasks_started = sum(1 for r in results if r.success)
    tasks_failed = sum(1 for r in results if not r.success)

    if not json_output:
        click.echo(f"\nTasks started: {tasks_started}")
        click.echo(f"Tasks failed: {tasks_failed}")

        if tasks_failed > 0:
            click.echo("\nFailed tasks:")
            for result in results:
                if not result.success:
                    click.echo(f"  - {result.task_id}: {result.error or 'Unknown error'}")
    else:
        output = {
            "tasks_started": tasks_started,
            "tasks_failed": tasks_failed,
            "results": [
                {
                    "task_id": r.task_id,
                    "agent": r.agent,
                    "success": r.success,
                    "worktree_path": str(r.worktree_path),
                    "window_name": r.window_name,
                    "pane_id": r.pane_id,
                    "error": r.error,
                }
                for r in results
            ],
        }
        click.echo(_json.dumps(output, indent=2, sort_keys=True))

    if tasks_started > 0 and tasks_failed == 0:
        sys.exit(EXIT_SUCCESS)
    elif tasks_started > 0:
        sys.exit(EXIT_PARTIAL)
    else:
        sys.exit(EXIT_ERROR)


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
    from village.config import get_config
    from village.errors import EXIT_BLOCKED, EXIT_ERROR
    from village.interactive import select_from_list
    from village.state_machine import TaskState, TaskStateMachine
    from village.status import collect_workers

    config = get_config()

    if task_id is None or select_mode:
        workers = collect_workers(config.tmux_session)
        state_machine = TaskStateMachine(config)

        in_progress = [w for w in workers if state_machine.get_state(w.task_id) == TaskState.IN_PROGRESS]
        if not in_progress:
            click.echo("No in-progress tasks found")
            if task_id is None:
                sys.exit(0)
            return

        selected = select_from_list(
            in_progress,
            "Select task to pause:",
            formatter=lambda w: f"{w.task_id} ({w.status})",
        )
        if selected is None:
            click.echo("Canceled")
            sys.exit(0)
        task_id = selected.task_id

    state_machine = TaskStateMachine(config)

    current_state = state_machine.get_state(task_id)

    if current_state is None:
        click.echo(f"Task {task_id} not found (no lock file)", err=True)
        sys.exit(EXIT_BLOCKED)

    if not force and current_state != TaskState.IN_PROGRESS:
        click.echo(f"Task {task_id} is not IN_PROGRESS (current: {current_state.value})", err=True)
        sys.exit(EXIT_BLOCKED)

    result = state_machine.transition(
        task_id,
        TaskState.PAUSED,
        context={"reason": "user_paused"},
    )

    if result.success:
        click.echo(f"Paused task {task_id}")
    else:
        click.echo(f"Failed to pause: {result.message}", err=True)
        sys.exit(EXIT_ERROR)


@builder_group.command("release")
@click.option("--dry-run", is_flag=True, help="Preview without applying")
@click.option("--changelog/--no-changelog", default=True, help="Update CHANGELOG.md")
@click.option("--tag/--no-tag", default=True, help="Create git tag")
@click.option("--force", is_flag=True, help="Skip unlabeled-task check")
def release(dry_run: bool, changelog: bool, tag: bool, force: bool) -> None:
    """
    Apply pending version bumps.

    Aggregates pending bump types (highest wins) and applies version bump.
    Updates CHANGELOG.md and creates git tag by default.

    \b
    Examples:
        village builder release                # Apply pending bumps
        village builder release --dry-run      # Preview what would happen
        village builder release --no-changelog # Skip CHANGELOG update
        village builder release --no-tag       # Skip git tag
        village builder release --force        # Skip unlabeled-task check

    Exit codes:
        0: Release applied successfully
        1: Unlabeled closed tasks found, no pending bumps, or error
    """
    import subprocess as _subprocess
    from datetime import datetime, timezone

    from village.errors import EXIT_ERROR, EXIT_SUCCESS
    from village.release import (
        aggregate_bumps,
        clear_pending_bumps,
        compute_next_version,
        get_pending_bumps,
        get_unlabeled_closed_tasks,
        is_no_op_release,
        record_release,
        update_changelog,
    )

    if not force:
        unlabeled = get_unlabeled_closed_tasks()
        if unlabeled:
            click.echo(f"Error: {len(unlabeled)} closed task(s) have no bump label:", err=True)
            for task in unlabeled:
                click.echo(f"  {task['id']}  {task['title']}", err=True)
            click.echo("Label them with: bd label add <id> bump:<major|minor|patch|none>", err=True)
            click.echo("Or use --force to skip this check.", err=True)
            sys.exit(EXIT_ERROR)

    pending = get_pending_bumps()

    if not pending:
        click.echo("No pending version bumps")
        sys.exit(EXIT_SUCCESS)

    aggregate = aggregate_bumps([b.bump for b in pending])

    if is_no_op_release([b.bump for b in pending]):
        click.echo("All pending tasks are bump:none — no version change required.")
        click.echo("Clearing queue without creating a release.")
        if dry_run:
            click.echo("(dry-run: would clear queue, no version bump)")
            return
        clear_pending_bumps()
        sys.exit(EXIT_SUCCESS)

    try:
        version = compute_next_version(aggregate)
    except ValueError as exc:
        click.echo(f"Error computing version: {exc}", err=True)
        sys.exit(EXIT_ERROR)

    click.echo(f"New version: {version} (bump: {aggregate})")

    if dry_run:
        task_ids_preview = [b.task_id for b in pending]
        click.echo(f"Pending tasks ({len(pending)}): {', '.join(task_ids_preview)}")
        click.echo("(dry-run: no changes applied)")
        return

    if changelog:
        try:
            update_changelog(version, pending)
            click.echo(f"Updated CHANGELOG.md with version {version}")
        except Exception as exc:  # noqa: BLE001
            click.echo(f"Warning: CHANGELOG update failed: {exc}", err=True)

    if tag:
        tag_result = _subprocess.run(
            ["git", "tag", "-a", f"v{version}", "-m", f"Release v{version}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if tag_result.returncode == 0:
            click.echo(f"Created git tag v{version}")
        else:
            click.echo(f"Warning: git tag failed: {tag_result.stderr.strip()}", err=True)

    from village.release import ReleaseRecord

    task_ids = [b.task_id for b in pending]
    clear_pending_bumps()

    record = ReleaseRecord(
        version=version,
        released_at=datetime.now(timezone.utc),
        aggregate_bump=aggregate,
        tasks=task_ids,
        changelog_entry="",
    )
    record_release(record)

    click.echo(f"Release v{version} applied: {aggregate} bump from {len(pending)} task(s)")
    click.echo("Run: git push --tags")
