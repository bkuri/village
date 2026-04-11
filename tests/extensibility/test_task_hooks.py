"""Test TaskHooks ABC and DefaultTaskHooks."""

import pytest

from village.extensibility.task_hooks import (
    DefaultTaskHooks,
    TaskCreated,
    TaskHooks,
    TaskHookSpec,
)


class TestTaskHookSpec:
    """Test TaskHookSpec dataclass."""

    def test_task_hook_spec_initialization(self):
        """Test TaskHookSpec initialization with required fields."""
        spec = TaskHookSpec(
            title="Test Task",
            description="Test description",
            issue_type="task",
            priority=2,
        )
        assert spec.title == "Test Task"
        assert spec.description == "Test description"
        assert spec.issue_type == "task"
        assert spec.priority == 2
        assert spec.tags == []
        assert spec.parent_id is None
        assert spec.deps == []
        assert spec.metadata == {}

    def test_task_hook_spec_with_tags(self):
        """Test TaskHookSpec with tags."""
        tags = ["trading", "backtest", "crypto"]
        spec = TaskHookSpec(
            title="Test",
            description="Desc",
            issue_type="task",
            priority=1,
            tags=tags,
        )
        assert spec.tags == tags

    def test_task_hook_spec_with_parent_id(self):
        """Test TaskHookSpec with parent_id."""
        spec = TaskHookSpec(
            title="Test",
            description="Desc",
            issue_type="task",
            priority=1,
            parent_id="parent-task-id",
        )
        assert spec.parent_id == "parent-task-id"

    def test_task_hook_spec_with_deps(self):
        """Test TaskHookSpec with dependencies."""
        deps = ["dep1", "dep2", "dep3"]
        spec = TaskHookSpec(
            title="Test",
            description="Desc",
            issue_type="task",
            priority=1,
            deps=deps,
        )
        assert spec.deps == deps

    def test_task_hook_spec_with_metadata(self):
        """Test TaskHookSpec with metadata."""
        metadata = {"strategy": "aggressive", "asset": "BTC"}
        spec = TaskHookSpec(
            title="Test",
            description="Desc",
            issue_type="task",
            priority=1,
            metadata=metadata,
        )
        assert spec.metadata == metadata

    def test_task_hook_spec_all_fields(self):
        """Test TaskHookSpec with all fields."""
        tags = ["tag1", "tag2"]
        deps = ["dep1"]
        metadata = {"key": "value"}
        spec = TaskHookSpec(
            title="Full Task",
            description="Full description",
            issue_type="feature",
            priority=0,
            tags=tags,
            parent_id="parent-id",
            deps=deps,
            metadata=metadata,
        )

        assert spec.title == "Full Task"
        assert spec.description == "Full description"
        assert spec.issue_type == "feature"
        assert spec.priority == 0
        assert spec.tags == tags
        assert spec.parent_id == "parent-id"
        assert spec.deps == deps
        assert spec.metadata == metadata

    def test_task_hook_spec_none_lists_become_empty(self):
        """Test that None lists become empty via post_init."""
        spec = TaskHookSpec(
            title="Test",
            description="Desc",
            issue_type="task",
            priority=1,
            tags=None,
            deps=None,
        )
        assert spec.tags == []
        assert spec.deps == []

    def test_task_hook_spec_none_metadata_becomes_empty(self):
        """Test that None metadata becomes empty dict via post_init."""
        spec = TaskHookSpec(
            title="Test",
            description="Desc",
            issue_type="task",
            priority=1,
            metadata=None,
        )
        assert spec.metadata == {}

    def test_task_hook_spec_valid_issue_types(self):
        """Test TaskHookSpec with various issue types."""
        issue_types = ["bug", "feature", "task", "epic", "chore"]

        for issue_type in issue_types:
            spec = TaskHookSpec(
                title="Test",
                description="Desc",
                issue_type=issue_type,
                priority=1,
            )
            assert spec.issue_type == issue_type

    def test_task_hook_spec_valid_priorities(self):
        """Test TaskHookSpec with valid priorities (0-4)."""
        for priority in range(5):
            spec = TaskHookSpec(
                title="Test",
                description="Desc",
                issue_type="task",
                priority=priority,
            )
            assert spec.priority == priority

    def test_task_hook_spec_mutation(self):
        """Test that TaskHookSpec fields can be mutated."""
        spec = TaskHookSpec(
            title="Test",
            description="Desc",
            issue_type="task",
            priority=1,
        )
        spec.tags.append("new_tag")
        spec.metadata["new_key"] = "new_value"

        assert "new_tag" in spec.tags
        assert spec.metadata["new_key"] == "new_value"


