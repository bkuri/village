"""Unit tests for task extraction and Beads integration."""

from datetime import datetime

import pytest

from village.chat.baseline import BaselineReport
from village.chat.sequential_thinking import TaskBreakdown, TaskBreakdownItem
from village.chat.task_extractor import BeadsTaskSpec, extract_beads_specs


class TestBeadsTaskSpecDefaults:
    """Tests for BeadsTaskSpec default values."""

    def test_beads_task_spec_defaults(self) -> None:
        """Test creating BeadsTaskSpec with minimal required fields."""
        spec = BeadsTaskSpec(
            title="Test Task",
            description="Test description",
            estimate="2 hours",
            success_criteria=[],
            blockers=[],
            depends_on=[],
            batch_id="batch-test-123-20250101-120000",
            parent_task_id=None,
            custom_fields={},
        )

        assert spec.title == "Test Task"
        assert spec.description == "Test description"
        assert spec.estimate == "2 hours"
        assert spec.success_criteria == []
        assert spec.blockers == []
        assert spec.depends_on == []
        assert spec.batch_id == "batch-test-123-20250101-120000"
        assert spec.parent_task_id is None
        assert spec.custom_fields == {}


class TestBeadsTaskSpecPostInit:
    """Tests for BeadsTaskSpec __post_init__ method."""

    def test_post_init_defaults_depends_on(self) -> None:
        """Test that depends_on defaults to empty list if None."""
        spec = BeadsTaskSpec(
            title="Test Task",
            description="Test description",
            estimate="2 hours",
            success_criteria=[],
            blockers=[],
            depends_on=None,  # type: ignore[arg-type]
            batch_id="batch-test",
            parent_task_id=None,
            custom_fields={},
        )

        assert spec.depends_on == []

    def test_post_init_defaults_success_criteria(self) -> None:
        """Test that success_criteria defaults to empty list if None."""
        spec = BeadsTaskSpec(
            title="Test Task",
            description="Test description",
            estimate="2 hours",
            success_criteria=None,  # type: ignore[arg-type]
            blockers=[],
            depends_on=[],
            batch_id="batch-test",
            parent_task_id=None,
            custom_fields={},
        )

        assert spec.success_criteria == []

    def test_post_init_defaults_blockers(self) -> None:
        """Test that blockers defaults to empty list if None."""
        spec = BeadsTaskSpec(
            title="Test Task",
            description="Test description",
            estimate="2 hours",
            success_criteria=[],
            blockers=None,  # type: ignore[arg-type]
            depends_on=[],
            batch_id="batch-test",
            parent_task_id=None,
            custom_fields={},
        )

        assert spec.blockers == []

    def test_post_init_defaults_custom_fields(self) -> None:
        """Test that custom_fields defaults to empty dict if None."""
        spec = BeadsTaskSpec(
            title="Test Task",
            description="Test description",
            estimate="2 hours",
            success_criteria=[],
            blockers=[],
            depends_on=[],
            batch_id="batch-test",
            parent_task_id=None,
            custom_fields=None,  # type: ignore[arg-type]
        )

        assert spec.custom_fields == {}


