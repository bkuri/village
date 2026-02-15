"""GitHub PR integration via GitHub CLI."""

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PRDescription:
    """Structured PR description with checklists."""

    summary: str
    changes: str
    testing_checklist: list[str] = field(default_factory=list)
    related_tasks: list[str] = field(default_factory=list)
    commit_suggestions: list[str] = field(default_factory=list)


@dataclass
class SyncResult:
    """Result of PR status synchronization."""

    success: bool
    pr_number: int
    pr_status: str
    message: str


class GitHubError(Exception):
    """GitHub operation error."""

    pass


def _run_gh_command(args: list[str], cwd: Optional[Path] = None) -> str:
    """
    Run GitHub CLI command and return output.

    Args:
        args: Command arguments (excluding 'gh')
        cwd: Working directory

    Returns:
        Command stdout

    Raises:
        GitHubError: If gh command fails
    """
    try:
        result = subprocess.run(
            ["gh", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        raise GitHubError(f"gh command failed: {error_msg}") from e
    except FileNotFoundError:
        raise GitHubError("GitHub CLI (gh) not installed") from None


def _get_git_diff(worktree_path: Path) -> str:
    """
    Get git diff output for changes.

    Args:
        worktree_path: Path to worktree directory

    Returns:
        Git diff output

    Raises:
        GitHubError: If git diff fails
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--name-status"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise GitHubError(f"git diff failed: {e.stderr.strip()}") from e


def _parse_file_changes(diff_output: str) -> dict[str, list[str]]:
    """
    Parse git diff output into categorized changes.

    Args:
        diff_output: Output from git diff --name-status

    Returns:
        Dict with keys 'added', 'modified', 'deleted', 'renamed'
    """
    changes: dict[str, list[str]] = {"added": [], "modified": [], "deleted": [], "renamed": []}

    for line in diff_output.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0], parts[1]

        if status == "A":
            changes["added"].append(path)
        elif status == "M":
            changes["modified"].append(path)
        elif status == "D":
            changes["deleted"].append(path)
        elif status.startswith("R") and len(parts) >= 3:
            changes["renamed"].append(parts[2])

    return changes


def _get_task_metadata(task_id: str) -> dict[str, str]:
    """
    Get task metadata from Beads if available.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")

    Returns:
        Dict of metadata key-value pairs
    """
    metadata: dict[str, str] = {}

    try:
        result = subprocess.run(
            ["bd", "show", task_id],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        for line in result.stdout.split("\n"):
            if ":" in line and not line.startswith("#"):
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return metadata


def _generate_summary(task_id: str, metadata: dict[str, str]) -> str:
    """
    Generate PR summary from task metadata.

    Args:
        task_id: Beads task ID
        metadata: Task metadata

    Returns:
        PR summary string
    """
    title = metadata.get("title", f"Work on task {task_id}")
    description = metadata.get("description", "")
    return f"{title}\n\n{description}" if description else title


def _generate_changes_summary(changes: dict[str, list[str]]) -> str:
    """
    Generate summary of file changes.

    Args:
        changes: Parsed file changes

    Returns:
        Formatted changes summary
    """
    sections = []
    for change_type, files in changes.items():
        if files:
            sections.append(f"**{change_type.capitalize()}** ({len(files)})")
            for f in files[:10]:
                sections.append(f"  - {f}")
            if len(files) > 10:
                sections.append(f"  ... and {len(files) - 10} more")

    return "\n".join(sections) if sections else "No changes detected"


def _generate_testing_checklist(changes: dict[str, list[str]]) -> list[str]:
    """
    Generate testing checklist based on changes.

    Args:
        changes: Parsed file changes

    Returns:
        List of checklist items
    """
    checklist = []
    if changes.get("added") or changes.get("modified"):
        checklist.append("- [ ] Code review completed")
        checklist.append("- [ ] Unit tests passing")
        checklist.append("- [ ] Integration tests passing")

        has_python = any(
            f.endswith(".py") for f in changes.get("added", []) + changes.get("modified", [])
        )
        if has_python:
            checklist.append("- [ ] Type checking passed (mypy)")
            checklist.append("- [ ] Linting passed (ruff)")

        has_tests = any("test" in f for f in changes.get("added", []) + changes.get("modified", []))
        if has_tests:
            checklist.append("- [ ] Test coverage reviewed")

    if changes.get("deleted"):
        checklist.append("- [ ] Verified no breaking changes from deletions")

    return checklist


def _generate_commit_suggestions(metadata: dict[str, str]) -> list[str]:
    """
    Generate commit message suggestions.

    Args:
        metadata: Task metadata

    Returns:
        List of commit suggestions
    """
    suggestions = []
    title = metadata.get("title", "")
    task_id = metadata.get("id", "")

    if title:
        suggestions.append(f"feat: {title}")
        suggestions.append(f"chore: work on {task_id}")

    return suggestions


def generate_pr_description(task_id: str, worktree_path: Path) -> PRDescription:
    """
    Generate PR description from task metadata and git diff.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        worktree_path: Path to worktree directory

    Returns:
        PRDescription with summary, changes, and checklists

    Raises:
        GitHubError: If git operations fail
    """
    diff_output = _get_git_diff(worktree_path)
    changes = _parse_file_changes(diff_output)
    metadata = _get_task_metadata(task_id)

    summary = _generate_summary(task_id, metadata)
    changes_summary = _generate_changes_summary(changes)
    testing_checklist = _generate_testing_checklist(changes)
    related_tasks = [task_id]
    commit_suggestions = _generate_commit_suggestions(metadata)

    return PRDescription(
        summary=summary,
        changes=changes_summary,
        testing_checklist=testing_checklist,
        related_tasks=related_tasks,
        commit_suggestions=commit_suggestions,
    )


def sync_pr_status(task_id: str, pr_number: int) -> SyncResult:
    """
    Sync PR status with Beads task completion.

    Args:
        task_id: Beads task ID (e.g., "bd-a3f8")
        pr_number: GitHub PR number

    Returns:
        SyncResult with status and message
    """
    try:
        pr_data = _run_gh_command(["pr", "view", str(pr_number), "--json", "state,merged,mergedAt"])
        import json

        pr_info = json.loads(pr_data)
        pr_state = pr_info.get("state", "")
        is_merged = pr_info.get("merged", False)

        if is_merged:
            pr_status = "merged"
            message = f"PR #{pr_number} is merged"
        elif pr_state == "open":
            pr_status = "open"
            message = f"PR #{pr_number} is open"
        elif pr_state == "closed":
            pr_status = "closed"
            message = f"PR #{pr_number} is closed"
        else:
            pr_status = "unknown"
            message = f"PR #{pr_number} status: {pr_state}"

        return SyncResult(
            success=True,
            pr_number=pr_number,
            pr_status=pr_status,
            message=message,
        )

    except GitHubError as e:
        return SyncResult(
            success=False,
            pr_number=pr_number,
            pr_status="error",
            message=str(e),
        )
    except json.JSONDecodeError as e:
        return SyncResult(
            success=False,
            pr_number=pr_number,
            pr_status="error",
            message=f"Failed to parse PR data: {e}",
        )


def add_pr_labels(pr_number: int, labels: list[str]) -> None:
    """
    Add labels to a PR.

    Args:
        pr_number: GitHub PR number
        labels: List of label names

    Raises:
        GitHubError: If gh command fails
    """
    if not labels:
        return

    try:
        _run_gh_command(["pr", "edit", str(pr_number), "--add-label", ",".join(labels)])
        logger.info(f"Added labels to PR #{pr_number}: {', '.join(labels)}")
    except GitHubError as e:
        raise GitHubError(f"Failed to add labels to PR #{pr_number}: {e}") from e


def create_pr(
    title: str,
    description: PRDescription,
    branch: str,
    base: str = "main",
    labels: Optional[list[str]] = None,
) -> int:
    """
    Create a new PR with the given description.

    Args:
        title: PR title
        description: PR description
        branch: Branch name
        base: Base branch (default: main)
        labels: Optional list of labels to add

    Returns:
        PR number

    Raises:
        GitHubError: If gh command fails
    """
    pr_body = f"{description.summary}\n\n## Changes\n{description.changes}"

    if description.testing_checklist:
        pr_body += "\n\n## Testing Checklist\n" + "\n".join(description.testing_checklist)

    if description.related_tasks:
        pr_body += "\n\n## Related Tasks\n" + "\n".join(f"- {t}" for t in description.related_tasks)

    if description.commit_suggestions:
        pr_body += "\n\n## Commit Suggestions\n" + "\n".join(
            f"- {s}" for s in description.commit_suggestions
        )

    try:
        output = _run_gh_command(
            [
                "pr",
                "create",
                "--title",
                title,
                "--body",
                pr_body,
                "--base",
                base,
                "--head",
                branch,
            ]
        )
        pr_url = output.strip()
        pr_number = int(pr_url.split("/")[-1])

        if labels:
            add_pr_labels(pr_number, labels)

        logger.info(f"Created PR #{pr_number}: {pr_url}")
        return pr_number

    except GitHubError as e:
        raise GitHubError(f"Failed to create PR: {e}") from e
