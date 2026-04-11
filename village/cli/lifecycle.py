"""Lifecycle commands: new, up, down."""

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


def _prompt(question: str) -> str:
    """Prompt for a single answer, handling abort gracefully.

    Returns:
        The trimmed answer, or empty string if aborted.
    """
    try:
        return str(click.prompt(f"  {question}")).strip()
    except (click.exceptions.Abort, EOFError, KeyboardInterrupt):
        click.echo("")
        return ""


_STOP_WORDS = frozenset(
    {"a", "an", "the", "and", "or", "but", "with", "for", "in", "on", "of", "to", "is", "it", "that"}
)


def _slugify(description: str) -> str:
    """Derive a working directory name from a description.

    Takes the first few meaningful words and joins them with hyphens.
    Strips common stop words. Falls back to 'new-project' if nothing
    useful can be derived.

    Args:
        description: A short project description or desired name.

    Returns:
        A slug-style directory name.
    """
    import re

    normalized = description.strip().lower()
    segments = re.split(r"[\s_]+", normalized)
    keep: list[str] = []
    for segment in segments:
        cleaned = re.sub(r"[^a-z0-9]+", "-", segment).strip("-")
        if not cleaned:
            continue
        word = cleaned.split("-")[0]
        if word not in _STOP_WORDS and re.match(r"^[a-z]", word):
            keep.append(cleaned)
    keep = keep[:3]
    return "-".join(keep) or "new-project"


def _run_create_project_workflow() -> tuple[str, str]:
    """Interactive reverse-prompt workflow for creating a new project.

    Asks what the user is building, then derives a working directory name
    from the description. Naming is deferred to the ``name-design``
    workflow or ``village onboard``.

    Returns:
        A (working directory name, description) tuple, or ("", "") if aborted.
    """
    click.echo("Let's set up a new project.\n")

    description = _prompt("What are you building?")
    if not description:
        click.echo("Aborted.")
        return "", ""

    slug = _slugify(description)
    click.echo(f"  Working directory: {slug}")
    click.echo("")
    return slug, description


@lifecycle_group.command("new")
@click.argument("name", required=False)
@click.option("--path", "path", type=click.Path(), default=".", help="Parent directory (default: current directory)")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--plan", is_flag=True, help="Alias for --dry-run")
@click.option("--dashboard/--no-dashboard", "dashboard", default=True, help="Create dashboard window")
def new(name: str | None, path: str, dry_run: bool, plan: bool, dashboard: bool) -> None:
    """
    Create a new project with village support.

    Creates a new project directory with:
      - git init
      - .gitignore (with .village/, .worktrees/ entries)
      - Adaptive onboarding interview (AGENTS.md, README.md, wiki seeds)
      - .village/config with commented defaults
      - bd init (if available)
      - tmux session + dashboard window

    When called without a name, starts an interactive create-project workflow
    that prompts for the project name and other details before scaffolding.

    Errors if already inside a git repository (use `village up` instead).

    Examples:
      village new
      village new myproject
      village new myproject --path ~/projects
      village new myproject --dry-run
    """
    from village.scaffold import (
        execute_scaffold,
        is_inside_git_repo,
        plan_scaffold,
    )

    if is_inside_git_repo():
        raise click.ClickException("Already inside a git repository. Use `village up` instead.")

    description = ""
    project_name = name
    if project_name is None:
        project_name, description = _run_create_project_workflow()
        if not project_name:
            raise click.ClickException("Project name is required.")
    else:
        project_name = _slugify(project_name)

    if dry_run or plan:
        parent_dir = Path(path).resolve()
        scaffold_plan = plan_scaffold(project_name, parent_dir)
        click.echo(f"Would create project: {scaffold_plan.project_dir}")
        click.echo("\nSteps:")
        for step in scaffold_plan.steps:
            click.echo(f"  - {step}")
        return

    parent_dir = Path(path).resolve()
    result = execute_scaffold(
        project_name,
        parent_dir,
        dashboard=dashboard,
        onboard=True,
        description=description,
    )

    if result.success:
        click.echo(f"Created project: {result.project_dir}")
        click.echo("\nCreated:")
        for item in result.created:
            click.echo(f"  - {item}")
        click.echo("\nNext steps:")
        click.echo(f"  cd {project_name}")
        click.echo("  village chat   # create your first task")
    else:
        click.echo(f"Failed to create project: {result.error}", err=True)
        raise click.ClickException(result.error or "Unknown error")


@lifecycle_group.command("up")
@click.option("--path", "path_opt", type=click.Path(), default=None, help="Project path (default: current directory)")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--plan", is_flag=True, help="Alias for --dry-run")
@click.option("--dashboard/--no-dashboard", "dashboard", default=True, help="Create dashboard window")
@click.option("--force", is_flag=True, help="Overwrite existing AGENTS.md/README.md during onboarding")
@click.option("--skip-interview", is_flag=True, help="Use scaffold defaults without interview")
def up(path_opt: str | None, dry_run: bool, plan: bool, dashboard: bool, force: bool, skip_interview: bool) -> None:
    """
    Initialize village runtime (idempotent).

    Brings system to desired state:
      - Creates .village/ directories
      - Creates .village/config (with defaults)
      - Initializes task store (if needed)
      - Creates tmux session (if missing)
      - Creates dashboard window (if enabled)
      - Runs onboarding if project setup is incomplete

    Skips components that already exist.
    Does not start workers.

    Supports: --dry-run, --plan (preview mode),
    --force (overwrite existing files during onboarding),
    --skip-interview (use scaffold defaults without prompts)
    """
    if path_opt is None:
        click.echo("No --path specified, using current directory.", err=True)

    config = get_config()

    if dry_run or plan:
        state = collect_runtime_state(config.tmux_session)
        init_plan = plan_initialization(state)
        plan_mode = True
        if not dashboard:
            click.echo("Note: Dashboard creation disabled (--no-dashboard)")
        click.echo(render_initialization_plan(init_plan, config.tmux_session, plan_mode=plan_mode))
        return

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

    from village.onboard.detector import detect_project

    info = detect_project(config.git_root)
    if info.needs_onboarding or force:
        if not force:
            click.echo("Detected incomplete project setup. Starting onboarding...")
        _run_onboard(config.git_root, force=force, skip_interview=skip_interview)


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
