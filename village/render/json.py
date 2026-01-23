"""JSON renderer with stable schema and versioning."""

import json

from village.status import FullStatus

JSON_VERSION = 1


def render_status_json(status: FullStatus) -> str:
    """
    Render full status as JSON.

    Schema version 1:
      {
        "command": "status",
        "version": 1,
        "summary": { ... },
        "workers": [ ... ],
        "orphans": [ ... ]
      }

    Args:
        status: FullStatus object to render

    Returns:
        JSON string with stable key ordering
    """
    output = {
        "command": "status",
        "version": JSON_VERSION,
        "summary": {
            "tmux_running": status.summary.tmux_running,
            "tmux_session": status.summary.tmux_session,
            "locks_count": status.summary.locks_count,
            "locks_active": status.summary.locks_active,
            "locks_stale": status.summary.locks_stale,
            "worktrees_count": status.summary.worktrees_count,
            "worktrees_tracked": status.summary.worktrees_tracked,
            "worktrees_untracked": status.summary.worktrees_untracked,
            "config_exists": status.summary.config_exists,
            "orphans_count": status.summary.orphans_count,
        },
        "workers": [
            {
                "task_id": w.task_id,
                "pane_id": w.pane_id,
                "window": w.window,
                "agent": w.agent,
                "claimed_at": w.claimed_at,
                "status": w.status,
            }
            for w in status.workers
        ],
        "orphans": [
            {
                "type": o.type,
                "task_id": o.task_id,
                "path": o.path,
                "reason": o.reason,
            }
            for o in status.orphans
        ],
    }

    return json.dumps(output, sort_keys=True)
