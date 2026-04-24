"""Project scaffolding for village new."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import anthropic
import httpx

from village.probes.tools import SubprocessError

if TYPE_CHECKING:
    from village.config import OnboardConfig

logger = logging.getLogger(__name__)

_GITIGNORE_ENTRIES = """\
# Village orchestration state (local only)
.village/
.worktrees/
"""

_MINIMAL_CONFIG = """\
# Village configuration
# See: https://opencode.ai/docs for full reference
#
# Priority: environment variables > this file > built-in defaults

[DEFAULT]
# Maximum number of concurrent workers
# MAX_WORKERS = 2

# Default agent type for tasks
# DEFAULT_AGENT = worker

# SCM backend: git or jj
# SCM_KIND = git

# Task deduplication TTL in minutes
# QUEUE_TTL_MINUTES = 5

# [agent.worker]
# opencode_args = --verbose
# contract = path/to/contract.md
#
# For pi agent backend:
# type = pi
# pi_args = --thinking high
"""

_MINIMAL_AGENTS_MD = """\
# {name} - Agent Development Guide

## Overview

Project description pending. Run `village onboard` to complete setup.

## Build, Lint, and Test Commands

```bash
# <fill in - run village onboard to auto-detect>
```

## Code Style Guidelines

- <fill in - run village onboard to auto-detect>

## Project Structure

```
<fill in - run village onboard to auto-detect>
```
"""

_MINIMAL_README = """\
# {name}

Project description goes here.

## Getting Started

```bash
# Initialize village runtime
village up

# Complete project setup
village onboard
```
"""


@dataclass
class ScaffoldPlan:
    """Plan for village new operation."""

    project_dir: Path
    steps: list[str] = field(default_factory=list)


@dataclass
class ScaffoldResult:
    """Result of village new operation."""

    success: bool
    project_dir: Path
    created: list[str] = field(default_factory=list)
    error: str | None = None


def is_inside_git_repo() -> bool:
    """
    Check whether the current working directory is inside a git repository.

    Returns:
        True if inside a git repo, False otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def plan_scaffold(name: str, parent_dir: Path) -> ScaffoldPlan:
    """
    Build a plan for scaffolding a new project.

    Args:
        name: Project name (used as directory name).
        parent_dir: Parent directory in which to create the project.

    Returns:
        ScaffoldPlan describing the steps to be taken.
    """
    project_dir = parent_dir / name
    steps = [
        f"Create directory: {project_dir}",
        "Run: git init",
        "Create: .gitignore",
        "Create: README.md",
        "Create: AGENTS.md",
        "Create: .village/config (with defaults)",
        "Initialize: tasks.jsonl",
        "Create tmux session + dashboard window",
    ]
    return ScaffoldPlan(project_dir=project_dir, steps=steps)


def _run_onboard_pipeline(
    project_dir: Path,
    name: str,
    description: str = "",
    onboard_config: OnboardConfig | None = None,
) -> list[str]:
    """Run the adaptive onboard pipeline for a new project.

    Args:
        project_dir: Root directory of the new project.
        name: Project name.
        description: Initial project description from the create workflow.
        onboard_config: Onboard config override (uses global config if not provided).

    Returns:
        List of created file descriptions.
    """
    from village.config import OnboardConfig
    from village.config import get_global_config as _get_global_config
    from village.onboard.detector import detect_project
    from village.onboard.generator import Generator
    from village.onboard.interview import InterviewEngine
    from village.onboard.scaffolds import get_scaffold

    created: list[str] = []

    info = detect_project(project_dir)
    info.project_name = name
    scaffold = get_scaffold(info)

    if onboard_config is None:
        onboard_config = _get_global_config().onboard

    if not isinstance(onboard_config, OnboardConfig):
        raise TypeError(f"Expected OnboardConfig, got {type(onboard_config).__name__}")

    preseeded: dict[str, str] = {}
    if description:
        preseeded["What does this project do?"] = description

    engine = InterviewEngine(
        config=onboard_config,
        project_info=info,
        scaffold=scaffold,
        preseeded_answers=preseeded,
    )
    interview_result = engine.run_interactive()

    if description:
        interview_result.preamble.append(("User", description))

    gen = Generator(info, scaffold, interview_result, project_dir)
    result = gen.generate()
    created.extend(gen.write_files(result))

    return created


def _write_minimal_files(project_dir: Path, name: str) -> list[str]:
    """Write minimal placeholder files when onboarding is skipped.

    Args:
        project_dir: Root directory of the new project.
        name: Project name.

    Returns:
        List of created file descriptions.
    """
    created: list[str] = []

    readme_path = project_dir / "README.md"
    readme_path.write_text(_MINIMAL_README.format(name=name), encoding="utf-8")
    created.append("README.md")
    logger.debug(f"Created {readme_path}")

    agents_md_path = project_dir / "AGENTS.md"
    agents_md_path.write_text(_MINIMAL_AGENTS_MD.format(name=name), encoding="utf-8")
    created.append("AGENTS.md")
    logger.debug(f"Created {agents_md_path}")

    return created


