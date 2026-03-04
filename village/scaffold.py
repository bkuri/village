"""Project scaffolding for village new."""

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from village.probes.tools import SubprocessError

logger = logging.getLogger(__name__)

_VILLAGE_CONFIG_TEMPLATE = """\
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
# ppc_mode = explore
# ppc_traits = conservative,terse
# ppc_format = markdown
"""

_AGENTS_MD_TEMPLATE = """\
# {name} - Agent Development Guide

## Overview

Brief description of what this project does and its key goals.

## Build, Lint, and Test Commands

```bash
# Install dependencies
# <fill in>

# Run tests
# <fill in>

# Lint
# <fill in>
```

## Code Style Guidelines

- Describe key conventions here (formatting tools, naming, etc.)

## Project Structure

```
<fill in key directories and their purpose>
```

## Key Integration Points

Describe external services, APIs, or tools this project depends on.

## Constraints

List any important constraints or rules agents must follow.
"""

_GITIGNORE_ENTRIES = """\
# Village orchestration state (local only)
.village/
.worktrees/

# Beads task DAG (local only)
.beads/
"""

_README_TEMPLATE = """\
# {name}

Project description goes here.

## Getting Started

```bash
# Initialize village runtime
village up

# Create a task
village chat

# Queue ready tasks
village queue
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
        "Run: bd init (if available)",
        "Create tmux session + dashboard window",
    ]
    return ScaffoldPlan(project_dir=project_dir, steps=steps)


def execute_scaffold(
    name: str,
    parent_dir: Path,
    *,
    dashboard: bool = True,
) -> ScaffoldResult:
    """
    Execute scaffolding for a new project.

    Creates the project directory, initialises git, writes starter files,
    and brings up the village runtime (directories + tmux session).

    Args:
        name: Project name (used as directory name).
        parent_dir: Parent directory in which to create the project.
        dashboard: Whether to create the tmux dashboard window.

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

    # 4. README.md
    readme_path = project_dir / "README.md"
    readme_path.write_text(_README_TEMPLATE.format(name=name), encoding="utf-8")
    created.append("README.md")
    logger.debug(f"Created {readme_path}")

    # 5. AGENTS.md
    agents_md_path = project_dir / "AGENTS.md"
    agents_md_path.write_text(_AGENTS_MD_TEMPLATE.format(name=name), encoding="utf-8")
    created.append("AGENTS.md")
    logger.debug(f"Created {agents_md_path}")

    # 6. .village/config
    village_dir = project_dir / ".village"
    locks_dir = village_dir / "locks"
    worktrees_dir = project_dir / ".worktrees"

    village_dir.mkdir()
    locks_dir.mkdir()
    worktrees_dir.mkdir()
    created.append(".village/")

    config_path = village_dir / "config"
    config_path.write_text(_VILLAGE_CONFIG_TEMPLATE, encoding="utf-8")
    created.append(".village/config")
    logger.debug(f"Created {config_path}")

    # 7. bd init (optional — skip silently if unavailable)
    try:
        result = subprocess.run(
            ["bd", "init"],
            capture_output=True,
            text=True,
            check=False,
            cwd=project_dir,
        )
        if result.returncode == 0:
            created.append("bd init")
            logger.debug("Beads initialised")
        else:
            logger.debug("bd init failed — skipping Beads init")
    except FileNotFoundError:
        logger.debug("bd not available — skipping Beads init")

    # 8. tmux session + dashboard
    from village.probes.tmux import create_session, create_window, session_exists

    tmux_session = "village"

    if not session_exists(tmux_session):
        if create_session(tmux_session):
            created.append(f"tmux session: {tmux_session}")
            logger.debug(f"Created tmux session: {tmux_session}")
        else:
            logger.warning(f"Failed to create tmux session: {tmux_session}")
    else:
        logger.debug(f"tmux session '{tmux_session}' already exists — skipping")

    if dashboard:
        from village.probes.tmux import list_windows

        dashboard_name = "village:dashboard"
        dashboard_cmd = "watch -n 2 village status --short"
        windows = list_windows(tmux_session)
        if dashboard_name not in windows:
            if create_window(tmux_session, dashboard_name, dashboard_cmd):
                created.append("tmux window: village:dashboard")
                logger.debug("Created dashboard window")
            else:
                logger.warning("Failed to create dashboard window")

    return ScaffoldResult(
        success=True,
        project_dir=project_dir,
        created=created,
    )
