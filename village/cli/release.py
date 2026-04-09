"""Release command for version management."""

import sys
from datetime import datetime, timezone

import click

from village.errors import EXIT_ERROR, EXIT_SUCCESS
from village.logging import get_logger

logger = get_logger(__name__)


@click.command()
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
        village release                # Apply pending bumps
        village release --dry-run      # Preview what would happen
        village release --no-changelog # Skip CHANGELOG update
        village release --no-tag       # Skip git tag
        village release --force        # Skip unlabeled-task check

    Exit codes:
        0: Release applied successfully
        1: Unlabeled closed tasks found, no pending bumps, or error
    """
    import subprocess as _subprocess

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

    # --- a) Check for unlabeled closed tasks ---
    if not force:
        unlabeled = get_unlabeled_closed_tasks()
        if unlabeled:
            click.echo(f"Error: {len(unlabeled)} closed task(s) have no bump label:", err=True)
            for task in unlabeled:
                click.echo(f"  {task['id']}  {task['title']}", err=True)
            click.echo("Label them with: bd label add <id> bump:<major|minor|patch|none>", err=True)
            click.echo("Or use --force to skip this check.", err=True)
            sys.exit(EXIT_ERROR)

    # --- b) Get pending bumps ---
    pending = get_pending_bumps()

    if not pending:
        click.echo("No pending version bumps")
        sys.exit(EXIT_SUCCESS)

    # --- c) Compute aggregate and check for no-op ---
    aggregate = aggregate_bumps([b.bump for b in pending])

    if is_no_op_release([b.bump for b in pending]):
        click.echo("All pending tasks are bump:none — no version change required.")
        click.echo("Clearing queue without creating a release.")
        if dry_run:
            click.echo("(dry-run: would clear queue, no version bump)")
            return
        clear_pending_bumps()
        sys.exit(EXIT_SUCCESS)

    # --- d) Compute next version ---
    try:
        version = compute_next_version(aggregate)
    except ValueError as exc:
        click.echo(f"Error computing version: {exc}", err=True)
        sys.exit(EXIT_ERROR)

    click.echo(f"New version: {version} (bump: {aggregate})")

    # --- e) Dry-run exit ---
    if dry_run:
        task_ids_preview = [b.task_id for b in pending]
        click.echo(f"Pending tasks ({len(pending)}): {', '.join(task_ids_preview)}")
        click.echo("(dry-run: no changes applied)")
        return

    # --- f) Apply changelog ---
    if changelog:
        try:
            update_changelog(version, pending)
            click.echo(f"Updated CHANGELOG.md with version {version}")
        except Exception as exc:  # noqa: BLE001
            click.echo(f"Warning: CHANGELOG update failed: {exc}", err=True)

    # --- g) Apply tag ---
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

    # --- h) Clear queue and record release ---
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
