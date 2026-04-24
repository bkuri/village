from village.tasks.models import (
    Task,
    TaskDependency,
    TaskStatus,
    TaskType,
    TaskUpdate,
)


def _make_task(**overrides) -> Task:
    defaults = {
        "id": "bd-a3f8",
        "title": "Test Task",
        "status": "open",
        "priority": 2,
        "issue_type": "task",
        "description": "desc",
        "estimate": 0,
        "labels": [],
        "depends_on": [],
        "blocks": [],
        "owner": "",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "closed_at": "",
        "closed_reason": "",
        "created_by": "",
    }
    defaults.update(overrides)
    return Task(**defaults)


class TestTaskDependency:
    def test_post_init_sets_created_at(self):
        dep = TaskDependency(task_id="bd-a1", depends_on_id="bd-a2", dep_type="blocks")
        assert dep.created_at != ""

    def test_post_init_preserves_existing_created_at(self):
        dep = TaskDependency(
            task_id="bd-a1",
            depends_on_id="bd-a2",
            dep_type="blocks",
            created_at="2025-01-01T00:00:00+00:00",
        )
        assert dep.created_at == "2025-01-01T00:00:00+00:00"


class TestTaskPostInit:
    def test_post_init_sets_timestamps(self):
        task = Task(id="bd-new", title="New Task")
        assert task.created_at != ""
        assert task.updated_at != ""

    def test_post_init_preserves_existing_timestamps(self):
        task = Task(
            id="bd-new",
            title="New Task",
            created_at="2025-01-01T00:00:00+00:00",
            updated_at="2025-01-01T00:00:00+00:00",
        )
        assert task.created_at == "2025-01-01T00:00:00+00:00"
        assert task.updated_at == "2025-01-01T00:00:00+00:00"


class TestTaskToDict:
    def test_roundtrip(self):
        task = _make_task(labels=["bug"], depends_on=["bd-001"])
        d = task.to_dict()
        assert d["id"] == "bd-a3f8"
        assert d["labels"] == ["bug"]
        assert d["depends_on"] == ["bd-001"]


class TestTaskFromDict:
    def test_full_dict(self):
        data = {
            "id": "bd-x1",
            "title": "X",
            "status": "done",
            "priority": 1,
            "issue_type": "bug",
            "description": "d",
            "estimate": 5,
            "labels": ["urgent"],
            "depends_on": ["bd-y"],
            "blocks": ["bd-z"],
            "owner": "alice",
            "created_at": "2025-06-01T00:00:00+00:00",
            "updated_at": "2025-06-01T00:00:00+00:00",
            "closed_at": "2025-06-02T00:00:00+00:00",
            "closed_reason": "completed",
            "created_by": "bob",
        }
        task = Task.from_dict(data)
        assert task.id == "bd-x1"
        assert task.title == "X"
        assert task.status == "done"
        assert task.priority == 1
        assert task.issue_type == "bug"
        assert task.description == "d"
        assert task.estimate == 5
        assert task.labels == ["urgent"]
        assert task.depends_on == ["bd-y"]
        assert task.blocks == ["bd-z"]
        assert task.owner == "alice"
        assert task.closed_at == "2025-06-02T00:00:00+00:00"
        assert task.closed_reason == "completed"
        assert task.created_by == "bob"

    def test_empty_dict_uses_defaults(self):
        task = Task.from_dict({})
        assert task.id == ""
        assert task.title == ""
        assert task.status == TaskStatus.OPEN.value
        assert task.priority == 2
        assert task.issue_type == TaskType.TASK.value
        assert task.description == ""
        assert task.estimate == 0
        assert task.labels == []
        assert task.depends_on == []
        assert task.blocks == []
        assert task.owner == ""

    def test_partial_dict(self):
        task = Task.from_dict({"id": "bd-p1", "title": "Partial"})
        assert task.id == "bd-p1"
        assert task.title == "Partial"
        assert task.status == TaskStatus.OPEN.value


class TestTaskUpdateHasChanges:
    def test_no_changes(self):
        assert TaskUpdate().has_changes() is False

    def test_title_change(self):
        assert TaskUpdate(title="new").has_changes() is True

    def test_description_change(self):
        assert TaskUpdate(description="new").has_changes() is True

    def test_status_change(self):
        assert TaskUpdate(status="done").has_changes() is True

    def test_priority_change(self):
        assert TaskUpdate(priority=1).has_changes() is True

    def test_issue_type_change(self):
        assert TaskUpdate(issue_type="bug").has_changes() is True

    def test_estimate_change(self):
        assert TaskUpdate(estimate=5).has_changes() is True

    def test_add_labels(self):
        assert TaskUpdate(add_labels=["x"]).has_changes() is True

    def test_remove_labels(self):
        assert TaskUpdate(remove_labels=["x"]).has_changes() is True

    def test_add_depends_on(self):
        assert TaskUpdate(add_depends_on=["bd-x"]).has_changes() is True

    def test_add_blocks(self):
        assert TaskUpdate(add_blocks=["bd-x"]).has_changes() is True

    def test_remove_depends_on(self):
        assert TaskUpdate(remove_depends_on=["bd-x"]).has_changes() is True

    def test_remove_blocks(self):
        assert TaskUpdate(remove_blocks=["bd-x"]).has_changes() is True

    def test_closed_reason_change(self):
        assert TaskUpdate(closed_reason="done").has_changes() is True

    def test_owner_change(self):
        assert TaskUpdate(owner="alice").has_changes() is True


