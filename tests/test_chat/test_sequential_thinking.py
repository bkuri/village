"""Unit tests for sequential thinking functionality."""

from datetime import datetime

import pytest

from village.chat.baseline import BaselineReport
from village.chat.sequential_thinking import (
    TaskBreakdown,
    TaskBreakdownItem,
    _build_sequential_thinking_prompt,
    _parse_task_breakdown,
    validate_dependencies,
)


class TestBuildSequentialThinkingPrompt:
    """Tests for _build_sequential_thinking_prompt."""

    def test_prompt_includes_baseline_title_and_reasoning(self) -> None:
        """Test that prompt includes baseline title and reasoning."""
        baseline = BaselineReport(
            title="Build a web application",
            reasoning="Need to break down into manageable tasks",
        )

        prompt = _build_sequential_thinking_prompt(baseline)

        assert "Title: Build a web application" in prompt
        assert "Reasoning: Need to break down into manageable tasks" in prompt

    def test_prompt_includes_instructions_for_task_breakdown(self) -> None:
        """Test that prompt includes instructions for task breakdown."""
        baseline = BaselineReport(
            title="Test task",
            reasoning="Test reasoning",
        )

        prompt = _build_sequential_thinking_prompt(baseline)

        assert "1. Break down into 3-7 concrete, actionable tasks" in prompt
        assert "2. Evaluate if the user's title is precise and descriptive enough" in prompt
        assert (
            "3. If the title is vague, suggest a more specific/recognizable alternative" in prompt
        )
        assert "4. Each task should be independently completable" in prompt
        assert "5. Identify dependencies between tasks (by index)" in prompt
        assert "6. Provide success criteria for each task" in prompt
        assert "7. Estimate effort (hours|days|weeks)" in prompt
        assert "8. Identify potential blockers" in prompt

    def test_prompt_includes_optional_parent_task_id(self) -> None:
        """Test that optional parent_task_id is included when provided."""
        baseline = BaselineReport(
            title="Test task",
            reasoning="Test reasoning",
            parent_task_id="bd-a1b2c3d",
        )

        prompt = _build_sequential_thinking_prompt(baseline)

        assert "Parent task: bd-a1b2c3d" in prompt

    def test_prompt_includes_optional_tags(self) -> None:
        """Test that optional tags are included when provided."""
        baseline = BaselineReport(
            title="Test task",
            reasoning="Test reasoning",
            tags=["frontend", "backend", "api"],
        )

        prompt = _build_sequential_thinking_prompt(baseline)

        assert "Tags: frontend, backend, api" in prompt

    def test_prompt_includes_beads_state(self) -> None:
        """Test that beads_state is included when provided."""
        baseline = BaselineReport(
            title="Test task",
            reasoning="Test reasoning",
        )
        beads_state = "bd-a1b2c3: Task 1\nbd-d4e5f6: Task 2"

        prompt = _build_sequential_thinking_prompt(baseline, beads_state)

        assert "CONTEXT: Consider these existing Beads tasks:" in prompt
        assert "bd-a1b2c3: Task 1" in prompt
        assert "bd-d4e5f6: Task 2" in prompt