def _get_config_content(scaffold_config: str) -> str:
    """Return config content, using scaffold template or minimal default.

    Args:
        scaffold_config: Config template from the scaffold (may be empty).

    Returns:
        Config file content string.
    """
    if scaffold_config:
        return scaffold_config
    return _MINIMAL_CONFIG


def execute_scaffold(
    name: str,
    parent_dir: Path,
    *,
    dashboard: bool = True,
    onboard: bool = True,
    description: str = "",
) -> ScaffoldResult:
    """
    Execute scaffolding for a new project.

    Creates the project directory, initialises git, writes starter files,
    and brings up the village runtime (directories + tmux session).

    Args:
        name: Project name (used as directory name).
        parent_dir: Parent directory in which to create the project.
        dashboard: Whether to create the tmux dashboard window.
        onboard: Whether to run the adaptive onboard pipeline.
        description: Initial project description (pre-seeds interview).

    Returns:
        ScaffoldResult with success flag and list of created items.
    """
    project_dir = parent_dir / name
    created: list[str] = []

    # 1. Create project directory
    try:
        project_dir.mkdir(parents=True, exist_ok=False)
        created.append(str(project_dir))
        logger.debug(f"Created project directory: {project_dir}")
    except FileExistsError:
        return ScaffoldResult(
            success=False,
            project_dir=project_dir,
            error=f"Directory already exists: {project_dir}",
        )

    # 2. git init
    try:
        result = subprocess.run(
            ["git", "init"],
            capture_output=True,
            text=True,
            check=False,
            cwd=project_dir,
        )
        if result.returncode != 0:
            raise SubprocessError(result.stderr.strip() or "git init failed")
        created.append("git init")
        logger.debug(f"Initialised git repo in {project_dir}")
    except (SubprocessError, FileNotFoundError) as e:
        return ScaffoldResult(
            success=False,
            project_dir=project_dir,
            created=created,
            error=f"git init failed: {e}",
        )

    # 3. .gitignore
    gitignore_path = project_dir / ".gitignore"
    gitignore_path.write_text(_GITIGNORE_ENTRIES, encoding="utf-8")
    created.append(".gitignore")
    logger.debug(f"Created {gitignore_path}")

    # 4. Generate project files (onboard pipeline or minimal placeholders)
    if onboard:
        try:
            onboard_created = _run_onboard_pipeline(project_dir, name, description)
            created.extend(onboard_created)
        except (httpx.HTTPError, anthropic.AnthropicError, ValueError) as e:
            logger.warning(f"Onboard pipeline failed, falling back to minimal files: {e}")
            created.extend(_write_minimal_files(project_dir, name))
    else:
        created.extend(_write_minimal_files(project_dir, name))

    # 5. .village/ directories and config
    village_dir = project_dir / ".village"
    locks_dir = village_dir / "locks"
    worktrees_dir = project_dir / ".worktrees"

    village_dir.mkdir()
    locks_dir.mkdir()
    worktrees_dir.mkdir()
    created.append(".village/")

    config_path = village_dir / "config"
    config_content = _get_config_content("")
    config_path.write_text(config_content, encoding="utf-8")
    created.append(".village/config")
    logger.debug(f"Created {config_path}")

    # 6. task store init
    try:
        from village.config import Config as _Config
        from village.tasks import get_task_store

        _cfg = _Config(git_root=Path(project_dir), village_dir=village_dir, worktrees_dir=worktrees_dir)
        store = get_task_store(tasks_file=village_dir / "tasks.jsonl", config=_cfg)
        store.initialize()
        created.append("tasks init")
        logger.debug("Task store initialized")
    except (OSError, ImportError) as e:
        logger.debug(f"Task store init skipped: {e}")

    # 7. git hooks
    try:
        from village.hooks import install_hooks

        install_hooks(project_dir, dry_run=False)
        created.append("git hooks")
    except (OSError, ImportError) as e:
        logger.debug(f"Git hook install skipped: {e}")

    # 8. tmux session + dashboard
    from village.probes.tmux import create_session, create_window, session_exists

    tmux_session = name

    if not session_exists(tmux_session):
        if create_session(tmux_session):
            created.append(f"tmux session: {tmux_session}")
            logger.debug(f"Created tmux session: {tmux_session}")
        else:
            logger.warning(f"Failed to create tmux session: {tmux_session}")
    else:
        logger.debug(f"tmux session '{tmux_session}' already exists -- skipping")

    if dashboard and session_exists(tmux_session):
        from village.probes.tmux import list_windows

        dashboard_name = f"{tmux_session}:dashboard"
        dashboard_cmd = "watch -n 2 village watcher status --short"
        windows = list_windows(tmux_session)
        if dashboard_name not in windows:
            if create_window(tmux_session, dashboard_name, dashboard_cmd, cwd=str(project_dir)):
                created.append(f"tmux window: {dashboard_name}")
                logger.debug("Created dashboard window")
            else:
                logger.warning("Failed to create dashboard window")

    return ScaffoldResult(
        success=True,
        project_dir=project_dir,
        created=created,
    )