class TestExtractBeadsSpecs:
    """Tests for extract_beads_specs function."""

    @pytest.fixture
    def mock_baseline(self) -> BaselineReport:
        """Fixture providing a mock BaselineReport."""
        return BaselineReport(
            title="Build a web application",
            reasoning="Need to break down into manageable tasks",
            parent_task_id="bd-a1b2c3d",
            tags=["frontend", "backend"],
        )

    @pytest.fixture
    def mock_breakdown(self) -> TaskBreakdown:
        """Fixture providing a mock TaskBreakdown."""
        return TaskBreakdown(
            items=[
                TaskBreakdownItem(
                    title="Set up project structure",
                    description="Initialize git repo, create directory structure",
                    estimated_effort="2 hours",
                    success_criteria=["Git repository initialized"],
                    blockers=[],
                    dependencies=[],
                    tags=["setup"],
                ),
                TaskBreakdownItem(
                    title="Implement authentication",
                    description="Add JWT authentication to API",
                    estimated_effort="1 day",
                    success_criteria=["JWT tokens generated"],
                    blockers=["Waiting for database design"],
                    dependencies=[0],
                    tags=["auth"],
                ),
            ],
            summary="Two main tasks to build a web application",
            created_at=datetime.now().isoformat(),
        )

    def test_extract_beads_specs_returns_list(
        self, mock_baseline: BaselineReport, mock_breakdown: TaskBreakdown
    ) -> None:
        """Test that extract_beads_specs returns list of BeadsTaskSpec."""
        session_id = "test-session-123"
        specs = extract_beads_specs(mock_baseline, mock_breakdown, session_id)

        assert isinstance(specs, list)
        assert len(specs) == 2
        assert all(isinstance(spec, BeadsTaskSpec) for spec in specs)

    def test_extract_beads_specs_batch_id_generated(
        self, mock_baseline: BaselineReport, mock_breakdown: TaskBreakdown
    ) -> None:
        """Test that batch_id is generated correctly."""
        session_id = "test-session-456"
        specs = extract_beads_specs(mock_baseline, mock_breakdown, session_id)

        for spec in specs:
            assert spec.batch_id.startswith(f"batch-{session_id}")

    def test_extract_beads_specs_parent_task_id_preserved(
        self, mock_baseline: BaselineReport, mock_breakdown: TaskBreakdown
    ) -> None:
        """Test that baseline.parent_task_id is preserved in specs."""
        session_id = "test-session-789"
        specs = extract_beads_specs(mock_baseline, mock_breakdown, session_id)

        for spec in specs:
            assert spec.parent_task_id == "bd-a1b2c3d"

    def test_extract_beads_specs_custom_fields_include_batch_and_source(
        self, mock_baseline: BaselineReport, mock_breakdown: TaskBreakdown
    ) -> None:
        """Test that custom fields include 'batch' and 'source' keys."""
        session_id = "test-session-abc"
        specs = extract_beads_specs(mock_baseline, mock_breakdown, session_id)

        for spec in specs:
            assert "batch" in spec.custom_fields
            assert "source" in spec.custom_fields
            assert spec.custom_fields["source"] == "village-brainstorm"
            assert spec.batch_id == spec.custom_fields["batch"]

    def test_extract_beads_specs_fields_mapped_correctly(
        self, mock_baseline: BaselineReport, mock_breakdown: TaskBreakdown
    ) -> None:
        """Test that TaskBreakdown fields are mapped correctly to BeadsTaskSpec."""
        session_id = "test-session-mapping"
        specs = extract_beads_specs(mock_baseline, mock_breakdown, session_id)

        spec1, spec2 = specs

        assert spec1.title == "Set up project structure"
        assert spec1.description == "Initialize git repo, create directory structure"
        assert spec1.estimate == "2 hours"
        assert spec1.success_criteria == ["Git repository initialized"]
        assert spec1.blockers == []
        assert "tags" in spec1.custom_fields
        assert spec1.custom_fields["tags"] == "setup"

        assert spec2.title == "Implement authentication"
        assert spec2.description == "Add JWT authentication to API"
        assert spec2.estimate == "1 day"
        assert spec2.success_criteria == ["JWT tokens generated"]
        assert spec2.blockers == ["Waiting for database design"]
        assert "tags" in spec2.custom_fields
        assert spec2.custom_fields["tags"] == "auth"

    def test_extract_beads_specs_with_no_parent_task_id(self) -> None:
        """Test extract_beads_specs when baseline has no parent_task_id."""
        baseline = BaselineReport(
            title="Test task",
            reasoning="Test reasoning",
        )

        breakdown = TaskBreakdown(
            items=[
                TaskBreakdownItem(
                    title="Task 1",
                    description="Description",
                    estimated_effort="1 hour",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[],
                    tags=[],
                ),
            ],
            summary="Summary",
            created_at=datetime.now().isoformat(),
        )

        session_id = "test-session-noparent"
        specs = extract_beads_specs(baseline, breakdown, session_id)

        assert specs[0].parent_task_id is None


