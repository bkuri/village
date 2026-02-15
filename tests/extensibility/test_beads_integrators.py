"""Test BeadsIntegrator ABC and DefaultBeadsIntegrator."""

import pytest

from village.extensibility.beads_integrators import (
    BeadCreated,
    BeadsIntegrator,
    BeadSpec,
    DefaultBeadsIntegrator,
)


class TestBeadSpec:
    """Test BeadSpec dataclass."""

    def test_bead_spec_initialization(self):
        """Test BeadSpec initialization with required fields."""
        spec = BeadSpec(
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

    def test_bead_spec_with_tags(self):
        """Test BeadSpec with tags."""
        tags = ["trading", "backtest", "crypto"]
        spec = BeadSpec(
            title="Test",
            description="Desc",
            issue_type="task",
            priority=1,
            tags=tags,
        )
        assert spec.tags == tags

    def test_bead_spec_with_parent_id(self):
        """Test BeadSpec with parent_id."""
        spec = BeadSpec(
            title="Test",
            description="Desc",
            issue_type="task",
            priority=1,
            parent_id="parent-bead-id",
        )
        assert spec.parent_id == "parent-bead-id"

    def test_bead_spec_with_deps(self):
        """Test BeadSpec with dependencies."""
        deps = ["dep1", "dep2", "dep3"]
        spec = BeadSpec(
            title="Test",
            description="Desc",
            issue_type="task",
            priority=1,
            deps=deps,
        )
        assert spec.deps == deps

    def test_bead_spec_with_metadata(self):
        """Test BeadSpec with metadata."""
        metadata = {"strategy": "aggressive", "asset": "BTC"}
        spec = BeadSpec(
            title="Test",
            description="Desc",
            issue_type="task",
            priority=1,
            metadata=metadata,
        )
        assert spec.metadata == metadata

    def test_bead_spec_all_fields(self):
        """Test BeadSpec with all fields."""
        tags = ["tag1", "tag2"]
        deps = ["dep1"]
        metadata = {"key": "value"}
        spec = BeadSpec(
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

    def test_bead_spec_none_lists_become_empty(self):
        """Test that None lists become empty via post_init."""
        spec = BeadSpec(
            title="Test",
            description="Desc",
            issue_type="task",
            priority=1,
            tags=None,
            deps=None,
        )
        assert spec.tags == []
        assert spec.deps == []

    def test_bead_spec_none_metadata_becomes_empty(self):
        """Test that None metadata becomes empty dict via post_init."""
        spec = BeadSpec(
            title="Test",
            description="Desc",
            issue_type="task",
            priority=1,
            metadata=None,
        )
        assert spec.metadata == {}

    def test_bead_spec_valid_issue_types(self):
        """Test BeadSpec with various issue types."""
        issue_types = ["bug", "feature", "task", "epic", "chore"]

        for issue_type in issue_types:
            spec = BeadSpec(
                title="Test",
                description="Desc",
                issue_type=issue_type,
                priority=1,
            )
            assert spec.issue_type == issue_type

    def test_bead_spec_valid_priorities(self):
        """Test BeadSpec with valid priorities (0-4)."""
        for priority in range(5):
            spec = BeadSpec(
                title="Test",
                description="Desc",
                issue_type="task",
                priority=priority,
            )
            assert spec.priority == priority

    def test_bead_spec_mutation(self):
        """Test that BeadSpec fields can be mutated."""
        spec = BeadSpec(
            title="Test",
            description="Desc",
            issue_type="task",
            priority=1,
        )
        spec.tags.append("new_tag")
        spec.metadata["new_key"] = "new_value"

        assert "new_tag" in spec.tags
        assert spec.metadata["new_key"] == "new_value"


class TestBeadCreated:
    """Test BeadCreated dataclass."""

    def test_bead_created_initialization(self):
        """Test BeadCreated initialization with required fields."""
        bead = BeadCreated(
            bead_id="bead-123",
            parent_id=None,
            created_at="2024-01-01T00:00:00Z",
        )
        assert bead.bead_id == "bead-123"
        assert bead.parent_id is None
        assert bead.created_at == "2024-01-01T00:00:00Z"
        assert bead.metadata == {}

    def test_bead_created_with_parent_id(self):
        """Test BeadCreated with parent_id."""
        bead = BeadCreated(
            bead_id="bead-456",
            parent_id="parent-bead-789",
            created_at="2024-01-01T00:00:00Z",
        )
        assert bead.parent_id == "parent-bead-789"

    def test_bead_created_with_metadata(self):
        """Test BeadCreated with metadata."""
        metadata = {"created_by": "system", "source": "village"}
        bead = BeadCreated(
            bead_id="bead-789",
            parent_id=None,
            created_at="2024-01-01T00:00:00Z",
            metadata=metadata,
        )
        assert bead.metadata == metadata

    def test_bead_created_none_metadata_becomes_empty(self):
        """Test that None metadata becomes empty dict via post_init."""
        bead = BeadCreated(
            bead_id="bead-999",
            parent_id=None,
            created_at="2024-01-01T00:00:00Z",
            metadata=None,
        )
        assert bead.metadata == {}


class TestDefaultBeadsIntegrator:
    """Test DefaultBeadsIntegrator behavior."""

    @pytest.mark.asyncio
    async def test_should_create_bead_always_returns_false(self):
        """Test that should_create_bead always returns False."""
        integrator = DefaultBeadsIntegrator()
        context = {"task": "info"}

        result = await integrator.should_create_bead(context)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_create_bead_with_empty_context(self):
        """Test should_create_bead with empty context."""
        integrator = DefaultBeadsIntegrator()
        context = {}

        result = await integrator.should_create_bead(context)
        assert result is False

    @pytest.mark.asyncio
    async def test_create_bead_spec_returns_minimal_spec(self):
        """Test that create_bead_spec returns minimal spec."""
        integrator = DefaultBeadsIntegrator()
        context = {"task_data": "value"}

        result = await integrator.create_bead_spec(context)

        assert isinstance(result, BeadSpec)
        assert result.title == "Task"
        assert result.description == ""
        assert result.issue_type == "task"
        assert result.priority == 2
        assert result.tags == []
        assert result.parent_id is None
        assert result.deps == []
        assert result.metadata == {}

    @pytest.mark.asyncio
    async def test_create_bead_spec_ignores_context(self):
        """Test that create_bead_spec ignores context."""
        integrator = DefaultBeadsIntegrator()
        context = {
            "title": "Custom Title",
            "description": "Custom Description",
            "priority": 0,
        }

        result = await integrator.create_bead_spec(context)

        assert result.title == "Task"
        assert result.description == ""

    @pytest.mark.asyncio
    async def test_on_bead_created_does_nothing(self):
        """Test that on_bead_created does nothing."""
        integrator = DefaultBeadsIntegrator()
        bead = BeadCreated(
            bead_id="bead-123",
            parent_id=None,
            created_at="2024-01-01",
        )
        context = {"task": "info"}

        result = await integrator.on_bead_created(bead, context)
        assert result is None

    @pytest.mark.asyncio
    async def test_on_bead_created_with_parent(self):
        """Test on_bead_created with parent bead."""
        integrator = DefaultBeadsIntegrator()
        bead = BeadCreated(
            bead_id="child-bead",
            parent_id="parent-bead",
            created_at="2024-01-01",
        )
        context = {}

        result = await integrator.on_bead_created(bead, context)
        assert result is None

    @pytest.mark.asyncio
    async def test_on_bead_updated_does_nothing(self):
        """Test that on_bead_updated does nothing."""
        integrator = DefaultBeadsIntegrator()
        bead_id = "bead-123"
        updates = {"status": "completed", "result": "success"}

        result = await integrator.on_bead_updated(bead_id, updates)
        assert result is None

    @pytest.mark.asyncio
    async def test_on_bead_updated_with_empty_updates(self):
        """Test on_bead_updated with empty updates."""
        integrator = DefaultBeadsIntegrator()
        bead_id = "bead-456"
        updates = {}

        result = await integrator.on_bead_updated(bead_id, updates)
        assert result is None


class TestCustomBeadsIntegrator:
    """Test custom BeadsIntegrator implementations."""

    @pytest.mark.asyncio
    async def test_custom_integrator_conditionally_creates_bead(self):
        """Test custom integrator that conditionally creates beads."""

        class ConditionalIntegrator(BeadsIntegrator):
            async def should_create_bead(self, context: dict[str, object]) -> bool:
                return context.get("create_bead", False)

            async def create_bead_spec(self, context: dict[str, object]) -> BeadSpec:
                return BeadSpec(
                    title="Task",
                    description="",
                    issue_type="task",
                    priority=2,
                )

            async def on_bead_created(self, bead: BeadCreated, context: dict[str, object]) -> None:
                pass

            async def on_bead_updated(self, bead_id: str, updates: dict[str, object]) -> None:
                pass

        integrator = ConditionalIntegrator()

        assert await integrator.should_create_bead({}) is False
        assert await integrator.should_create_bead({"create_bead": False}) is False
        assert await integrator.should_create_bead({"create_bead": True}) is True

    @pytest.mark.asyncio
    async def test_custom_integrator_creates_detailed_spec(self):
        """Test custom integrator that creates detailed bead specs."""

        class DetailedIntegrator(BeadsIntegrator):
            async def should_create_bead(self, context: dict[str, object]) -> bool:
                return True

            async def create_bead_spec(self, context: dict[str, object]) -> BeadSpec:
                return BeadSpec(
                    title=context.get("title", "Task"),
                    description=context.get("description", ""),
                    issue_type=context.get("issue_type", "task"),
                    priority=context.get("priority", 2),
                    tags=context.get("tags", []),
                    parent_id=context.get("parent_id"),
                    deps=context.get("deps", []),
                    metadata=context.get("metadata", {}),
                )

            async def on_bead_created(self, bead: BeadCreated, context: dict[str, object]) -> None:
                pass

            async def on_bead_updated(self, bead_id: str, updates: dict[str, object]) -> None:
                pass

        integrator = DetailedIntegrator()
        context = {
            "title": "Backtest Analysis",
            "description": "Analyze recent backtest results",
            "issue_type": "task",
            "priority": 1,
            "tags": ["trading", "analysis"],
            "deps": ["bead-1"],
            "metadata": {"strategy": "aggressive"},
        }

        spec = await integrator.create_bead_spec(context)

        assert spec.title == "Backtest Analysis"
        assert spec.description == "Analyze recent backtest results"
        assert spec.issue_type == "task"
        assert spec.priority == 1
        assert spec.tags == ["trading", "analysis"]
        assert spec.deps == ["bead-1"]
        assert spec.metadata == {"strategy": "aggressive"}

    @pytest.mark.asyncio
    async def test_custom_integrator_tracks_beads(self):
        """Test custom integrator that tracks created beads."""

        class TrackingIntegrator(BeadsIntegrator):
            def __init__(self):
                self.created_beads = []
                self.updated_beads = []

            async def should_create_bead(self, context: dict[str, object]) -> bool:
                return True

            async def create_bead_spec(self, context: dict[str, object]) -> BeadSpec:
                return BeadSpec(
                    title="Task",
                    description="",
                    issue_type="task",
                    priority=2,
                )

            async def on_bead_created(self, bead: BeadCreated, context: dict[str, object]) -> None:
                self.created_beads.append(bead)

            async def on_bead_updated(self, bead_id: str, updates: dict[str, object]) -> None:
                self.updated_beads.append((bead_id, updates))

        integrator = TrackingIntegrator()
        bead = BeadCreated(
            bead_id="bead-1",
            parent_id=None,
            created_at="2024-01-01",
        )
        context = {}

        await integrator.on_bead_created(bead, context)
        await integrator.on_bead_updated("bead-1", {"status": "done"})

        assert len(integrator.created_beads) == 1
        assert integrator.created_beads[0].bead_id == "bead-1"
        assert len(integrator.updated_beads) == 1
        assert integrator.updated_beads[0] == ("bead-1", {"status": "done"})

    @pytest.mark.asyncio
    async def test_custom_integrator_with_workflow(self):
        """Test custom integrator with full workflow."""

        class WorkflowIntegrator(BeadsIntegrator):
            def __init__(self):
                self.state = {}

            async def should_create_bead(self, context: dict[str, object]) -> bool:
                return "title" in context

            async def create_bead_spec(self, context: dict[str, object]) -> BeadSpec:
                return BeadSpec(
                    title=context.get("title", "Task"),
                    description=context.get("description", ""),
                    issue_type=context.get("issue_type", "task"),
                    priority=context.get("priority", 2),
                )

            async def on_bead_created(self, bead: BeadCreated, context: dict[str, object]) -> None:
                self.state[bead.bead_id] = {
                    "status": "created",
                    "context": context,
                }

            async def on_bead_updated(self, bead_id: str, updates: dict[str, object]) -> None:
                if bead_id in self.state:
                    self.state[bead_id].update(updates)

        integrator = WorkflowIntegrator()
        context = {"title": "Test Task", "description": "Test"}

        assert await integrator.should_create_bead(context)

        spec = await integrator.create_bead_spec(context)
        assert spec.title == "Test Task"

        bead = BeadCreated(
            bead_id="test-bead-1",
            parent_id=None,
            created_at="2024-01-01",
        )
        await integrator.on_bead_created(bead, context)

        assert "test-bead-1" in integrator.state
        assert integrator.state["test-bead-1"]["status"] == "created"

        await integrator.on_bead_updated("test-bead-1", {"status": "completed"})
        assert integrator.state["test-bead-1"]["status"] == "completed"


class TestBeadsIntegratorABC:
    """Test that BeadsIntegrator ABC cannot be instantiated directly."""

    def test_beads_integrator_cannot_be_instantiated(self):
        """Test that abstract BeadsIntegrator cannot be instantiated."""
        with pytest.raises(TypeError):
            BeadsIntegrator()

    def test_custom_integrator_must_implement_all_methods(self):
        """Test that custom integrator must implement all abstract methods."""

        class IncompleteIntegrator(BeadsIntegrator):
            async def should_create_bead(self, context: dict[str, object]) -> bool:
                return True

            async def create_bead_spec(self, context: dict[str, object]) -> BeadSpec:
                return BeadSpec(
                    title="Task",
                    description="",
                    issue_type="task",
                    priority=2,
                )

            async def on_bead_created(self, bead: BeadCreated, context: dict[str, object]) -> None:
                pass

        with pytest.raises(TypeError):
            IncompleteIntegrator()
