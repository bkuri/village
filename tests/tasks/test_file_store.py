import json

import pytest

from village.tasks.file_store import FileTaskStore
from village.tasks.models import (
    TaskCreate,
    TaskStatus,
    TaskType,
    TaskUpdate,
)
from village.tasks.store import TaskNotFoundError


def _make_store(tmp_path):
    tasks_file = tmp_path / "tasks.jsonl"
    return FileTaskStore(tasks_file)


def _create_task(store, **kwargs):
    spec = TaskCreate(**kwargs)
    return store.create_task(spec)


class TestReadAll:
    def test_reads_empty_file(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        result = store._read_all()
        assert result == {}

    def test_reads_nonexistent_file(self, tmp_path):
        store = _make_store(tmp_path)
        result = store._read_all()
        assert result == {}

    def test_reads_valid_tasks(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t1 = _create_task(store, title="First")
        t2 = _create_task(store, title="Second")
        tasks = store._read_all()
        assert len(tasks) == 2
        assert tasks[t1.id].title == "First"
        assert tasks[t2.id].title == "Second"

    def test_latest_version_wins_for_duplicate_ids(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Original")
        update = TaskUpdate(title="Updated")
        store.update_task(t.id, update)
        tasks = store._read_all()
        assert tasks[t.id].title == "Updated"

    def test_skips_corrupted_json_lines(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Valid")
        tasks_file = tmp_path / "tasks.jsonl"
        with open(tasks_file, "a", encoding="utf-8") as f:
            f.write("{not valid json\n")
        tasks = store._read_all()
        assert len(tasks) == 1
        assert tasks[t.id].title == "Valid"

    def test_dict_with_missing_keys_creates_empty_default_task(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Valid")
        tasks_file = tmp_path / "tasks.jsonl"
        with open(tasks_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"wrong_field": "value"}) + "\n")
        tasks = store._read_all()
        assert len(tasks) == 2
        assert tasks[t.id].title == "Valid"
        assert tasks[""].title == ""

    def test_skips_empty_lines(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="Valid")
        tasks_file = tmp_path / "tasks.jsonl"
        with open(tasks_file, "a", encoding="utf-8") as f:
            f.write("\n")
            f.write("   \n")
        tasks = store._read_all()
        assert len(tasks) == 1


class TestRewriteAll:
    def test_rewrite_preserves_tasks(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t1 = _create_task(store, title="First")
        t2 = _create_task(store, title="Second")
        tasks = store._read_all()
        store._rewrite_all(tasks)
        reloaded = store._read_all()
        assert len(reloaded) == 2
        assert reloaded[t1.id].title == "First"
        assert reloaded[t2.id].title == "Second"

    def test_rewrite_compacts_superseded_records(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Original")
        store.update_task(t.id, TaskUpdate(title="Updated"))
        store.update_task(t.id, TaskUpdate(description="More info"))
        tasks_file = tmp_path / "tasks.jsonl"
        lines = [line for line in tasks_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 3
        tasks = store._read_all()
        store._rewrite_all(tasks)
        lines_after = [line for line in tasks_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines_after) == 1
        reloaded = store._read_all()
        assert reloaded[t.id].title == "Updated"
        assert reloaded[t.id].description == "More info"

    def test_rewrite_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b" / "tasks.jsonl"
        store = FileTaskStore(nested)
        t = _create_task(store, title="Nested")
        tasks = store._read_all()
        store._rewrite_all(tasks)
        reloaded = store._read_all()
        assert reloaded[t.id].title == "Nested"


class TestCreateTask:
    def test_create_basic_task(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Test task")
        assert t.id.startswith("bd-")
        assert t.title == "Test task"
        assert t.status == TaskStatus.OPEN.value

    def test_create_with_all_fields(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(
            store,
            title="Full task",
            description="A detailed description",
            issue_type=TaskType.BUG.value,
            priority=0,
            estimate=5,
            labels=["urgent", "backend"],
            owner="alice",
        )
        assert t.issue_type == TaskType.BUG.value
        assert t.priority == 0
        assert t.estimate == 5
        assert t.labels == ["urgent", "backend"]
        assert t.owner == "alice"

    def test_create_with_parent_adds_bidirectional_link(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        parent = _create_task(store, title="Parent")
        child = _create_task(store, title="Child", parent_id=parent.id)
        parent_reloaded = store.get_task(parent.id)
        assert child.id in parent_reloaded.blocks
        assert parent.id in child.depends_on

    def test_create_with_depends_on(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        dep = _create_task(store, title="Dependency")
        t = _create_task(store, title="Dependent", depends_on=[dep.id])
        assert dep.id in t.depends_on

    def test_create_with_blocks(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Blocker", blocks=["some-id"])
        assert "some-id" in t.blocks


class TestEnsureBidirectional:
    def test_adds_child_to_parent_blocks(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        parent = _create_task(store, title="Parent")
        child = _create_task(store, title="Child")
        existing = store._read_all()
        store._ensure_bidirectional(existing, child.id, parent.id)
        parent_reloaded = store.get_task(parent.id)
        assert child.id in parent_reloaded.blocks

    def test_no_duplicate_when_already_linked(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        parent = _create_task(store, title="Parent")
        child = _create_task(store, title="Child", parent_id=parent.id)
        existing = store._read_all()
        store._ensure_bidirectional(existing, child.id, parent.id)
        parent_reloaded = store.get_task(parent.id)
        assert parent_reloaded.blocks.count(child.id) == 1

    def test_nonexistent_parent_does_nothing(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        child = _create_task(store, title="Child")
        existing = store._read_all()
        store._ensure_bidirectional(existing, child.id, "nonexistent-id")
        assert True


class TestGetTask:
    def test_get_existing_task(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Find me")
        found = store.get_task(t.id)
        assert found is not None
        assert found.title == "Find me"

    def test_get_missing_task(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        assert store.get_task("nonexistent") is None


class TestListTasks:
    def test_list_all_tasks(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="First")
        _create_task(store, title="Second")
        result = store.list_tasks()
        assert len(result) == 2

    def test_filter_by_status(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t1 = _create_task(store, title="Open")
        _create_task(store, title="Done")
        store.update_task(t1.id, TaskUpdate(status=TaskStatus.IN_PROGRESS.value))
        result = store.list_tasks(status=TaskStatus.OPEN.value)
        assert len(result) == 1

    def test_filter_by_issue_type(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="Bug", issue_type=TaskType.BUG.value)
        _create_task(store, title="Feature", issue_type=TaskType.FEATURE.value)
        result = store.list_tasks(issue_type=TaskType.BUG.value)
        assert len(result) == 1
        assert result[0].title == "Bug"

    def test_filter_by_label(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="Labeled", labels=["urgent"])
        _create_task(store, title="Other", labels=["low"])
        result = store.list_tasks(label="urgent")
        assert len(result) == 1
        assert result[0].title == "Labeled"

    def test_combined_filters(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="Urgent Bug", issue_type=TaskType.BUG.value, labels=["urgent"])
        _create_task(store, title="Low Bug", issue_type=TaskType.BUG.value, labels=["low"])
        _create_task(store, title="Urgent Feature", issue_type=TaskType.FEATURE.value, labels=["urgent"])
        result = store.list_tasks(issue_type=TaskType.BUG.value, label="urgent")
        assert len(result) == 1
        assert result[0].title == "Urgent Bug"

    def test_limit_and_offset(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        for i in range(5):
            _create_task(store, title=f"Task {i}", priority=i)
        page = store.list_tasks(limit=2, offset=1)
        assert len(page) == 2

    def test_sorted_by_priority_then_created(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        low = _create_task(store, title="Low priority", priority=3)
        high = _create_task(store, title="High priority", priority=0)
        result = store.list_tasks()
        assert result[0].id == high.id
        assert result[1].id == low.id


class TestSearchTasks:
    def test_search_by_title(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="Authentication module")
        _create_task(store, title="Database schema")
        result = store.search_tasks("auth")
        assert len(result.tasks) == 1
        assert result.tasks[0].title == "Authentication module"

    def test_search_by_description(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="Task A", description="Implements OAuth2 flow")
        _create_task(store, title="Task B", description="Adds caching layer")
        result = store.search_tasks("oauth")
        assert len(result.tasks) == 1
        assert result.tasks[0].title == "Task A"

    def test_search_case_insensitive(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="AUTH Module")
        result = store.search_tasks("auth")
        assert len(result.tasks) == 1

    def test_search_with_status_filter(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="Auth task")
        t2 = _create_task(store, title="Auth done task")
        store.update_task(t2.id, TaskUpdate(status=TaskStatus.DONE.value))
        result = store.search_tasks("auth", status=TaskStatus.DONE.value)
        assert len(result.tasks) == 1
        assert result.tasks[0].id == t2.id

    def test_search_respects_limit(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        for i in range(5):
            _create_task(store, title=f"Auth task {i}")
        result = store.search_tasks("auth", limit=2)
        assert len(result.tasks) == 2
        assert result.total == 5

    def test_search_no_match(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="Something else")
        result = store.search_tasks("nonexistent")
        assert len(result.tasks) == 0
        assert result.total == 0

    def test_search_sorted_by_priority(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        low = _create_task(store, title="Auth fix", priority=3)
        high = _create_task(store, title="Auth critical", priority=0)
        result = store.search_tasks("auth")
        assert result.tasks[0].id == high.id
        assert result.tasks[1].id == low.id


class TestUpdateTask:
    def test_update_title(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Original")
        updated = store.update_task(t.id, TaskUpdate(title="Changed"))
        assert updated.title == "Changed"
        reloaded = store.get_task(t.id)
        assert reloaded.title == "Changed"

    def test_update_status(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Task")
        updated = store.update_task(t.id, TaskUpdate(status=TaskStatus.IN_PROGRESS.value))
        assert updated.status == TaskStatus.IN_PROGRESS.value

    def test_update_nonexistent_raises(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        with pytest.raises(TaskNotFoundError):
            store.update_task("nonexistent", TaskUpdate(title="X"))

    def test_add_depends_on_adds_bidirectional(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t1 = _create_task(store, title="Task 1")
        t2 = _create_task(store, title="Task 2")
        store.update_task(t1.id, TaskUpdate(add_depends_on=[t2.id]))
        reloaded_t1 = store.get_task(t1.id)
        reloaded_t2 = store.get_task(t2.id)
        assert t2.id in reloaded_t1.depends_on
        assert t1.id in reloaded_t2.blocks

    def test_remove_depends_on_removes_bidirectional(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t1 = _create_task(store, title="Task 1")
        t2 = _create_task(store, title="Task 2")
        store.update_task(t1.id, TaskUpdate(add_depends_on=[t2.id]))
        store.update_task(t1.id, TaskUpdate(remove_depends_on=[t2.id]))
        reloaded_t1 = store.get_task(t1.id)
        reloaded_t2 = store.get_task(t2.id)
        assert t2.id not in reloaded_t1.depends_on
        assert t1.id not in reloaded_t2.blocks

    def test_add_blocks_adds_bidirectional(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t1 = _create_task(store, title="Task 1")
        t2 = _create_task(store, title="Task 2")
        store.update_task(t1.id, TaskUpdate(add_blocks=[t2.id]))
        reloaded_t1 = store.get_task(t1.id)
        reloaded_t2 = store.get_task(t2.id)
        assert t2.id in reloaded_t1.blocks
        assert t1.id in reloaded_t2.depends_on

    def test_add_labels(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Task")
        store.update_task(t.id, TaskUpdate(add_labels=["urgent", "backend"]))
        reloaded = store.get_task(t.id)
        assert "urgent" in reloaded.labels
        assert "backend" in reloaded.labels

    def test_remove_labels(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Task", labels=["urgent", "backend"])
        store.update_task(t.id, TaskUpdate(remove_labels=["urgent"]))
        reloaded = store.get_task(t.id)
        assert "urgent" not in reloaded.labels
        assert "backend" in reloaded.labels

    def test_update_priority(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Task", priority=2)
        store.update_task(t.id, TaskUpdate(priority=0))
        reloaded = store.get_task(t.id)
        assert reloaded.priority == 0

    def test_add_depends_on_nonexistent_dep_is_ignored(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Task")
        store.update_task(t.id, TaskUpdate(add_depends_on=["nonexistent"]))
        reloaded = store.get_task(t.id)
        assert "nonexistent" in reloaded.depends_on


class TestDeleteTask:
    def test_delete_existing_task(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Delete me")
        store.delete_task(t.id)
        assert store.get_task(t.id) is None

    def test_delete_nonexistent_raises(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        with pytest.raises(TaskNotFoundError):
            store.delete_task("nonexistent")

    def test_delete_cascade_removes_from_depends_on(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        dep = _create_task(store, title="Dependency")
        child = _create_task(store, title="Child", depends_on=[dep.id])
        store.delete_task(dep.id)
        reloaded_child = store.get_task(child.id)
        assert dep.id not in reloaded_child.depends_on

    def test_delete_cascade_removes_from_blocks(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        parent = _create_task(store, title="Parent")
        child = _create_task(store, title="Child", parent_id=parent.id)
        assert parent.id in child.depends_on
        store.delete_task(parent.id)
        reloaded_child = store.get_task(child.id)
        assert parent.id not in reloaded_child.depends_on

    def test_delete_rewrites_file_compactly(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t1 = _create_task(store, title="Keep")
        t2 = _create_task(store, title="Delete")
        store.update_task(t2.id, TaskUpdate(title="Updated delete"))
        store.delete_task(t2.id)
        reloaded = store._read_all()
        assert len(reloaded) == 1
        assert t1.id in reloaded


class TestGetReadyTasks:
    def test_open_task_with_no_deps_is_ready(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Ready task")
        ready = store.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == t.id

    def test_draft_task_with_no_deps_is_ready(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Draft task")
        store.update_task(t.id, TaskUpdate(status=TaskStatus.DRAFT.value))
        ready = store.get_ready_tasks()
        assert len(ready) == 1

    def test_in_progress_task_not_ready(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="In progress")
        store.update_task(t.id, TaskUpdate(status=TaskStatus.IN_PROGRESS.value))
        ready = store.get_ready_tasks()
        assert len(ready) == 0

    def test_task_with_open_dep_not_ready(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        dep = _create_task(store, title="Open dep")
        child = _create_task(store, title="Child", depends_on=[dep.id])
        ready = store.get_ready_tasks()
        ready_ids = [t.id for t in ready]
        assert child.id not in ready_ids

    def test_task_with_done_dep_is_ready(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        dep = _create_task(store, title="Done dep")
        store.update_task(dep.id, TaskUpdate(status=TaskStatus.DONE.value))
        child = _create_task(store, title="Child", depends_on=[dep.id])
        ready = store.get_ready_tasks()
        ready_ids = [t.id for t in ready]
        assert child.id in ready_ids

    def test_task_with_closed_dep_is_ready(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        dep = _create_task(store, title="Closed dep")
        store.update_task(dep.id, TaskUpdate(status=TaskStatus.CLOSED.value))
        child = _create_task(store, title="Child", depends_on=[dep.id])
        ready = store.get_ready_tasks()
        ready_ids = [t.id for t in ready]
        assert child.id in ready_ids

    def test_task_with_missing_dep_is_ready(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        child = _create_task(store, title="Child", depends_on=["nonexistent-id"])
        ready = store.get_ready_tasks()
        ready_ids = [t.id for t in ready]
        assert child.id in ready_ids

    def test_ready_tasks_sorted_by_priority(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        low = _create_task(store, title="Low", priority=3)
        high = _create_task(store, title="High", priority=0)
        ready = store.get_ready_tasks()
        assert ready[0].id == high.id
        assert ready[1].id == low.id


class TestGetDependencies:
    def test_get_dependencies_of_task(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        dep = _create_task(store, title="Dependency")
        child = _create_task(store, title="Child", depends_on=[dep.id])
        info = store.get_dependencies(child.id)
        assert info.task_id == child.id
        assert len(info.blocks) == 1
        assert info.blocks[0].id == dep.id
        assert len(info.blocked_by) == 0

    def test_get_dependencies_blocked_by(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        parent = _create_task(store, title="Parent")
        child = _create_task(store, title="Child", parent_id=parent.id)
        info = store.get_dependencies(parent.id)
        assert len(info.blocks) == 0
        assert len(info.blocked_by) == 1
        assert info.blocked_by[0].id == child.id

    def test_get_dependencies_nonexistent_raises(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        with pytest.raises(TaskNotFoundError):
            store.get_dependencies("nonexistent")

    def test_dependency_chain(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        a = _create_task(store, title="A")
        b = _create_task(store, title="B", depends_on=[a.id])
        c = _create_task(store, title="C", depends_on=[b.id])
        info_c = store.get_dependencies(c.id)
        assert len(info_c.blocks) == 1
        assert info_c.blocks[0].id == b.id
        info_b = store.get_dependencies(b.id)
        assert len(info_b.blocks) == 1
        assert info_b.blocks[0].id == a.id


class TestAddDependency:
    def test_add_blocks_dependency(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t1 = _create_task(store, title="Blocker")
        t2 = _create_task(store, title="Blocked")
        store.add_dependency(t1.id, t2.id, dep_type="blocks")
        reloaded_t1 = store.get_task(t1.id)
        reloaded_t2 = store.get_task(t2.id)
        assert t2.id in reloaded_t1.blocks
        assert t1.id in reloaded_t2.depends_on

    def test_add_depends_on_dependency(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t1 = _create_task(store, title="Dependent")
        t2 = _create_task(store, title="Depended on")
        store.add_dependency(t1.id, t2.id, dep_type="depends_on")
        reloaded_t1 = store.get_task(t1.id)
        reloaded_t2 = store.get_task(t2.id)
        assert t2.id in reloaded_t1.depends_on
        assert t1.id in reloaded_t2.blocks

    def test_add_dependency_nonexistent_task_raises(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Exists")
        with pytest.raises(TaskNotFoundError):
            store.add_dependency("nonexistent", t.id)

    def test_add_dependency_nonexistent_dep_raises(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Exists")
        with pytest.raises(TaskNotFoundError):
            store.add_dependency(t.id, "nonexistent")

    def test_add_dependency_idempotent(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t1 = _create_task(store, title="T1")
        t2 = _create_task(store, title="T2")
        store.add_dependency(t1.id, t2.id, dep_type="blocks")
        store.add_dependency(t1.id, t2.id, dep_type="blocks")
        reloaded_t1 = store.get_task(t1.id)
        assert reloaded_t1.blocks.count(t2.id) == 1


class TestAddLabel:
    def test_add_label_to_task(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Task")
        store.add_label(t.id, "urgent")
        reloaded = store.get_task(t.id)
        assert "urgent" in reloaded.labels

    def test_add_label_nonexistent_raises(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        with pytest.raises(TaskNotFoundError):
            store.add_label("nonexistent", "urgent")

    def test_add_label_idempotent(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Task", labels=["urgent"])
        store.add_label(t.id, "urgent")
        reloaded = store.get_task(t.id)
        assert reloaded.labels.count("urgent") == 1


class TestGetPrimeContext:
    def test_context_with_open_tasks(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="Open task")
        ctx = store.get_prime_context()
        assert "1 open" in ctx

    def test_context_with_in_progress_tasks(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Active")
        store.update_task(t.id, TaskUpdate(status=TaskStatus.IN_PROGRESS.value))
        ctx = store.get_prime_context()
        assert "1 in_progress" in ctx

    def test_context_shows_ready_tasks(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="Ready task", priority=0)
        ctx = store.get_prime_context()
        assert "Ready: 1 unblocked" in ctx

    def test_context_limits_ready_to_five(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        for i in range(7):
            _create_task(store, title=f"Ready {i}", priority=i)
        ctx = store.get_prime_context()
        assert "Ready: 7 unblocked" in ctx
        lines = ctx.split("\n")
        task_lines = [line for line in lines if line.startswith("  ")]
        assert len(task_lines) == 5

    def test_context_empty_store(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        ctx = store.get_prime_context()
        assert "0 open" in ctx
        assert "0 in_progress" in ctx


class TestCountTasks:
    def test_count_all(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="A")
        _create_task(store, title="B")
        _create_task(store, title="C")
        assert store.count_tasks() == 3

    def test_count_by_status(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="Open")
        t2 = _create_task(store, title="Done")
        store.update_task(t2.id, TaskUpdate(status=TaskStatus.DONE.value))
        assert store.count_tasks(status=TaskStatus.OPEN.value) == 1
        assert store.count_tasks(status=TaskStatus.DONE.value) == 1


class TestCompact:
    def test_compact_removes_superseded(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t = _create_task(store, title="Original")
        store.update_task(t.id, TaskUpdate(title="Updated"))
        store.update_task(t.id, TaskUpdate(description="Final"))
        tasks_file = tmp_path / "tasks.jsonl"
        lines_before = [line for line in tasks_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines_before) == 3
        removed = store.compact()
        assert removed == 2
        lines_after = [line for line in tasks_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines_after) == 1
        reloaded = store.get_task(t.id)
        assert reloaded.title == "Updated"
        assert reloaded.description == "Final"

    def test_compact_nonexistent_file(self, tmp_path):
        store = _make_store(tmp_path)
        removed = store.compact()
        assert removed == 0

    def test_compact_multiple_tasks(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        t1 = _create_task(store, title="T1")
        t2 = _create_task(store, title="T2")
        store.update_task(t1.id, TaskUpdate(title="T1 updated"))
        store.update_task(t2.id, TaskUpdate(title="T2 updated"))
        removed = store.compact()
        assert removed == 2
        reloaded = store._read_all()
        assert len(reloaded) == 2


class TestInitialize:
    def test_initialize_creates_file(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        assert (tmp_path / "tasks.jsonl").exists()

    def test_initialize_idempotent(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        _create_task(store, title="Task")
        store.initialize()
        reloaded = store.get_task(list(store._read_all().keys())[0])
        assert reloaded.title == "Task"


class TestIsAvailable:
    def test_available_after_init(self, tmp_path):
        store = _make_store(tmp_path)
        store.initialize()
        assert store.is_available() is True

    def test_unavailable_when_parent_missing(self, tmp_path):
        store = FileTaskStore(tmp_path / "nonexistent" / "tasks.jsonl")
        assert store.is_available() is False


class TestAppendRecord:
    def test_append_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "tasks.jsonl"
        store = FileTaskStore(nested)
        store.initialize()
        _create_task(store, title="Nested task")
        assert store.get_task(list(store._read_all().keys())[0]) is not None
