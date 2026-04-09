"""Lifecycle commands: new, up, down, onboard."""

from datetime import datetime, timezone
from pathlib import Path

import click

from village.config import get_config
from village.event_log import Event, append_event
from village.logging import get_logger
from village.probes.tmux import session_exists
from village.render.text import render_initialization_plan
from village.runtime import collect_runtime_state, execute_initialization, plan_initialization

logger = get_logger(__name__)


@click.group(name="lifecycle")
def lifecycle_group() -> None:
    """Project lifecycle management."""
    pass


@lifecycle_group.command("new")
@click.argument("name")
@click.option("--path", "path", type=click.Path(), default=".", help="Parent directory (default: current directory)")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--plan", is_flag=True, help="Alias for --dry-run")
@click.option("--dashboard/--no-dashboard", "dashboard", default=True, help="Create dashboard window")
@click.option("--skip-onboard", is_flag=True, help="Skip onboarding interview, write placeholder files")
def new(name: str, path: str, dry_run: bool, plan: bool, dashboard: bool, skip_onboard: bool) -> None:
    """
    Create a new project with village support.

    Creates a new project directory with:
      - git init
      - .gitignore (with .village/, .worktrees/, .beads/ entries)
      - Adaptive onboarding interview (AGENTS.md, README.md, wiki seeds)
      - .village/config with commented defaults
      - bd init (if beads available)
      - tmux session + dashboard window

    Errors if already inside a git repository (use `village up` instead).

    Examples:
      village new myproject
      village new myproject --path ~/projects
      village new myproject --dry-run
      village new myproject --skip-onboard
    """
    from village.scaffold import (
        execute_scaffold,
        is_inside_git_repo,
        plan_scaffold,
    )

    if dry_run or plan:
        parent_dir = Path(path).resolve()
        scaffold_plan = plan_scaffold(name, parent_dir)
        click.echo(f"Would create project: {scaffold_plan.project_dir}")
        click.echo("\nSteps:")
        for step in scaffold_plan.steps:
            click.echo(f"  - {step}")
        return

    if is_inside_git_repo():
        raise click.ClickException("Already inside a git repository. Use `village up` instead.")

    parent_dir = Path(path).resolve()
    result = execute_scaffold(name, parent_dir, dashboard=dashboard, onboard=not skip_onboard)

    if result.success:
        click.echo(f"Created project: {result.project_dir}")
        click.echo("\nCreated:")
        for item in result.created:
            click.echo(f"  - {item}")
        if skip_onboard:
            click.echo(
                "\nOnboarding skipped. AGENTS.md contains placeholder values. Run `village onboard` to complete setup."
            )
        click.echo("\nNext steps:")
        click.echo(f"  cd {name}")
        click.echo("  village chat   # create your first task")
    else:
        click.echo(f"Failed to create project: {result.error}", err=True)
        raise click.ClickException(result.error or "Unknown error")


@lifecycle_group.command("up")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--plan", is_flag=True, help="Alias for --dry-run")
@click.option("--dashboard/--no-dashboard", "dashboard", default=True, help="Create dashboard window")
@click.option("--skip-onboard", is_flag=True, help="Skip onboarding check")
def up(dry_run: bool, plan: bool, dashboard: bool, skip_onboard: bool) -> None:
    """
    Initialize village runtime (idempotent).

    Brings system to desired state:
      - Creates .village/ directories
      - Creates .village/config (with defaults)
      - Initializes Beads (if needed)
      - Creates tmux session (if missing)
      - Creates dashboard window (if enabled)
      - Runs onboarding if project setup is incomplete

    Skips components that already exist.
    Does not start workers.

    Supports: --dry-run, --plan (preview mode)
    """
    config = get_config()

    if dry_run or plan:
        state = collect_runtime_state(config.tmux_session)
        init_plan = plan_initialization(state)
        plan_mode = True
        if not dashboard:
            click.echo("Note: Dashboard creation disabled (--no-dashboard)")
        click.echo(render_initialization_plan(init_plan, config.tmux_session, plan_mode=plan_mode))
        return

    # Execute initialization
    state = collect_runtime_state(config.tmux_session)
    init_plan = plan_initialization(state)
    success = execute_initialization(
        init_plan,
        dry_run=False,
        dashboard=dashboard,
    )

    if not success:
        raise click.ClickException("Failed to initialize runtime")

    event = Event(
        ts=datetime.now(timezone.utc).isoformat(),
        cmd="up",
        task_id=None,
        pane=None,
        result="ok",
    )
    append_event(event, config.village_dir)
    click.echo("Runtime initialized")

    # Check for onboarding after runtime is up
    if not skip_onboard:
        from village.onboard.detector import detect_project

        info = detect_project(config.git_root)
        if info.needs_onboarding:
            click.echo("Detected incomplete project setup. Starting onboarding...")
            _run_onboard(config.git_root, force=False, skip_interview=False)


