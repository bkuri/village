"""Release dashboard rendering."""

from datetime import datetime, timezone

from village.release.queue import PendingBump, ReleaseRecord
from village.release.version import aggregate_bumps


def format_release_dashboard(
    history: list[ReleaseRecord],
    pending: list[PendingBump],
    open_tasks: list[dict[str, str]],
) -> str:
    """Format release dashboard for display."""
    lines = ["# Release Status\n"]

    if history:
        lines.append("## Last Releases")
        lines.append("| Version | Date       | Bump  | Tasks |")
        lines.append("|---------|------------|-------|-------|")
        for record in history[:5]:
            date_str = record.released_at.strftime("%Y-%m-%d")
            lines.append(f"| {record.version:<7} | {date_str} | {record.aggregate_bump:<5} | {len(record.tasks)}     |")
        lines.append("")

    if pending:
        aggregate = aggregate_bumps([b.bump for b in pending])
        lines.append("## Pending Release")
        lines.append(f"Aggregate: **{aggregate}** ({len(pending)} tasks)")
        lines.append("| Task    | Bump  | Completed     |")
        lines.append("|---------|-------|---------------|")
        for bump in pending:
            ago = _format_time_ago(bump.completed_at)
            lines.append(f"| {bump.task_id:<7} | {bump.bump:<5} | {ago:<13} |")
        lines.append("")

    if open_tasks:
        lines.append("## Open Tasks with Bump Labels")
        lines.append("| Task    | Title              | Bump  | Status      |")
        lines.append("|---------|--------------------|-------|-------------|")
        for task in open_tasks[:10]:
            title = task.get("title", "")[:18]
            task_id = task.get("task_id", "")
            bump_type = task.get("bump", "")
            status = task.get("status", "")
            lines.append(f"| {task_id:<7} | {title:<18} | {bump_type:<5} | {status:<11} |")
        lines.append("")

    if not pending and not open_tasks and not history:
        lines.append("No pending releases or bump-labeled tasks.")

    lines.append("\nRun `village builder arrange --dry-run` to preview, `village builder arrange` to apply.")

    return "\n".join(lines)


def _format_time_ago(dt: datetime) -> str:
    """Format datetime as relative time."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    diff = now - dt

    if diff.days > 0:
        return f"{diff.days}d ago"
    seconds = int(diff.total_seconds())
    if seconds >= 3600:
        hours = seconds // 3600
        return f"{hours}h ago"
    if seconds >= 60:
        mins = seconds // 60
        return f"{mins}m ago"
    return "just now"