class TestTaskCreated:
    """Test TaskCreated dataclass."""

    def test_task_created_initialization(self):
        """Test TaskCreated initialization with required fields."""
        created = TaskCreated(
            task_id="task-123",
            parent_id=None,
            created_at="2024-01-01T00:00:00Z",
        )
        assert created.task_id == "task-123"
        assert created.parent_id is None
        assert created.created_at == "2024-01-01T00:00:00Z"
        assert created.metadata == {}

    def test_task_created_with_parent_id(self):
        """Test TaskCreated with parent_id."""
        created = TaskCreated(
            task_id="task-456",
            parent_id="parent-task-789",
            created_at="2024-01-01T00:00:00Z",
        )
        assert created.parent_id == "parent-task-789"

    def test_task_created_with_metadata(self):
        """Test TaskCreated with metadata."""
        metadata = {"created_by": "system", "source": "village"}
        created = TaskCreated(
            task_id="task-789",
            parent_id=None,
            created_at="2024-01-01T00:00:00Z",
            metadata=metadata,
        )
        assert created.metadata == metadata

    def test_task_created_none_metadata_becomes_empty(self):
        """Test that None metadata becomes empty dict via post_init."""
        created = TaskCreated(
            task_id="task-999",
            parent_id=None,
            created_at="2024-01-01T00:00:00Z",
            metadata=None,
        )
        assert created.metadata == {}


class TestDefaultTaskHooks:
    """Test DefaultTaskHooks behavior."""

    @pytest.mark.asyncio
    async def test_should_create_task_hook_always_returns_false(self):
        """Test that should_create_task_hook always returns False."""
        hooks = DefaultTaskHooks()
        context = {"task": "info"}

        result = await hooks.should_create_task_hook(context)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_create_task_hook_with_empty_context(self):
        """Test should_create_task_hook with empty context."""
        hooks = DefaultTaskHooks()
        context = {}

        result = await hooks.should_create_task_hook(context)
        assert result is False

    @pytest.mark.asyncio
    async def test_create_hook_spec_returns_minimal_spec(self):
        """Test that create_hook_spec returns minimal spec."""
        hooks = DefaultTaskHooks()
        context = {"task_data": "value"}

        result = await hooks.create_hook_spec(context)

        assert isinstance(result, TaskHookSpec)
        assert result.title == "Task"
        assert result.description == ""
        assert result.issue_type == "task"
        assert result.priority == 2
        assert result.tags == []
        assert result.parent_id is None
        assert result.deps == []
        assert result.metadata == {}

    @pytest.mark.asyncio
    async def test_create_hook_spec_ignores_context(self):
        """Test that create_hook_spec ignores context."""
        hooks = DefaultTaskHooks()
        context = {
            "title": "Custom Title",
            "description": "Custom Description",
            "priority": 0,
        }

        result = await hooks.create_hook_spec(context)

        assert result.title == "Task"
        assert result.description == ""

    @pytest.mark.asyncio
    async def test_on_task_created_does_nothing(self):
        """Test that on_task_created does nothing."""
        hooks = DefaultTaskHooks()
        created = TaskCreated(
            task_id="task-123",
            parent_id=None,
            created_at="2024-01-01",
        )
        context = {"task": "info"}

        result = await hooks.on_task_created(created, context)
        assert result is None

    @pytest.mark.asyncio
    async def test_on_task_created_with_parent(self):
        """Test on_task_created with parent task."""
        hooks = DefaultTaskHooks()
        created = TaskCreated(
            task_id="child-task",
            parent_id="parent-task",
            created_at="2024-01-01",
        )
        context = {}

        result = await hooks.on_task_created(created, context)
        assert result is None

    @pytest.mark.asyncio
    async def test_on_task_updated_does_nothing(self):
        """Test that on_task_updated does nothing."""
        hooks = DefaultTaskHooks()
        task_id = "task-123"
        updates = {"status": "completed", "result": "success"}

        result = await hooks.on_task_updated(task_id, updates)
        assert result is None

    @pytest.mark.asyncio
    async def test_on_task_updated_with_empty_updates(self):
        """Test on_task_updated with empty updates."""
        hooks = DefaultTaskHooks()
        task_id = "task-456"
        updates = {}

        result = await hooks.on_task_updated(task_id, updates)
        assert result is None