class TestExtractBeadsSpecsWithDependencies:
    """Tests for extract_beads_specs with dependency handling."""

    @pytest.fixture
    def breakdown_with_dependencies(self) -> TaskBreakdown:
        """Fixture providing TaskBreakdown with dependencies."""
        return TaskBreakdown(
            items=[
                TaskBreakdownItem(
                    title="Task 1",
                    description="First task",
                    estimated_effort="1 hour",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[],
                    tags=[],
                ),
                TaskBreakdownItem(
                    title="Task 2",
                    description="Second task depends on Task 1",
                    estimated_effort="2 hours",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[0],
                    tags=[],
                ),
                TaskBreakdownItem(
                    title="Task 3",
                    description="Third task depends on both Task 1 and Task 2",
                    estimated_effort="3 hours",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[0, 1],
                    tags=[],
                ),
            ],
            summary="Three tasks with dependencies",
            created_at=datetime.now().isoformat(),
        )

    @pytest.fixture
    def baseline_simple(self) -> BaselineReport:
        """Fixture providing a simple BaselineReport."""
        return BaselineReport(
            title="Test project",
            reasoning="Test reasoning",
        )

    def test_dependencies_converted_to_task_ids(
        self, baseline_simple: BaselineReport, breakdown_with_dependencies: TaskBreakdown
    ) -> None:
        """Test that dependencies are converted to task IDs (indices → bd-xxxx format)."""
        session_id = "test-session-deps"
        specs = extract_beads_specs(baseline_simple, breakdown_with_dependencies, session_id)

        assert len(specs) == 3

        spec1, spec2, spec3 = specs

        assert spec1.depends_on == []

        assert len(spec2.depends_on) == 1
        assert spec2.depends_on[0] == "index-0"

        assert len(spec3.depends_on) == 2
        assert "index-0" in spec3.depends_on
        assert "index-1" in spec3.depends_on

    def test_empty_dependencies_handled(self, baseline_simple: BaselineReport) -> None:
        """Test that tasks with empty dependencies are handled correctly."""
        breakdown = TaskBreakdown(
            items=[
                TaskBreakdownItem(
                    title="Task with no deps",
                    description="Description",
                    estimated_effort="1 hour",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[],
                    tags=[],
                ),
            ],
            summary="Single task",
            created_at=datetime.now().isoformat(),
        )

        session_id = "test-session-nodeps"
        specs = extract_beads_specs(baseline_simple, breakdown, session_id)

        assert specs[0].depends_on == []


class TestBeadsTaskSpecRequiredFields:
    """Tests for BeadsTaskSpec required fields."""

    def test_beads_task_spec_required_fields(self) -> None:
        """Test that all required fields (title, description, estimate, etc.) are present."""
        spec = BeadsTaskSpec(
            title="Test Task",
            description="Test description",
            estimate="2 hours",
            success_criteria=["Criterion 1", "Criterion 2"],
            blockers=["Blocker 1"],
            depends_on=["bd-abc123"],
            batch_id="batch-test-123",
            parent_task_id="bd-parent",
            custom_fields={"key": "value"},
        )

        assert hasattr(spec, "title")
        assert hasattr(spec, "description")
        assert hasattr(spec, "estimate")
        assert hasattr(spec, "success_criteria")
        assert hasattr(spec, "blockers")
        assert hasattr(spec, "depends_on")
        assert hasattr(spec, "batch_id")
        assert hasattr(spec, "parent_task_id")
        assert hasattr(spec, "custom_fields")

        assert spec.title == "Test Task"
        assert spec.description == "Test description"
        assert spec.estimate == "2 hours"
        assert spec.success_criteria == ["Criterion 1", "Criterion 2"]
        assert spec.blockers == ["Blocker 1"]
        assert spec.depends_on == ["bd-abc123"]
        assert spec.batch_id == "batch-test-123"
        assert spec.parent_task_id == "bd-parent"
        assert spec.custom_fields == {"key": "value"}