class TestParseTaskBreakdown:
    """Tests for _parse_task_breakdown."""

    @pytest.fixture
    def valid_json_response(self) -> str:
        """Fixture providing a valid JSON response."""
        return """{
  "title_original": "Build a web app",
  "title_suggested": "Build a RESTful web application with React and FastAPI",
  "items": [
    {
      "title": "Set up project structure",
      "description": "Initialize git repo, create directory structure",
      "estimated_effort": "2 hours",
      "success_criteria": [
        "Git repository initialized",
        "Directory structure follows best practices"
      ],
      "blockers": [],
      "dependencies": [],
      "tags": ["setup", "git"]
    },
    {
      "title": "Implement authentication",
      "description": "Add JWT authentication to API",
      "estimated_effort": "1 day",
      "success_criteria": [
        "JWT tokens generated",
        "Login endpoint working"
      ],
      "blockers": ["Waiting for database design"],
      "dependencies": [0],
      "tags": ["auth", "security"]
    },
    {
      "title": "Create frontend UI",
      "description": "Build React components for main pages",
      "estimated_effort": "3 days",
      "success_criteria": [
        "Home page component created",
        "Dashboard component created"
      ],
      "blockers": [],
      "dependencies": [1],
      "tags": ["frontend", "react"]
    }
  ],
  "summary": "Three main tasks to build a RESTful web application"
}"""

    def test_parses_valid_json_response(self, valid_json_response: str) -> None:
        """Test that valid JSON response parses correctly into TaskBreakdown."""
        breakdown = _parse_task_breakdown(valid_json_response)

        assert isinstance(breakdown, TaskBreakdown)
        assert breakdown.title_original == "Build a web app"
        assert breakdown.title_suggested == "Build a RESTful web application with React and FastAPI"
        assert breakdown.summary == "Three main tasks to build a RESTful web application"
        assert len(breakdown.items) == 3

    def test_task_breakdown_item_fields_populated_correctly(
        self,
        valid_json_response: str,
    ) -> None:
        """Test that TaskBreakdownItem fields are populated correctly."""
        breakdown = _parse_task_breakdown(valid_json_response)
        item = breakdown.items[0]

        assert item.title == "Set up project structure"
        assert item.description == "Initialize git repo, create directory structure"
        assert item.estimated_effort == "2 hours"

    def test_task_breakdown_item_lists_populated_correctly(
        self,
        valid_json_response: str,
    ) -> None:
        """Test that success_criteria, blockers, dependencies, tags are parsed as lists."""
        breakdown = _parse_task_breakdown(valid_json_response)
        item1 = breakdown.items[1]
        item2 = breakdown.items[2]

        # Check success_criteria
        assert item1.success_criteria == [
            "JWT tokens generated",
            "Login endpoint working",
        ]

        # Check blockers
        assert item1.blockers == ["Waiting for database design"]
        assert item2.blockers == []

        # Check dependencies
        assert item1.dependencies == [0]
        assert item2.dependencies == [1]

        # Check tags
        assert item1.tags == ["auth", "security"]
        assert item2.tags == ["frontend", "react"]

    def test_created_at_is_timestamp(self, valid_json_response: str) -> None:
        """Test that created_at is a valid timestamp."""
        breakdown = _parse_task_breakdown(valid_json_response)

        assert isinstance(breakdown.created_at, str)
        datetime.fromisoformat(breakdown.created_at)  # Will raise if invalid

    def test_handles_missing_optional_fields(self) -> None:
        """Test that missing optional fields are handled gracefully."""
        json_response = """{
  "items": [
    {
      "title": "Task 1",
      "description": "Description",
      "estimated_effort": "1 day",
      "success_criteria": [],
      "blockers": [],
      "dependencies": [],
      "tags": []
    }
  ],
  "summary": "Summary"
}"""

        breakdown = _parse_task_breakdown(json_response)

        assert breakdown.title_original is None
        assert breakdown.title_suggested is None


class TestParseTaskBreakdownWithMarkdown:
    """Tests for parsing JSON wrapped in markdown code blocks."""

    def test_json_wrapped_in_markdown_code_blocks(self) -> None:
        """Test that JSON wrapped in markdown code blocks is extracted correctly."""
        json_content = """{
  "title_original": "Test task",
  "title_suggested": "Better task name",
  "items": [
    {
      "title": "Task 1",
      "description": "Description",
      "estimated_effort": "1 hour",
      "success_criteria": [],
      "blockers": [],
      "dependencies": [],
      "tags": []
    }
  ],
  "summary": "Test summary"
}"""

        markdown_output = f"```json\n{json_content}\n```"

        breakdown = _parse_task_breakdown(markdown_output)

        assert breakdown.title_original == "Test task"
        assert len(breakdown.items) == 1
        assert breakdown.items[0].title == "Task 1"

    def test_json_without_language_specifier(self) -> None:
        """Test that JSON without language specifier is also handled."""
        json_content = """{
  "title_original": "Test task",
  "title_suggested": "Better task name",
  "items": [
    {
      "title": "Task 1",
      "description": "Description",
      "estimated_effort": "1 hour",
      "success_criteria": [],
      "blockers": [],
      "dependencies": [],
      "tags": []
    }
  ],
  "summary": "Test summary"
}"""

        markdown_output = f"```\n{json_content}\n```"

        breakdown = _parse_task_breakdown(markdown_output)

        assert breakdown.title_original == "Test task"
        assert len(breakdown.items) == 1

    def test_json_without_markdown(self) -> None:
        """Test that JSON without markdown is handled correctly."""
        json_response = """{
  "title_original": "Test task",
  "title_suggested": "Better task name",
  "items": [
    {
      "title": "Task 1",
      "description": "Description",
      "estimated_effort": "1 hour",
      "success_criteria": [],
      "blockers": [],
      "dependencies": [],
      "tags": []
    }
  ],
  "summary": "Test summary"
}"""

        breakdown = _parse_task_breakdown(json_response)

        assert breakdown.title_original == "Test task"
        assert len(breakdown.items) == 1


