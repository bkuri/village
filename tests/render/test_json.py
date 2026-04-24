import json

from village.ready import ReadyAssessment
from village.render.json import render_ready_json


def test_render_ready_json_with_error():
    assessment = ReadyAssessment(
        overall="error",
        environment_ready=False,
        runtime_ready=False,
        work_available="unknown",
        orphans_count=0,
        stale_locks_count=0,
        untracked_worktrees_count=0,
        active_workers_count=0,
        ready_tasks_count=None,
        suggested_actions=[],
        error="Something went wrong",
    )

    output = render_ready_json(assessment)
    data = json.loads(output)

    assert data["command"] == "ready"
    assert data["version"] == 1
    assert data["assessment"]["overall"] == "error"
    assert data["assessment"]["error"] == "Something went wrong"
    assert data["assessment"]["ready_tasks_count"] is None
    assert data["assessment"]["environment_ready"] is False
    assert data["assessment"]["runtime_ready"] is False


def test_render_ready_json_with_orphans_and_workers():
    assessment = ReadyAssessment(
        overall="ready_with_actions",
        environment_ready=True,
        runtime_ready=True,
        work_available="available",
        orphans_count=3,
        stale_locks_count=2,
        untracked_worktrees_count=1,
        active_workers_count=1,
        ready_tasks_count=5,
        suggested_actions=[],
        error=None,
    )

    output = render_ready_json(assessment)
    data = json.loads(output)

    assert data["assessment"]["orphans_count"] == 3
    assert data["assessment"]["stale_locks_count"] == 2
    assert data["assessment"]["untracked_worktrees_count"] == 1
    assert data["assessment"]["active_workers_count"] == 1
    assert data["assessment"]["ready_tasks_count"] == 5
    assert data["assessment"]["error"] is None
