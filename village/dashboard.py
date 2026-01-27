"""Real-time terminal UI dashboard for monitoring Village state."""

import logging
import select
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from village.config import get_config
from village.queue import generate_queue_plan
from village.render.text import render_worker_table
from village.status import collect_full_status, collect_orphans

if TYPE_CHECKING:
    from village.queue import QueuePlan
    from village.status import FullStatus, Orphan

logger = logging.getLogger(__name__)


@dataclass
class DashboardState:
    """Current dashboard state."""

    session_name: str
    max_workers: int
    last_refresh: float


class VillageDashboard:
    """Real-time terminal UI dashboard for monitoring Village state."""

    def __init__(self, session_name: str | None = None):
        """
        Initialize dashboard.

        Args:
            session_name: Tmux session name (uses config default if None)
        """
        self.config = get_config()
        self.session_name = session_name or self.config.tmux_session
        self.state = DashboardState(
            session_name=self.session_name,
            max_workers=self.config.max_workers,
            last_refresh=0.0,
        )
        self._running = False

    def start_watch_mode(self, refresh_interval: int = 2) -> None:
        """
        Start interactive watch mode.

        Auto-refreshes display every refresh_interval seconds.
        Supports keyboard input: 'q' to quit, 'r' to refresh.

        Args:
            refresh_interval: Refresh interval in seconds (default: 2)
        """
        self._running = True
        logger.info(f"Starting dashboard watch mode (refresh: {refresh_interval}s)")

        try:
            while self._running:
                self.refresh_display()
                self.state.last_refresh = time.time()

                if self._wait_for_input(refresh_interval):
                    if self._handle_input():
                        break

        except KeyboardInterrupt:
            logger.info("Dashboard interrupted by user")
        finally:
            self.quit()

    def refresh_display(self) -> None:
        """Refresh display with current Village state."""
        from village.event_log import log_dashboard_refresh

        clear_screen()

        full_status = collect_full_status(self.session_name)
        queue_plan = generate_queue_plan(self.session_name, self.config.max_workers)
        orphans = collect_orphans(self.session_name, full_status.workers)

        render_dashboard(full_status, queue_plan, orphans, self.state)

        log_dashboard_refresh(self.config.village_dir)

    def quit(self) -> None:
        """Quit dashboard and restore terminal state."""
        self._running = False
        show_cursor()
        logger.info("Dashboard stopped")

    def _wait_for_input(self, timeout: int) -> bool:
        """
        Wait for keyboard input with timeout.

        Args:
            timeout: Timeout in seconds

        Returns:
            True if input available, False otherwise
        """
        if select.select([sys.stdin], [], [], timeout)[0]:
            return True
        return False

    def _handle_input(self) -> bool:
        """
        Handle keyboard input.

        Returns:
            True if should quit, False otherwise
        """
        try:
            char = sys.stdin.read(1)
            if char.lower() == "q":
                return True
            elif char.lower() == "r":
                self.refresh_display()
        except (IOError, OSError):
            pass
        return False