class TestCustomTaskHooks:
    """Test custom TaskHooks implementations."""

    @pytest.mark.asyncio
    async def test_custom_hooks_conditionally_fires(self):
        """Test custom hooks that conditionally fire."""

        class ConditionalHooks(TaskHooks):
            async def should_create_task_hook(self, context: dict[str, object]) -> bool:
                return context.get("create_hook", False)

            async def create_hook_spec(self, context: dict[str, object]) -> TaskHookSpec:
                return TaskHookSpec(
                    title="Task",
                    description="",
                    issue_type="task",
                    priority=2,
                )

            async def on_task_created(self, created: TaskCreated, context: dict[str, object]) -> None:
                pass

            async def on_task_updated(self, task_id: str, updates: dict[str, object]) -> None:
                pass

        hooks = ConditionalHooks()

        assert await hooks.should_create_task_hook({}) is False
        assert await hooks.should_create_task_hook({"create_hook": False}) is False
        assert await hooks.should_create_task_hook({"create_hook": True}) is True

    @pytest.mark.asyncio
    async def test_custom_hooks_creates_detailed_spec(self):
        """Test custom hooks that creates detailed specs."""

        class DetailedHooks(TaskHooks):
            async def should_create_task_hook(self, context: dict[str, object]) -> bool:
                return True

            async def create_hook_spec(self, context: dict[str, object]) -> TaskHookSpec:
                return TaskHookSpec(
                    title=context.get("title", "Task"),
                    description=context.get("description", ""),
                    issue_type=context.get("issue_type", "task"),
                    priority=context.get("priority", 2),
                    tags=context.get("tags", []),
                    parent_id=context.get("parent_id"),
                    deps=context.get("deps", []),
                    metadata=context.get("metadata", {}),
                )

            async def on_task_created(self, created: TaskCreated, context: dict[str, object]) -> None:
                pass

            async def on_task_updated(self, task_id: str, updates: dict[str, object]) -> None:
                pass

        hooks = DetailedHooks()
        context = {
            "title": "Backtest Analysis",
            "description": "Analyze recent backtest results",
            "issue_type": "task",
            "priority": 1,
            "tags": ["trading", "analysis"],
            "deps": ["task-1"],
            "metadata": {"strategy": "aggressive"},
        }

        spec = await hooks.create_hook_spec(context)

        assert spec.title == "Backtest Analysis"
        assert spec.description == "Analyze recent backtest results"
        assert spec.issue_type == "task"
        assert spec.priority == 1
        assert spec.tags == ["trading", "analysis"]
        assert spec.deps == ["task-1"]
        assert spec.metadata == {"strategy": "aggressive"}

    @pytest.mark.asyncio
    async def test_custom_hooks_tracks_tasks(self):
        """Test custom hooks that tracks created tasks."""

        class TrackingHooks(TaskHooks):
            def __init__(self):
                self.created_tasks = []
                self.updated_tasks = []

            async def should_create_task_hook(self, context: dict[str, object]) -> bool:
                return True

            async def create_hook_spec(self, context: dict[str, object]) -> TaskHookSpec:
                return TaskHookSpec(
                    title="Task",
                    description="",
                    issue_type="task",
                    priority=2,
                )

            async def on_task_created(self, created: TaskCreated, context: dict[str, object]) -> None:
                self.created_tasks.append(created)

            async def on_task_updated(self, task_id: str, updates: dict[str, object]) -> None:
                self.updated_tasks.append((task_id, updates))

        hooks = TrackingHooks()
        created = TaskCreated(
            task_id="task-1",
            parent_id=None,
            created_at="2024-01-01",
        )
        context = {}

        await hooks.on_task_created(created, context)
        await hooks.on_task_updated("task-1", {"status": "done"})

        assert len(hooks.created_tasks) == 1
        assert hooks.created_tasks[0].task_id == "task-1"
        assert len(hooks.updated_tasks) == 1
        assert hooks.updated_tasks[0] == ("task-1", {"status": "done"})

    @pytest.mark.asyncio
    async def test_custom_hooks_with_workflow(self):
        """Test custom hooks with full workflow."""

        class WorkflowHooks(TaskHooks):
            def __init__(self):
                self.state = {}

            async def should_create_task_hook(self, context: dict[str, object]) -> bool:
                return "title" in context

            async def create_hook_spec(self, context: dict[str, object]) -> TaskHookSpec:
                return TaskHookSpec(
                    title=context.get("title", "Task"),
                    description=context.get("description", ""),
                    issue_type=context.get("issue_type", "task"),
                    priority=context.get("priority", 2),
                )

            async def on_task_created(self, created: TaskCreated, context: dict[str, object]) -> None:
                self.state[created.task_id] = {
                    "status": "created",
                    "context": context,
                }

            async def on_task_updated(self, task_id: str, updates: dict[str, object]) -> None:
                if task_id in self.state:
                    self.state[task_id].update(updates)

        hooks = WorkflowHooks()
        context = {"title": "Test Task", "description": "Test"}

        assert await hooks.should_create_task_hook(context)

        spec = await hooks.create_hook_spec(context)
        assert spec.title == "Test Task"

        created = TaskCreated(
            task_id="test-task-1",
            parent_id=None,
            created_at="2024-01-01",
        )
        await hooks.on_task_created(created, context)

        assert "test-task-1" in hooks.state
        assert hooks.state["test-task-1"]["status"] == "created"

        await hooks.on_task_updated("test-task-1", {"status": "completed"})
        assert hooks.state["test-task-1"]["status"] == "completed"


class TestTaskHooksABC:
    """Test that TaskHooks ABC cannot be instantiated directly."""

    def test_task_hooks_cannot_be_instantiated(self):
        """Test that abstract TaskHooks cannot be instantiated."""
        with pytest.raises(TypeError):
            TaskHooks()

    def test_custom_hooks_must_implement_all_methods(self):
        """Test that custom hooks must implement all abstract methods."""

        class IncompleteHooks(TaskHooks):
            async def should_create_task_hook(self, context: dict[str, object]) -> bool:
                return True

            async def create_hook_spec(self, context: dict[str, object]) -> TaskHookSpec:
                return TaskHookSpec(
                    title="Task",
                    description="",
                    issue_type="task",
                    priority=2,
                )

            async def on_task_created(self, created: TaskCreated, context: dict[str, object]) -> None:
                pass

        with pytest.raises(TypeError):
            IncompleteHooks()