class TestTaskUpdateApply:
    def test_apply_title(self):
        task = _make_task()
        result = TaskUpdate(title="New Title").apply(task)
        assert result.title == "New Title"

    def test_apply_description(self):
        task = _make_task()
        result = TaskUpdate(description="New desc").apply(task)
        assert result.description == "New desc"

    def test_apply_status(self):
        task = _make_task()
        result = TaskUpdate(status="in_progress").apply(task)
        assert result.status == "in_progress"

    def test_apply_priority(self):
        task = _make_task()
        result = TaskUpdate(priority=0).apply(task)
        assert result.priority == 0

    def test_apply_issue_type(self):
        task = _make_task()
        result = TaskUpdate(issue_type="bug").apply(task)
        assert result.issue_type == "bug"

    def test_apply_estimate(self):
        task = _make_task()
        result = TaskUpdate(estimate=10).apply(task)
        assert result.estimate == 10

    def test_apply_owner(self):
        task = _make_task()
        result = TaskUpdate(owner="alice").apply(task)
        assert result.owner == "alice"

    def test_apply_closed_reason(self):
        task = _make_task()
        result = TaskUpdate(closed_reason="completed").apply(task)
        assert result.closed_reason == "completed"

    def test_add_labels_new(self):
        task = _make_task(labels=["bug"])
        result = TaskUpdate(add_labels=["urgent"]).apply(task)
        assert "urgent" in result.labels
        assert "bug" in result.labels

    def test_add_labels_no_duplicate(self):
        task = _make_task(labels=["bug"])
        result = TaskUpdate(add_labels=["bug"]).apply(task)
        assert result.labels == ["bug"]

    def test_remove_labels(self):
        task = _make_task(labels=["bug", "urgent"])
        result = TaskUpdate(remove_labels=["bug"]).apply(task)
        assert result.labels == ["urgent"]

    def test_remove_labels_not_present(self):
        task = _make_task(labels=["bug"])
        result = TaskUpdate(remove_labels=["missing"]).apply(task)
        assert result.labels == ["bug"]

    def test_add_depends_on_new(self):
        task = _make_task(depends_on=["bd-001"])
        result = TaskUpdate(add_depends_on=["bd-002"]).apply(task)
        assert "bd-002" in result.depends_on
        assert "bd-001" in result.depends_on

    def test_add_depends_on_no_duplicate(self):
        task = _make_task(depends_on=["bd-001"])
        result = TaskUpdate(add_depends_on=["bd-001"]).apply(task)
        assert result.depends_on == ["bd-001"]

    def test_remove_depends_on(self):
        task = _make_task(depends_on=["bd-001", "bd-002"])
        result = TaskUpdate(remove_depends_on=["bd-001"]).apply(task)
        assert result.depends_on == ["bd-002"]

    def test_add_blocks_new(self):
        task = _make_task(blocks=["bd-001"])
        result = TaskUpdate(add_blocks=["bd-002"]).apply(task)
        assert "bd-002" in result.blocks

    def test_add_blocks_no_duplicate(self):
        task = _make_task(blocks=["bd-001"])
        result = TaskUpdate(add_blocks=["bd-001"]).apply(task)
        assert result.blocks == ["bd-001"]

    def test_remove_blocks(self):
        task = _make_task(blocks=["bd-001", "bd-002"])
        result = TaskUpdate(remove_blocks=["bd-001"]).apply(task)
        assert result.blocks == ["bd-002"]

    def test_auto_close_timestamp_on_done(self):
        task = _make_task(status="open", closed_at="")
        result = TaskUpdate(status="done").apply(task)
        assert result.closed_at != ""
        assert result.status == "done"

    def test_auto_close_timestamp_on_closed(self):
        task = _make_task(status="open", closed_at="")
        result = TaskUpdate(status="closed").apply(task)
        assert result.closed_at != ""
        assert result.status == "closed"

    def test_no_auto_close_when_not_terminal_status(self):
        task = _make_task(status="open", closed_at="")
        result = TaskUpdate(status="in_progress").apply(task)
        assert result.closed_at == ""

    def test_no_auto_close_when_already_closed(self):
        task = _make_task(status="open", closed_at="2025-01-01T00:00:00+00:00")
        result = TaskUpdate(status="done").apply(task)
        assert result.closed_at == "2025-01-01T00:00:00+00:00"

    def test_updated_at_always_set(self):
        task = _make_task(updated_at="2025-01-01T00:00:00+00:00")
        result = TaskUpdate(title="x").apply(task)
        assert result.updated_at != "2025-01-01T00:00:00+00:00"

    def test_apply_multiple_fields(self):
        task = _make_task(labels=["old"])
        update = TaskUpdate(
            title="New",
            status="done",
            priority=0,
            add_labels=["new"],
            remove_labels=["old"],
        )
        result = update.apply(task)
        assert result.title == "New"
        assert result.status == "done"
        assert result.priority == 0
        assert "new" in result.labels
        assert "old" not in result.labels

    def test_returns_same_task_object(self):
        task = _make_task()
        result = TaskUpdate(title="x").apply(task)
        assert result is task


class TestDependencyInfo:
    def test_defaults(self):
        from village.tasks.models import DependencyInfo

        info = DependencyInfo(task_id="bd-a1")
        assert info.blocks == []
        assert info.blocked_by == []


class TestSearchResult:
    def test_defaults(self):
        from village.tasks.models import SearchResult

        result = SearchResult(tasks=[], total=0)
        assert result.total == 0
        assert result.tasks == []