def clear_screen() -> None:
    """Clear terminal screen."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def hide_cursor() -> None:
    """Hide cursor."""
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()


def show_cursor() -> None:
    """Show cursor."""
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


def move_cursor(row: int, col: int) -> None:
    """
    Move cursor to specific position.

    Args:
        row: Row number (1-indexed)
        col: Column number (1-indexed)
    """
    sys.stdout.write(f"\033[{row};{col}H")
    sys.stdout.flush()


def render_dashboard(
    full_status: "FullStatus",
    queue_plan: "QueuePlan",
    orphans: list["Orphan"],
    state: DashboardState,
) -> None:
    """
    Render complete dashboard.

    Args:
        full_status: FullStatus object from collect_full_status
        queue_plan: QueuePlan object from generate_queue_plan
        orphans: List of Orphan objects
        state: DashboardState object
    """
    hide_cursor()
    lines = []

    header = f"Village Dashboard - {time.strftime('%Y-%m-%d %H:%M:%S')}"
    lines.append(header)
    lines.append("=" * len(header))
    lines.append("")

    workers_line = f"Active Workers: {full_status.summary.locks_active}/{state.max_workers}"
    lines.append(workers_line)

    session_status = "running" if full_status.summary.tmux_running else "not running"
    session_line = f"Session: {state.session_name} ({session_status})"
    lines.append(session_line)

    orphans_line = f"Orphans: {len(orphans)}"
    lines.append(orphans_line)
    lines.append("")

    lines.append("ACTIVE WORKERS")
    lines.append("-" * 80)
    if full_status.workers:
        worker_table = render_worker_table(full_status.workers)
        lines.append(worker_table)
    else:
        lines.append("No active workers")
    lines.append("")

    lines.append("TASK QUEUE")
    lines.append("-" * 80)
    lines.append(f"Ready tasks: {len(queue_plan.ready_tasks)}")
    lines.append(f"Available tasks: {len(queue_plan.available_tasks)}")
    lines.append(f"Blocked tasks: {len(queue_plan.blocked_tasks)}")
    lines.append("")

    if queue_plan.available_tasks:
        lines.append("Available tasks (will start):")
        for task in queue_plan.available_tasks[:5]:
            lines.append(f"  - {task.task_id} (agent: {task.agent})")
        if len(queue_plan.available_tasks) > 5:
            lines.append(f"  ... and {len(queue_plan.available_tasks) - 5} more")
        lines.append("")

    if queue_plan.blocked_tasks:
        lines.append("Blocked tasks:")
        for task in queue_plan.blocked_tasks[:5]:
            reason = task.skip_reason or "unknown"
            lines.append(f"  - {task.task_id} (agent: {task.agent}) - {reason}")
        if len(queue_plan.blocked_tasks) > 5:
            lines.append(f"  ... and {len(queue_plan.blocked_tasks) - 5} more")
        lines.append("")

    lines.append("LOCK STATUS")
    lines.append("-" * 80)
    lines.append(f"Total locks: {full_status.summary.locks_count}")
    lines.append(f"Active locks: {full_status.summary.locks_active}")
    lines.append(f"Stale locks: {full_status.summary.locks_stale}")
    lines.append("")

    if orphans:
        lines.append("ORPHANS")
        lines.append("-" * 80)
        stale_locks = [o for o in orphans if o.type == "STALE_LOCK"]
        untracked_worktrees = [o for o in orphans if o.type == "UNTRACKED_WORKTREE"]

        if stale_locks:
            lines.append(f"Stale locks ({len(stale_locks)}):")
            for orphan in stale_locks[:5]:
                lines.append(f"  - {orphan.task_id}")
            if len(stale_locks) > 5:
                lines.append(f"  ... and {len(stale_locks) - 5} more")
            lines.append("")

        if untracked_worktrees:
            lines.append(f"Untracked worktrees ({len(untracked_worktrees)}):")
            for orphan in untracked_worktrees[:5]:
                lines.append(f"  - {orphan.path}")
            if len(untracked_worktrees) > 5:
                lines.append(f"  ... and {len(untracked_worktrees) - 5} more")
            lines.append("")

    lines.append("")
    lines.append("CONTROLS")
    lines.append("-" * 80)
    lines.append("q: Quit | r: Refresh")
    lines.append("")
    lines.append(f"Last refresh: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    output = "\n".join(lines)
    sys.stdout.write(output)
    sys.stdout.flush()


def render_dashboard_static(
    session_name: str | None = None,
) -> str:
    """
    Render dashboard as static text (for non-interactive use).

    Args:
        session_name: Tmux session name (uses config default if None)

    Returns:
        Formatted dashboard string
    """
    from io import StringIO

    config = get_config()
    session_name = session_name or config.tmux_session

    full_status = collect_full_status(session_name)
    queue_plan = generate_queue_plan(session_name, config.max_workers)
    orphans = collect_orphans(session_name, full_status.workers)

    state = DashboardState(
        session_name=session_name,
        max_workers=config.max_workers,
        last_refresh=time.time(),
    )

    output = StringIO()
    lines = []

    header = f"Village Dashboard - {time.strftime('%Y-%m-%d %H:%M:%S')}"
    lines.append(header)
    lines.append("=" * len(header))
    lines.append("")

    workers_line = f"Active Workers: {full_status.summary.locks_active}/{state.max_workers}"
    lines.append(workers_line)

    session_status = "running" if full_status.summary.tmux_running else "not running"
    session_line = f"Session: {state.session_name} ({session_status})"
    lines.append(session_line)

    orphans_line = f"Orphans: {len(orphans)}"
    lines.append(orphans_line)
    lines.append("")

    lines.append("ACTIVE WORKERS")
    lines.append("-" * 80)
    if full_status.workers:
        worker_table = render_worker_table(full_status.workers)
        lines.append(worker_table)
    else:
        lines.append("No active workers")
    lines.append("")

    lines.append("TASK QUEUE")
    lines.append("-" * 80)
    lines.append(f"Ready tasks: {len(queue_plan.ready_tasks)}")
    lines.append(f"Available tasks: {len(queue_plan.available_tasks)}")
    lines.append(f"Blocked tasks: {len(queue_plan.blocked_tasks)}")
    lines.append("")

    if queue_plan.available_tasks:
        lines.append("Available tasks (will start):")
        for task in queue_plan.available_tasks[:5]:
            lines.append(f"  - {task.task_id} (agent: {task.agent})")
        if len(queue_plan.available_tasks) > 5:
            lines.append(f"  ... and {len(queue_plan.available_tasks) - 5} more")
        lines.append("")

    if queue_plan.blocked_tasks:
        lines.append("Blocked tasks:")
        for task in queue_plan.blocked_tasks[:5]:
            reason = task.skip_reason or "unknown"
            lines.append(f"  - {task.task_id} (agent: {task.agent}) - {reason}")
        if len(queue_plan.blocked_tasks) > 5:
            lines.append(f"  ... and {len(queue_plan.blocked_tasks) - 5} more")
        lines.append("")

    lines.append("LOCK STATUS")
    lines.append("-" * 80)
    lines.append(f"Total locks: {full_status.summary.locks_count}")
    lines.append(f"Active locks: {full_status.summary.locks_active}")
    lines.append(f"Stale locks: {full_status.summary.locks_stale}")
    lines.append("")

    if orphans:
        lines.append("ORPHANS")
        lines.append("-" * 80)
        stale_locks = [o for o in orphans if o.type == "STALE_LOCK"]
        untracked_worktrees = [o for o in orphans if o.type == "UNTRACKED_WORKTREE"]

        if stale_locks:
            lines.append(f"Stale locks ({len(stale_locks)}):")
            for orphan in stale_locks[:5]:
                lines.append(f"  - {orphan.task_id}")
            if len(stale_locks) > 5:
                lines.append(f"  ... and {len(stale_locks) - 5} more")
            lines.append("")

        if untracked_worktrees:
            lines.append(f"Untracked worktrees ({len(untracked_worktrees)}):")
            for orphan in untracked_worktrees[:5]:
                lines.append(f"  - {orphan.path}")
            if len(untracked_worktrees) > 5:
                lines.append(f"  ... and {len(untracked_worktrees) - 5} more")
            lines.append("")

    output.write("\n".join(lines))
    return output.getvalue()
