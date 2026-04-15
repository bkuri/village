"""Landing arrangement - creates stacked PRs when all tasks complete."""

from typing import Any

from village.stack.factory import get_stack_backend
from village.stack.labels import create_pr_specs
from village.tasks import get_task_store


def arrange_landing(dry_run: bool = False) -> dict[str, Any]:
    """Arrange all done tasks into stacked PRs and trigger landing.

    Args:
        dry_run: If True, just return the PR specs without creating them

    Returns:
        Dict with created PRs info
    """
    store = get_task_store()
    backend = get_stack_backend()

    done_tasks = store.list_tasks(status="done")
    if not done_tasks:
        return {"prs": [], "message": "No completed tasks"}

    task_dicts = [{"id": t.id, "title": t.title, "labels": t.labels} for t in done_tasks]

    pr_specs = create_pr_specs(task_dicts, "landing", flat=False)

    if dry_run:
        return {"prs": pr_specs, "message": "Dry run"}

    trunk = backend.get_default_trunk()
    created = []

    for i, spec in enumerate(pr_specs):
        base_branch = trunk if i == 0 else pr_specs[i - 1]["head"]
        try:
            branch = backend.create_branch(spec["head"], base_branch)
            backend.push_branch(spec["head"])
            created.append(
                {
                    "branch": branch,
                    "layer": spec["layer"],
                    "tasks": spec["tasks"],
                }
            )
        except Exception as e:
            created.append(
                {
                    "branch": spec["head"],
                    "layer": spec["layer"],
                    "tasks": spec["tasks"],
                    "error": str(e),
                }
            )

    return {"prs": created, "trunk": trunk}
