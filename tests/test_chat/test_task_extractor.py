"""Unit tests for task extraction and Beads integration."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from village.chat.baseline import BaselineReport
from village.chat.sequential_thinking import TaskBreakdown, TaskBreakdownItem
from village.chat.task_extractor import TaskSubmissionSpec, extract_task_specs


class TestExtractBeadsSpecs:
    """Tests for extract_task_specs function."""

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

    def test_extract_task_specs_returns_list(
        self, mock_baseline: BaselineReport, mock_breakdown: TaskBreakdown
    ) -> None:
        """Test that extract_task_specs returns list of TaskSubmissionSpec."""
        session_id = "test-session-123"
        specs = extract_task_specs(mock_baseline, mock_breakdown, session_id)

        assert isinstance(specs, list)
        assert len(specs) == 2
        assert all(isinstance(spec, TaskSubmissionSpec) for spec in specs)

    def test_extract_task_specs_batch_id_generated(
        self, mock_baseline: BaselineReport, mock_breakdown: TaskBreakdown
    ) -> None:
        """Test that batch_id is generated correctly."""
        session_id = "test-session-456"
        specs = extract_task_specs(mock_baseline, mock_breakdown, session_id)

        for spec in specs:
            assert spec.batch_id.startswith(f"batch-{session_id}")

    def test_extract_task_specs_parent_task_id_preserved(
        self, mock_baseline: BaselineReport, mock_breakdown: TaskBreakdown
    ) -> None:
        """Test that baseline.parent_task_id is preserved in specs."""
        session_id = "test-session-789"
        specs = extract_task_specs(mock_baseline, mock_breakdown, session_id)

        for spec in specs:
            assert spec.parent_task_id == "bd-a1b2c3d"

    def test_extract_task_specs_custom_fields_include_batch_and_source(
        self, mock_baseline: BaselineReport, mock_breakdown: TaskBreakdown
    ) -> None:
        """Test that custom fields include 'batch' and 'source' keys."""
        session_id = "test-session-abc"
        specs = extract_task_specs(mock_baseline, mock_breakdown, session_id)

        for spec in specs:
            assert "batch" in spec.custom_fields
            assert "source" in spec.custom_fields
            assert spec.custom_fields["source"] == "village-brainstorm"
            assert spec.batch_id == spec.custom_fields["batch"]

    def test_extract_task_specs_fields_mapped_correctly(
        self, mock_baseline: BaselineReport, mock_breakdown: TaskBreakdown
    ) -> None:
        """Test that TaskBreakdown fields are mapped correctly to TaskSubmissionSpec."""
        session_id = "test-session-mapping"
        specs = extract_task_specs(mock_baseline, mock_breakdown, session_id)

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

    def test_extract_task_specs_with_no_parent_task_id(self) -> None:
        """Test extract_task_specs when baseline has no parent_task_id."""
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
        specs = extract_task_specs(baseline, breakdown, session_id)

        assert specs[0].parent_task_id is None


class TestExtractBeadsSpecsWithDependencies:
    """Tests for extract_task_specs with dependency handling."""

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
        specs = extract_task_specs(baseline_simple, breakdown_with_dependencies, session_id)

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
        specs = extract_task_specs(baseline_simple, breakdown, session_id)

        assert specs[0].depends_on == []


class TestTaskSubmissionSpecDefaults:
    def test_post_init_defaults_none_to_empty(self) -> None:
        spec = TaskSubmissionSpec(
            title="Test",
            description="Desc",
            estimate="1h",
            success_criteria=None,
            blockers=None,
            depends_on=None,
            batch_id="batch-1",
            parent_task_id=None,
            custom_fields=None,
        )
        assert spec.success_criteria == []
        assert spec.blockers == []
        assert spec.depends_on == []
        assert spec.custom_fields == {}

    def test_post_init_preserves_values(self) -> None:
        spec = TaskSubmissionSpec(
            title="Test",
            description="Desc",
            estimate="1h",
            success_criteria=["done"],
            blockers=["blocked"],
            depends_on=["dep1"],
            batch_id="batch-1",
            parent_task_id="parent",
            custom_fields={"key": "val"},
        )
        assert spec.success_criteria == ["done"]
        assert spec.blockers == ["blocked"]
        assert spec.depends_on == ["dep1"]
        assert spec.custom_fields == {"key": "val"}


class TestInferBumpType:
    def test_infer_bump_major(self) -> None:
        from village.chat.task_extractor import _extract_bump_from_tags

        assert _extract_bump_from_tags(["bump:major"]) == "major"

    def test_infer_bump_minor(self) -> None:
        from village.chat.task_extractor import _extract_bump_from_tags

        assert _extract_bump_from_tags(["bump:minor"]) == "minor"

    def test_infer_bump_patch(self) -> None:
        from village.chat.task_extractor import _extract_bump_from_tags

        assert _extract_bump_from_tags(["bump:patch"]) == "patch"

    def test_infer_bump_none(self) -> None:
        from village.chat.task_extractor import _extract_bump_from_tags

        assert _extract_bump_from_tags(["bump:none"]) == "none"

    def test_infer_bump_default_no_tag(self) -> None:
        from village.chat.task_extractor import _extract_bump_from_tags

        assert _extract_bump_from_tags(["frontend", "urgent"]) == "patch"

    def test_infer_bump_empty_tags(self) -> None:
        from village.chat.task_extractor import _extract_bump_from_tags

        assert _extract_bump_from_tags([]) == "patch"

    def test_infer_bump_invalid_value(self) -> None:
        from village.chat.task_extractor import _extract_bump_from_tags

        assert _extract_bump_from_tags(["bump:invalid"]) == "patch"

    def test_infer_bump_case_insensitive(self) -> None:
        from village.chat.task_extractor import _extract_bump_from_tags

        assert _extract_bump_from_tags(["bump:MAJOR"]) == "major"


class TestResolveTaskIds:
    def test_resolve_index_dependencies(self) -> None:
        from village.chat.task_extractor import _resolve_task_ids

        spec1 = TaskSubmissionSpec(
            title="Task 1",
            description="D",
            estimate="1h",
            success_criteria=[],
            blockers=[],
            depends_on=[],
            batch_id="b",
            parent_task_id=None,
            custom_fields={},
        )
        spec2 = TaskSubmissionSpec(
            title="Task 2",
            description="D",
            estimate="2h",
            success_criteria=[],
            blockers=[],
            depends_on=["index-0"],
            batch_id="b",
            parent_task_id=None,
            custom_fields={},
        )
        specs = [spec1, spec2]
        created_tasks = {"Task 1": "tsk-aaa", "Task 2": "tsk-bbb"}
        config = MagicMock()
        with patch("village.chat.task_extractor.get_task_store"):
            _resolve_task_ids(created_tasks, specs, config)
        assert specs[1].depends_on == ["tsk-aaa"]

    def test_resolve_preserves_non_index_deps(self) -> None:
        from village.chat.task_extractor import _resolve_task_ids

        spec1 = TaskSubmissionSpec(
            title="Task 1",
            description="D",
            estimate="1h",
            success_criteria=[],
            blockers=[],
            depends_on=["tsk-existing"],
            batch_id="b",
            parent_task_id=None,
            custom_fields={},
        )
        specs = [spec1]
        created_tasks = {"Task 1": "tsk-aaa"}
        config = MagicMock()
        with patch("village.chat.task_extractor.get_task_store"):
            _resolve_task_ids(created_tasks, specs, config)
        assert specs[0].depends_on == ["tsk-existing"]

    def test_resolve_invalid_index_warns(self) -> None:
        from village.chat.task_extractor import _resolve_task_ids

        spec1 = TaskSubmissionSpec(
            title="Task 1",
            description="D",
            estimate="1h",
            success_criteria=[],
            blockers=[],
            depends_on=["index-99"],
            batch_id="b",
            parent_task_id=None,
            custom_fields={},
        )
        specs = [spec1]
        created_tasks = {"Task 1": "tsk-aaa"}
        config = MagicMock()
        with patch("village.chat.task_extractor.get_task_store"):
            _resolve_task_ids(created_tasks, specs, config)
        assert specs[0].depends_on == []


class TestCreateDraftTasks:
    @pytest.mark.asyncio
    async def test_create_draft_tasks_success(self) -> None:
        from village.chat.task_extractor import create_draft_tasks

        spec = TaskSubmissionSpec(
            title="Draft task",
            description="Desc",
            estimate="1h",
            success_criteria=["done"],
            blockers=[],
            depends_on=[],
            batch_id="batch-1",
            parent_task_id=None,
            custom_fields={"batch": "batch-1", "source": "village-brainstorm"},
        )
        mock_task = MagicMock()
        mock_task.id = "tsk-new1"

        config = MagicMock()
        with patch("village.chat.task_extractor.get_task_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.create_task.return_value = mock_task
            mock_get_store.return_value = mock_store
            result = await create_draft_tasks([spec], config)
        assert result == {"Draft task": "tsk-new1"}
        mock_store.initialize.assert_called()

    @pytest.mark.asyncio
    async def test_create_draft_tasks_propagates_error(self) -> None:
        from village.chat.task_extractor import create_draft_tasks

        spec = TaskSubmissionSpec(
            title="Fail task",
            description="Desc",
            estimate="1h",
            success_criteria=[],
            blockers=[],
            depends_on=[],
            batch_id="batch-1",
            parent_task_id=None,
            custom_fields={},
        )
        config = MagicMock()
        with patch("village.chat.task_extractor.get_task_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.create_task.side_effect = Exception("store error")
            mock_get_store.return_value = mock_store
            with pytest.raises(Exception, match="store error"):
                await create_draft_tasks([spec], config)


class TestCreateSingleDraft:
    @pytest.mark.asyncio
    async def test_labels_include_batch_and_bump(self) -> None:
        from village.chat.task_extractor import _create_single_draft

        spec = TaskSubmissionSpec(
            title="Labeled",
            description="D",
            estimate="1h",
            success_criteria=[],
            blockers=[],
            depends_on=[],
            batch_id="batch-123",
            parent_task_id=None,
            custom_fields={"batch": "batch-123", "source": "village-brainstorm", "tags": "urgent,important"},
            bump="minor",
        )
        mock_task = MagicMock()
        mock_task.id = "tsk-lbl"

        config = MagicMock()
        with patch("village.chat.task_extractor.get_task_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.create_task.return_value = mock_task
            mock_get_store.return_value = mock_store
            result = await _create_single_draft(spec, config)

        assert result == "tsk-lbl"
        call_args = mock_store.create_task.call_args[0][0]
        assert "batch:batch-123" in call_args.labels
        assert "bump:minor" in call_args.labels
        assert "urgent" in call_args.labels
        assert "important" in call_args.labels

    @pytest.mark.asyncio
    async def test_parent_task_id_added_to_depends_on(self) -> None:
        from village.chat.task_extractor import _create_single_draft

        spec = TaskSubmissionSpec(
            title="Child",
            description="D",
            estimate="1h",
            success_criteria=[],
            blockers=[],
            depends_on=[],
            batch_id="batch-1",
            parent_task_id="tsk-parent",
            custom_fields={},
            bump="patch",
        )
        mock_task = MagicMock()
        mock_task.id = "tsk-child"

        config = MagicMock()
        with patch("village.chat.task_extractor.get_task_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.create_task.return_value = mock_task
            mock_get_store.return_value = mock_store
            await _create_single_draft(spec, config)

        call_args = mock_store.create_task.call_args[0][0]
        assert "tsk-parent" in call_args.depends_on

    @pytest.mark.asyncio
    async def test_bump_none_not_added_as_label(self) -> None:
        from village.chat.task_extractor import _create_single_draft

        spec = TaskSubmissionSpec(
            title="NoBump",
            description="D",
            estimate="1h",
            success_criteria=[],
            blockers=[],
            depends_on=[],
            batch_id="batch-1",
            parent_task_id=None,
            custom_fields={},
            bump="none",
        )
        mock_task = MagicMock()
        mock_task.id = "tsk-nobump"

        config = MagicMock()
        with patch("village.chat.task_extractor.get_task_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.create_task.return_value = mock_task
            mock_get_store.return_value = mock_store
            await _create_single_draft(spec, config)

        call_args = mock_store.create_task.call_args[0][0]
        assert "bump:none" not in call_args.labels
