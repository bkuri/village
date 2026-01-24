"""Text renderer for status output."""

from datetime import datetime, timezone

from village.chat.drafts import DraftTask
from village.ready import ReadyAssessment, SuggestedAction
from village.resume import ResumeAction, ResumeResult
from village.runtime import InitializationPlan
from village.status import FullStatus, Orphan, StatusSummary, Worker


def format_datetime(iso_string: str) -> str:
    """
    Format ISO datetime for human-readable output.

    Args:
        iso_string: ISO 8601 datetime string

    Returns:
        Formatted datetime string (e.g., "2026-01-22 10:41:12 UTC")
    """
    try:
        dt = datetime.fromisoformat(iso_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    except (ValueError, AttributeError):
        return iso_string


def render_worker_table(workers: list[Worker]) -> str:
    """
    Render workers as tabular table.

    Columns: TASK_ID, STATUS, PANE, AGENT, WINDOW, CLAIMED_AT

    Args:
        workers: List of Worker objects

    Returns:
        Formatted table string
    """
    if not workers:
        return "No workers found"

    headers = ["TASK_ID", "STATUS", "PANE", "AGENT", "WINDOW", "CLAIMED_AT"]
    rows = [
        [
            w.task_id,
            w.status,
            w.pane_id,
            w.agent,
            w.window,
            format_datetime(w.claimed_at),
        ]
        for w in workers
    ]

    col_widths = [max(len(str(row[i])) for row in [headers] + rows) for i in range(len(headers))]

    separator = "  "
    lines = []

    header_line = separator.join(f"{headers[i]:<{col_widths[i]}}" for i in range(len(headers)))
    lines.append(header_line)

    separator_line = separator.join("-" * col_widths[i] for i in range(len(headers)))
    lines.append(separator_line)

    for row in rows:
        row_line = separator.join(f"{str(row[i]):<{col_widths[i]}}" for i in range(len(row)))
        lines.append(row_line)

    return "\n".join(lines)


def render_orphans_grouped(orphans: list[Orphan], show_actions: bool = True) -> str:
    """
    Render orphans grouped by type with suggested actions.

    Args:
        orphans: List of Orphan objects
        show_actions: Show suggested actions (text renderer only)

    Returns:
        Formatted orphans string
    """
    if not orphans:
        return "No orphans found"

    stale_locks = [o for o in orphans if o.type == "STALE_LOCK"]
    untracked_worktrees = [o for o in orphans if o.type == "UNTRACKED_WORKTREE"]

    lines = [f"ORPHANS ({len(orphans)}):", ""]

    if stale_locks:
        lines.append(f"  STALE LOCKS ({len(stale_locks)}):")
        for orphan in stale_locks:
            pane_id = orphan.task_id.split("-")[0] if orphan.task_id else "unknown"
            lines.append(f"    {orphan.task_id} (pane: {pane_id})")
        lines.append("")

    if untracked_worktrees:
        lines.append(f"  UNTRACKED WORKTREES ({len(untracked_worktrees)}):")
        for orphan in untracked_worktrees:
            if orphan.path:
                lines.append(f"    {orphan.path}")
        lines.append("")

    if show_actions:
        lines.append("  SUGGESTED ACTIONS:")
        if stale_locks:
            lines.append("    - village cleanup (remove stale locks)")
        if untracked_worktrees:
            lines.append("    - village worktree prune (remove untracked worktrees)")

    return "\n".join(lines)


def render_summary(summary: StatusSummary) -> str:
    """
    Render summary-only output.

    Args:
        summary: StatusSummary object

    Returns:
        Formatted summary string
    """
    lines = [
        f"Village directory: {summary.tmux_session}",
        f"TMUX session: {summary.tmux_session} "
        f"{'running' if summary.tmux_running else 'not running'}",
        f"Lock files: {summary.locks_count} "
        f"({summary.locks_active} ACTIVE, {summary.locks_stale} STALE)",
    ]

    if summary.worktrees_count > 0:
        lines.append(
            f"Worktrees: {summary.worktrees_count} "
            f"({summary.worktrees_tracked} tracked, {summary.worktrees_untracked} untracked)"
        )
    else:
        lines.append("Worktrees: 0 (0 tracked, 0 untracked)")

    lines.append(f"Config file: {'exists' if summary.config_exists else 'not created'}")

    if summary.orphans_count > 0:
        lines.append("")
        lines.append("WARNING: Orphans detected (use --orphans for details)")

    lines.append("")
    lines.append("Use --workers, --locks, --orphans for details.")

    return "\n".join(lines)


def render_full_status(status: FullStatus, flags: dict[str, bool]) -> str:
    """
    Render full status based on flags.

    If no flags, show summary only.

    Args:
        status: FullStatus object
        flags: Dict of flag states {"workers": bool, "locks": bool, "orphans": bool}

    Returns:
        Formatted status string
    """
    show_workers = flags.get("workers", False)
    show_locks = flags.get("locks", False)
    show_orphans = flags.get("orphans", False)

    if not (show_workers or show_locks or show_orphans):
        return render_summary(status.summary)

    lines = [render_summary(status.summary), ""]

    if show_workers:
        lines.append(render_worker_table(status.workers))
        lines.append("")

    if show_locks:
        lines.append(render_worker_table(status.workers))
        lines.append("")

    if show_orphans:
        lines.append(render_orphans_grouped(status.orphans))

    return "\n".join(lines)


def render_suggested_actions(actions: list[SuggestedAction]) -> str:
    """
    Render suggested actions in priority order.

    Format:
      SUGGESTED ACTIONS:
        1. [BLOCKING] village up
           Reason: Runtime not initialized
        2. village cleanup
           Reason: Remove 2 stale locks

    Blocking actions shown first with [BLOCKING] label.

    Args:
        actions: List of SuggestedAction objects

    Returns:
        Formatted suggested actions string
    """
    if not actions:
        return "SUGGESTED ACTIONS:\n  None (everything looks good)"

    lines = ["SUGGESTED ACTIONS:", ""]

    for i, action in enumerate(actions, 1):
        prefix = f"  {i}. [BLOCKING]" if action.blocking else f"  {i}."
        lines.append(f"{prefix} {action.action}")
        lines.append(f"     Reason: {action.reason}")

    return "\n".join(lines)


def render_ready_text(assessment: ReadyAssessment) -> str:
    """
    Render readiness assessment as human-readable text.

    Layout:
      1. Overall state (prominent)
      2. Status of each check (environment, runtime, work)
      3. Orphans summary
      4. Suggested actions (with priorities)

    Args:
        assessment: ReadyAssessment object

    Returns:
        Formatted readiness string
    """
    lines = []

    # Overall state
    state_label = assessment.overall.upper().replace("_", " ")
    lines.append(f"OVERALL STATUS: {state_label}")
    lines.append("")

    # Environment check
    if assessment.environment_ready:
        lines.append("Environment Check:   ✓ Git repository found")
    else:
        lines.append("Environment Check:   ✗ Village runtime not initialized")

    # Runtime check
    if assessment.runtime_ready:
        lines.append("Runtime Check:       ✓ Tmux session running")
    else:
        lines.append("Runtime Check:       ✗ Tmux session not running")

    # Work availability
    if assessment.work_available == "available":
        count = assessment.ready_tasks_count or 0
        lines.append(f"Work Available:      ✓ {count} ready task(s) available")
    elif assessment.work_available == "not_available":
        lines.append("Work Available:      ✓ No ready tasks available")
    elif assessment.work_available == "unknown":
        lines.append("Work Available:      ? Cannot determine (Beads not available)")

    # Orphans
    if assessment.orphans_count > 0:
        orphans_parts = []
        if assessment.stale_locks_count > 0:
            orphans_parts.append(f"{assessment.stale_locks_count} stale locks")
        if assessment.untracked_worktrees_count > 0:
            orphans_parts.append(f"{assessment.untracked_worktrees_count} untracked worktrees")

        lines.append(f"Orphans:             ✗ {', '.join(orphans_parts)}")
    else:
        lines.append("Orphans:             ✓ None")

    # Error message if present
    if assessment.error:
        lines.append("")
        lines.append(f"ERROR: {assessment.error}")

    # Suggested actions
    lines.append("")
    lines.append(render_suggested_actions(assessment.suggested_actions))

    return "\n".join(lines)


def render_initialization_plan(plan: "InitializationPlan", *, plan_mode: bool = False) -> str:
    """Render initialization plan as concise one-screen summary.

    Example output:
    DRY RUN: Would initialize village runtime
      Session: village (new)
      Directories: .village/ (create)
      Beads: .beads/ (create)
      Dashboard: yes

    Args:
        plan: InitializationPlan to render
        plan_mode: If True, show "DRY RUN" prefix
    """
    prefix = "DRY RUN: " if plan_mode else ""

    lines = [f"{prefix} Would initialize village runtime", ""]

    if plan.session_exists:
        lines.append(f"  Session: {plan.session_name} (exists)")
    else:
        lines.append(f"  Session: {plan.session_name} (new)")

    if plan.directories_exist:
        lines.append("  Directories: .village/ (exists)")
    else:
        lines.append("  Directories: .village/ (create)")

    if plan.beads_initialized:
        lines.append("  Beads: .beads/ (exists)")
    else:
        lines.append("  Beads: would initialize (not found)")

    return "\n".join(lines)


def render_resume_result(result: "ResumeResult") -> str:
    """
    Render resume result as text.

    Args:
        result: ResumeResult object

    Returns:
        Formatted output
    """
    if result.success:
        output = [
            f"✓ Resume successful: {result.task_id}",
            f"  Window: {result.window_name}",
            f"  Pane: {result.pane_id}",
            f"  Worktree: {result.worktree_path}",
        ]
        return "\n".join(output)
    else:
        output = [
            f"✗ Resume failed: {result.task_id}",
        ]
        if result.error:
            output.append(f"  Error: {result.error}")
        return "\n".join(output)


def render_resume_actions(action: "ResumeAction") -> str:
    """
    Render resume action as text.
    """
    output = [
        f"Action: village {action.action}",
        f"Reason: {action.reason}",
    ]

    if action.meta:
        command = action.meta.get("command", "")
        if command:
            output.append(f"Run: {command}")

    return "\n".join(output)


def render_drafts_table(drafts: list[DraftTask]) -> str:
    """
    Render drafts as 2-column table (ID, Title).

    Args:
        drafts: List of draft tasks

    Returns:
        Formatted table string
    """

    if not drafts:
        return "No drafts found."

    sorted_drafts = sorted(drafts, key=lambda d: d.created_at, reverse=True)

    lines = []
    lines.append(f"{'ID':<20} {'Title':<60}")
    lines.append(f"{'-' * 20} {'-' * 60}")

    for draft in sorted_drafts:
        title = (draft.title[:57] + "...") if len(draft.title) > 60 else draft.title
        lines.append(f"{draft.id:<20} {title:<60}")

    return "\n".join(lines)