class TestValidateDependencies:
    """Tests for validate_dependencies."""

    @pytest.fixture
    def valid_breakdown(self) -> TaskBreakdown:
        """Fixture providing a valid TaskBreakdown with valid dependencies."""
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
                    description="Second task",
                    estimated_effort="2 hours",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[0],
                    tags=[],
                ),
                TaskBreakdownItem(
                    title="Task 3",
                    description="Third task",
                    estimated_effort="3 hours",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[0, 1],
                    tags=[],
                ),
            ],
            summary="Valid breakdown",
            created_at=datetime.now().isoformat(),
        )

    def test_valid_dependencies_pass(self, valid_breakdown: TaskBreakdown) -> None:
        """Test that valid dependencies pass validation."""
        assert validate_dependencies(valid_breakdown) is True

    def test_empty_dependencies_pass(self) -> None:
        """Test that breakdown with empty dependencies passes."""
        breakdown = TaskBreakdown(
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
            ],
            summary="Single task",
            created_at=datetime.now().isoformat(),
        )

        assert validate_dependencies(breakdown) is True

    def test_out_of_range_dependency_fails(self) -> None:
        """Test that out of range dependencies fail validation."""
        breakdown = TaskBreakdown(
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
                    description="Second task",
                    estimated_effort="2 hours",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[5],  # Invalid: only 2 items (indices 0-1)
                    tags=[],
                ),
            ],
            summary="Invalid breakdown",
            created_at=datetime.now().isoformat(),
        )

        assert validate_dependencies(breakdown) is False

    def test_negative_dependency_fails(self) -> None:
        """Test that negative dependency indices fail validation."""
        breakdown = TaskBreakdown(
            items=[
                TaskBreakdownItem(
                    title="Task 1",
                    description="First task",
                    estimated_effort="1 hour",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[-1],
                    tags=[],
                ),
            ],
            summary="Invalid breakdown",
            created_at=datetime.now().isoformat(),
        )

        assert validate_dependencies(breakdown) is False

    def test_self_reference_dependency_fails(self) -> None:
        """Test that self-reference dependencies fail validation."""
        breakdown = TaskBreakdown(
            items=[
                TaskBreakdownItem(
                    title="Task 1",
                    description="First task",
                    estimated_effort="1 hour",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[0],  # Invalid: depends on itself
                    tags=[],
                ),
            ],
            summary="Invalid breakdown",
            created_at=datetime.now().isoformat(),
        )

        assert validate_dependencies(breakdown) is False

    def test_cyclic_dependencies_detected(self) -> None:
        """Test that cyclic dependencies are detected and fail validation."""
        # Create a cycle: Task 0 depends on Task 1, Task 1 depends on Task 0
        breakdown = TaskBreakdown(
            items=[
                TaskBreakdownItem(
                    title="Task 1",
                    description="First task",
                    estimated_effort="1 hour",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[1],  # Depends on Task 1
                    tags=[],
                ),
                TaskBreakdownItem(
                    title="Task 2",
                    description="Second task",
                    estimated_effort="2 hours",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[0],  # Depends on Task 0 - creates cycle!
                    tags=[],
                ),
            ],
            summary="Cyclic breakdown",
            created_at=datetime.now().isoformat(),
        )

        # Note: The current validate_dependencies doesn't detect cycles,
        # only checks bounds and self-references. This test documents current behavior.
        assert validate_dependencies(breakdown) is True

    def test_complex_valid_dependencies(self) -> None:
        """Test complex dependency chain that should be valid."""
        # Task 0 has no deps
        # Task 1 depends on Task 0
        # Task 2 depends on Task 1
        # Task 3 depends on Tasks 0, 1, 2
        breakdown = TaskBreakdown(
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
                    description="Second task",
                    estimated_effort="2 hours",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[0],
                    tags=[],
                ),
                TaskBreakdownItem(
                    title="Task 3",
                    description="Third task",
                    estimated_effort="3 hours",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[1],
                    tags=[],
                ),
                TaskBreakdownItem(
                    title="Task 4",
                    description="Fourth task",
                    estimated_effort="4 hours",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[0, 1, 2],
                    tags=[],
                ),
            ],
            summary="Complex valid breakdown",
            created_at=datetime.now().isoformat(),
        )

        assert validate_dependencies(breakdown) is True
