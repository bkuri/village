"""JSONL file-based task store implementation."""

import fcntl
import json
import logging
import tempfile
from pathlib import Path
from typing import Optional

from village.fs import ensure_parent
from village.tasks.ids import generate_task_id
from village.tasks.models import (
    DependencyInfo,
    SearchResult,
    Task,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
)
from village.tasks.store import (
    TaskNotFoundError,
    TaskStore,
)

logger = logging.getLogger(__name__)


class FileTaskStore(TaskStore):
    """Task store backed by a single JSONL file.

    Storage format: one JSON object per line in tasks.jsonl.
    Each line is a complete Task.to_dict() record.
    Updates append new records; compaction removes superseded versions.
    """

    def __init__(self, tasks_file: Path) -> None:
        self._tasks_file = tasks_file

    def _ensure_dir(self) -> None:
        ensure_parent(self._tasks_file)

    def _read_all(self) -> dict[str, Task]:
        """Read all tasks, returning latest version of each by ID."""
        tasks: dict[str, Task] = {}
        if not self._tasks_file.exists():
            return tasks
        for line in self._tasks_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                task = Task.from_dict(data)
                tasks[task.id] = task
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(f"Skipping corrupted task line: {e}")
        return tasks

    def _append_record(self, task: Task) -> None:
        """Append a task record to the JSONL file with file locking."""
        self._ensure_dir()
        self._tasks_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self._tasks_file, "a", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(json.dumps(task.to_dict(), sort_keys=True) + "\n")
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _rewrite_all(self, tasks: dict[str, Task]) -> None:
        """Atomically rewrite the entire JSONL file (used for compaction)."""
        self._ensure_dir()
        dir_ = self._tasks_file.parent
        with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False, suffix=".tmp", encoding="utf-8") as tmp:
            for task in tasks.values():
                tmp.write(json.dumps(task.to_dict(), sort_keys=True) + "\n")
            tmp_path = Path(tmp.name)
        tmp_path.replace(self._tasks_file)

    def initialize(self) -> None:
        self._ensure_dir()
        if not self._tasks_file.exists():
            self._tasks_file.write_text("", encoding="utf-8")
            logger.info(f"Initialized task store at {self._tasks_file}")

    def is_available(self) -> bool:
        return self._tasks_file.parent.exists()

    def create_task(self, spec: TaskCreate) -> Task:
        existing = self._read_all()
        existing_ids = set(existing.keys())
        task_id = generate_task_id(existing_ids)

        depends_on = list(spec.depends_on)
        blocks = list(spec.blocks)

        if spec.parent_id:
            depends_on.append(spec.parent_id)

        task = Task(
            id=task_id,
            title=spec.title,
            description=spec.description,
            issue_type=spec.issue_type,
            priority=spec.priority,
            estimate=spec.estimate,
            labels=list(spec.labels),
            depends_on=depends_on,
            blocks=blocks,
            owner=spec.owner,
            created_by=spec.created_by,
        )

        if spec.parent_id:
            self._ensure_bidirectional(existing, task_id, spec.parent_id)

        self._append_record(task)

        if spec.parent_id:
            parent = existing.get(spec.parent_id)
            if parent and task_id not in parent.blocks:
                updated_parent = TaskUpdate(add_blocks=[task_id])
                updated_parent.apply(parent)
                self._append_record(parent)

        logger.info(f"Created task {task_id}: {spec.title}")
        return task

    def _ensure_bidirectional(self, tasks: dict[str, Task], task_id: str, parent_id: str) -> None:
        parent = tasks.get(parent_id)
        if parent and task_id not in parent.blocks:
            parent.blocks.append(task_id)
            self._append_record(parent)

    def get_task(self, task_id: str) -> Optional[Task]:
        tasks = self._read_all()
        return tasks.get(task_id)

    def list_tasks(
        self,
        status: str | None = None,
        issue_type: str | None = None,
        label: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        tasks = self._read_all()
        result = list(tasks.values())

        if status is not None:
            result = [t for t in result if t.status == status]
        if issue_type is not None:
            result = [t for t in result if t.issue_type == issue_type]
        if label is not None:
            result = [t for t in result if label in t.labels]

        result.sort(key=lambda t: (t.priority, t.created_at))
        return result[offset : offset + limit]

    def search_tasks(
        self,
        query: str,
        status: str | None = None,
        limit: int = 20,
    ) -> SearchResult:
        tasks = self._read_all()
        query_lower = query.lower()
        matched = []
        for task in tasks.values():
            if status is not None and task.status != status:
                continue
            searchable = f"{task.title} {task.description}".lower()
            if query_lower in searchable:
                matched.append(task)

        matched.sort(key=lambda t: (t.priority, t.created_at))
        return SearchResult(tasks=matched[:limit], total=len(matched))

    def update_task(self, task_id: str, updates: TaskUpdate) -> Task:
        tasks = self._read_all()
        task = tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)

        updates.apply(task)
        self._append_record(task)

        for dep_id in updates.add_depends_on:
            dep_task = tasks.get(dep_id)
            if dep_task and task_id not in dep_task.blocks:
                dep_task.blocks.append(task_id)
                dep_task.updated_at = task.updated_at
                self._append_record(dep_task)

        for dep_id in updates.remove_depends_on:
            dep_task = tasks.get(dep_id)
            if dep_task:
                dep_task.blocks = [b for b in dep_task.blocks if b != task_id]
                dep_task.updated_at = task.updated_at
                self._append_record(dep_task)

        for blk_id in updates.add_blocks:
            blk_task = tasks.get(blk_id)
            if blk_task and task_id not in blk_task.depends_on:
                blk_task.depends_on.append(task_id)
                blk_task.updated_at = task.updated_at
                self._append_record(blk_task)

        logger.info(f"Updated task {task_id}")
        return task

    def delete_task(self, task_id: str) -> None:
        tasks = self._read_all()
        if task_id not in tasks:
            raise TaskNotFoundError(task_id)

        del tasks[task_id]
        for task in tasks.values():
            changed = False
            if task_id in task.depends_on:
                task.depends_on = [d for d in task.depends_on if d != task_id]
                changed = True
            if task_id in task.blocks:
                task.blocks = [b for b in task.blocks if b != task_id]
                changed = True
            if changed:
                task.updated_at = task.updated_at
                self._rewrite_all(tasks)
                logger.info(f"Deleted task {task_id}")
                return

        self._rewrite_all(tasks)
        logger.info(f"Deleted task {task_id}")

    def get_ready_tasks(self) -> list[Task]:
        tasks = self._read_all()
        result = []
        for task in tasks.values():
            if task.status not in (TaskStatus.OPEN.value, TaskStatus.DRAFT.value):
                continue
            all_deps_done = True
            for dep_id in task.depends_on:
                dep = tasks.get(dep_id)
                if dep is None:
                    continue
                if dep.status not in (TaskStatus.DONE.value, TaskStatus.CLOSED.value):
                    all_deps_done = False
                    break
            if all_deps_done:
                result.append(task)

        result.sort(key=lambda t: (t.priority, t.created_at))
        return result

    def get_dependencies(self, task_id: str) -> DependencyInfo:
        tasks = self._read_all()
        task = tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)

        blocking = [tasks[dep_id] for dep_id in task.depends_on if dep_id in tasks]
        blocked_by = [tasks[blk_id] for blk_id in task.blocks if blk_id in tasks]

        return DependencyInfo(
            task_id=task_id,
            blocks=blocking,
            blocked_by=blocked_by,
        )

    def add_dependency(
        self,
        task_id: str,
        depends_on_id: str,
        dep_type: str = "blocks",
    ) -> None:
        tasks = self._read_all()
        if task_id not in tasks:
            raise TaskNotFoundError(task_id)
        if depends_on_id not in tasks:
            raise TaskNotFoundError(depends_on_id)

        if dep_type == "blocks":
            if depends_on_id not in tasks[task_id].blocks:
                tasks[task_id].blocks.append(depends_on_id)
            if task_id not in tasks[depends_on_id].depends_on:
                tasks[depends_on_id].depends_on.append(task_id)
        else:
            if depends_on_id not in tasks[task_id].depends_on:
                tasks[task_id].depends_on.append(depends_on_id)
            if task_id not in tasks[depends_on_id].blocks:
                tasks[depends_on_id].blocks.append(task_id)

        self._append_record(tasks[task_id])
        self._append_record(tasks[depends_on_id])
        logger.info(f"Added {dep_type} dependency: {task_id} -> {depends_on_id}")

    def add_label(self, task_id: str, label: str) -> None:
        task = self.get_task(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        if label not in task.labels:
            update = TaskUpdate(add_labels=[label])
            update.apply(task)
            self._append_record(task)

    def get_prime_context(self) -> str:
        tasks = self._read_all()
        open_count = sum(1 for t in tasks.values() if t.status == TaskStatus.OPEN.value)
        in_progress_count = sum(1 for t in tasks.values() if t.status == TaskStatus.IN_PROGRESS.value)
        ready = self.get_ready_tasks()

        lines = [
            f"Tasks: {open_count} open, {in_progress_count} in_progress",
        ]
        if ready:
            lines.append(f"Ready: {len(ready)} unblocked")
            for t in ready[:5]:
                priority_str = f"P{t.priority}"
                lines.append(f"  {t.id} [{priority_str}] {t.title}")
        return "\n".join(lines)

    def count_tasks(self, status: str | None = None) -> int:
        tasks = self._read_all()
        if status is None:
            return len(tasks)
        return sum(1 for t in tasks.values() if t.status == status)

    def compact(self) -> int:
        """Compact the JSONL file by removing superseded records.

        Returns:
            Number of records removed
        """
        if not self._tasks_file.exists():
            return 0

        lines = self._tasks_file.read_text(encoding="utf-8").splitlines()
        seen_ids: set[str] = set()
        kept: list[str] = []

        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                task_id = data.get("id", "")
                if task_id not in seen_ids:
                    seen_ids.add(task_id)
                    kept.append(line)
            except json.JSONDecodeError:
                kept.append(line)

        kept.reverse()
        removed = len(lines) - len(kept)
        self._rewrite_all({t.id: t for t in (Task.from_dict(json.loads(k)) for k in kept) if t.id})
        logger.info(f"Compacted task store: removed {removed} superseded records")
        return removed