@lifecycle_group.command("down")
@click.option("--dry-run", is_flag=True, help="Show what would be killed")
@click.option("--plan", is_flag=True, help="Alias for --dry-run")
def down(dry_run: bool, plan: bool) -> None:
    """
    Stop village runtime.

    Kills tmux session only (doesn't delete work data).
    Safe to run while workers are active (they'll be detached).

    Supports: --dry-run, --plan (preview mode)
    """
    from village.runtime import shutdown_runtime

    config = get_config()

    if dry_run or plan:
        if session_exists(config.tmux_session):
            click.echo(f"Would kill session '{config.tmux_session}'")
        else:
            click.echo("No session to stop")
        return

    # Execute shutdown
    success = shutdown_runtime(config.tmux_session)

    if success:
        event = Event(
            ts=datetime.now(timezone.utc).isoformat(),
            cmd="down",
            task_id=None,
            pane=None,
            result="ok",
        )
        append_event(event, config.village_dir)
        click.echo(f"Runtime stopped (session '{config.tmux_session}' terminated)")
    else:
        raise click.ClickException("Failed to stop runtime")


@lifecycle_group.command("onboard")
@click.option("--force", is_flag=True, help="Overwrite existing AGENTS.md/README.md")
@click.option("--skip-interview", is_flag=True, help="Use scaffold defaults without interview")
def onboard(force: bool, skip_interview: bool) -> None:
    """
    Run adaptive onboarding interview for this project.

    Detects the project language, framework, and tooling, then runs
    an interactive interview to generate AGENTS.md, README.md, and
    wiki seed files tailored to the project.

    Use --force to overwrite existing files.
    Use --skip-interview to generate from scaffold defaults without prompts.
    """
    from village.probes.repo import find_git_root

    try:
        git_root = find_git_root()
    except Exception:
        raise click.ClickException("Must be inside a git repository to run onboard.")

    _run_onboard(Path(git_root), force=force, skip_interview=skip_interview)


def _run_onboard(project_root: Path, force: bool, skip_interview: bool) -> None:
    """Execute the onboard pipeline.

    Args:
        project_root: Path to the project root directory.
        force: Whether to overwrite existing files.
        skip_interview: Whether to skip the interactive interview.
    """
    from village.config import OnboardConfig
    from village.onboard.detector import detect_project
    from village.onboard.generator import Generator
    from village.onboard.generator import InterviewResult as GenInterviewResult
    from village.onboard.interview import InterviewEngine
    from village.onboard.scaffolds import get_scaffold

    info = detect_project(project_root)
    scaffold = get_scaffold(info)

    # Check existing files when not forcing
    if not force:
        agents_path = project_root / "AGENTS.md"
        readme_path = project_root / "README.md"
        if agents_path.exists() and readme_path.exists():
            click.echo("AGENTS.md and README.md already exist. Use --force to overwrite.")
            return

    engine = InterviewEngine(
        config=OnboardConfig(),
        project_info=info,
        scaffold=scaffold,
    )

    if skip_interview:
        interview_result = engine.run_default()
    else:
        interview_result = engine.run_interactive()

    # Convert interview module's InterviewResult to generator module's InterviewResult
    gen_interview = GenInterviewResult(
        answers=interview_result.answers,
        project_summary=interview_result.project_summary,
        raw_transcript=interview_result.raw_transcript,
    )

    gen = Generator(info, scaffold, gen_interview, project_root)
    result = gen.generate()
    created = gen.write_files(result)

    click.echo(f"Onboarding complete for {info.project_name}")
    click.echo("\nCreated:")
    for item in created:
        click.echo(f"  - {item}")
