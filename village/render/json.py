"""JSON renderer with stable schema and versioning."""

import json

from village.ready import ReadyAssessment
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


def render_ready_json(assessment: ReadyAssessment) -> str:
    """
    Render readiness assessment as JSON.

    Schema version 1:
      {
        "command": "ready",
        "version": 1,
        "assessment": {
          "overall": "<state>",
          "environment_ready": bool,
          "runtime_ready": bool,
          "work_available": "<status>",
          "orphans_count": int,
          "stale_locks_count": int,
          "untracked_worktrees_count": int,
          "active_workers_count": int,
          "ready_tasks_count": int|null,
          "error": string|null
        }
      }

    NOTE: No suggested_actions in JSON (text renderer only).

    Args:
        assessment: ReadyAssessment object to render

    Returns:
        JSON string with stable key ordering
    """
    output = {
        "command": "ready",
        "version": JSON_VERSION,
        "assessment": {
            "overall": assessment.overall,
            "environment_ready": assessment.environment_ready,
            "runtime_ready": assessment.runtime_ready,
            "work_available": assessment.work_available,
            "orphans_count": assessment.orphans_count,
            "stale_locks_count": assessment.stale_locks_count,
            "untracked_worktrees_count": assessment.untracked_worktrees_count,
            "active_workers_count": assessment.active_workers_count,
            "ready_tasks_count": assessment.ready_tasks_count,
            "error": assessment.error,
        },
    }

    return json.dumps(output, sort_keys=True)
