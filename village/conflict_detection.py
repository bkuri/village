"""Conflict detection for file overlap between workers."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from village.config import Config, get_config
from village.probes.tools import SubprocessError, run_command_output_cwd

logger = logging.getLogger(__name__)


@dataclass
class WorkerInfo:
    """Worker information with worktree path."""

    task_id: str
    worktree_path: Path
    pane_id: str
    window_id: str


@dataclass
class Conflict:
    """File conflict between workers."""

    file: Path
    workers: list[str]
    worktrees: list[Path]


@dataclass
class ConflictReport:
    """Conflict detection report."""

    has_conflicts: bool
    conflicts: list[Conflict]
    blocked: bool


def _detect_vcs(worktree_path: Path) -> Optional[str]:
    """
    Detect which VCS is in use for a worktree.

    Args:
        worktree_path: Path to worktree directory

    Returns:
        "git" or "jj" or None if not detected
    """
    try:
        git_dir = worktree_path / ".git"
        if git_dir.exists():
            return "git"

        jj_dir = worktree_path / ".jj"
        if jj_dir.exists():
            return "jj"

        return None
    except Exception:
        logger.debug(f"Failed to detect VCS for {worktree_path}")
        return None


def get_modified_files(worktree_path: Path) -> list[Path]:
    """
    Get modified files in a worktree.

    Args:
        worktree_path: Path to worktree directory

    Returns:
        List of modified file paths (relative to worktree)

    Raises:
        RuntimeError: If worktree doesn't exist or VCS detection fails
    """
    if not worktree_path.exists():
        raise RuntimeError(f"Worktree does not exist: {worktree_path}")

    vcs = _detect_vcs(worktree_path)
    if not vcs:
        return []

    try:
        if vcs == "git":
            return _get_git_modified_files(worktree_path)
        elif vcs == "jj":
            return _get_jj_modified_files(worktree_path)
        else:
            return []
    except SubprocessError as e:
        logger.warning(f"Failed to get modified files from {worktree_path}: {e}")
        return []


def _get_git_modified_files(worktree_path: Path) -> list[Path]:
    """
    Get modified files from git status.

    Args:
        worktree_path: Path to git worktree

    Returns:
        List of modified file paths

    Raises:
        SubprocessError: If git status command fails
    """
    cmd = ["git", "status", "--porcelain"]
    output = run_command_output_cwd(cmd, cwd=worktree_path)

    files: list[Path] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            continue

        file_path = Path(parts[1])

        if file_path.is_absolute():
            files.append(file_path)
        else:
            files.append(worktree_path / file_path)

    logger.debug(f"Found {len(files)} modified files in git worktree {worktree_path}")
    return files


def _get_jj_modified_files(worktree_path: Path) -> list[Path]:
    """
    Get modified files from jj status.

    Args:
        worktree_path: Path to jj workspace

    Returns:
        List of modified file paths

    Raises:
        SubprocessError: If jj status command fails
    """
    cmd = ["jj", "diff", "--files"]
    output = run_command_output_cwd(cmd, cwd=worktree_path)

    files: list[Path] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        file_path = Path(line)

        if file_path.is_absolute():
            files.append(file_path)
        else:
            files.append(worktree_path / file_path)

    logger.debug(f"Found {len(files)} modified files in jj workspace {worktree_path}")
    return files


def find_overlaps(all_files: dict[str, list[Path]]) -> list[Conflict]:
    """
    Find file overlaps between workers.

    Args:
        all_files: Dict mapping task_id to list of modified files

    Returns:
        List of Conflict objects
    """
    conflicts: list[Conflict] = []

    file_to_workers: dict[str, dict[str, list[Path]]] = {}

    for task_id, files in all_files.items():
        for file in files:
            file_key = str(file.absolute().resolve())

            if file_key not in file_to_workers:
                file_to_workers[file_key] = {}

            if task_id not in file_to_workers[file_key]:
                file_to_workers[file_key][task_id] = []

            file_to_workers[file_key][task_id].append(file)

    for file_key, workers_map in file_to_workers.items():
        worker_ids = list(workers_map.keys())

        if len(worker_ids) > 1:
            conflict = Conflict(
                file=Path(file_key),
                workers=worker_ids,
                worktrees=list({list(files)[0].parent for files in workers_map.values()}),
            )
            conflicts.append(conflict)

    logger.debug(f"Found {len(conflicts)} file conflicts")
    return conflicts


def detect_file_conflicts(
    active_workers: list[WorkerInfo],
    config: Optional[Config] = None,
) -> ConflictReport:
    """
    Detect file conflicts between active workers.

    Args:
        active_workers: List of active worker information
        config: Optional config (uses default if not provided)

    Returns:
        ConflictReport with conflicts and blocking status
    """
    if config is None:
        config = get_config()

    all_files: dict[str, list[Path]] = {}

    for worker in active_workers:
        try:
            modified = get_modified_files(worker.worktree_path)
            all_files[worker.task_id] = modified
        except Exception as e:
            logger.warning(f"Failed to get modified files for worker {worker.task_id}: {e}")
            all_files[worker.task_id] = []

    conflicts = find_overlaps(all_files)

    block_on_conflict = config.conflict.block_on_conflict

    has_conflicts = len(conflicts) > 0
    blocked = has_conflicts and block_on_conflict

    if has_conflicts:
        logger.warning(f"Detected {len(conflicts)} file conflict(s)")
        for conflict in conflicts:
            logger.warning(f"  {conflict.file}: {', '.join(conflict.workers)}")
        if blocked:
            logger.error("Blocking execution due to conflicts (BLOCK_ON_CONFLICT=True)")
        else:
            logger.warning("Proceeding with conflicts (BLOCK_ON_CONFLICT=False)")

    return ConflictReport(
        has_conflicts=has_conflicts,
        conflicts=conflicts,
        blocked=blocked,
    )


def render_conflict_report(report: ConflictReport) -> str:
    """
    Render conflict report as human-readable text.

    Args:
        report: ConflictReport to render

    Returns:
        Formatted text output
    """
    lines = []

    if not report.has_conflicts:
        lines.append("No file conflicts detected")
        return "\n".join(lines)

    lines.append(f"File conflicts detected: {len(report.conflicts)}")
    lines.append("")

    for conflict in report.conflicts:
        lines.append(f"  File: {conflict.file}")
        lines.append(f"    Workers: {', '.join(conflict.workers)}")
        lines.append("")

    if report.blocked:
        lines.append("Execution blocked due to conflicts (BLOCK_ON_CONFLICT=True)")
    else:
        lines.append("Proceeding with conflicts (BLOCK_ON_CONFLICT=False)")

    return "\n".join(lines)


def render_conflict_report_json(report: ConflictReport) -> str:
    """
    Render conflict report as JSON.

    Args:
        report: ConflictReport to render

    Returns:
        JSON string with full detail
    """
    import json

    def conflict_to_dict(conflict: Conflict) -> dict[str, object]:
        return {
            "file": str(conflict.file),
            "workers": conflict.workers,
            "worktrees": [str(w) for w in conflict.worktrees],
        }

    report_dict: dict[str, object] = {
        "has_conflicts": report.has_conflicts,
        "blocked": report.blocked,
        "conflicts": [conflict_to_dict(c) for c in report.conflicts],
    }

    return json.dumps(report_dict, indent=2, sort_keys=True)
