"""Integration tests for /brainstorm command workflow."""

import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import anyio
import pytest

from village.chat.baseline import BaselineReport
from village.chat.conversation import ConversationState, _handle_brainstorm, start_conversation
from village.chat.sequential_thinking import TaskBreakdown, TaskBreakdownItem
from village.config import Config


@pytest.fixture
def integration_config(tmp_path: Path) -> Config:
    """Create test config with all necessary directories."""
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
        tmux_session="test-session",
        default_agent="worker",
        max_workers=2,
    )
    config.village_dir.mkdir(parents=True, exist_ok=True)
    (config.village_dir / "context").mkdir(parents=True, exist_ok=True)
    (config.village_dir / "drafts").mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture
def mock_baseline_report() -> BaselineReport:
    """Mock baseline report for testing."""
    return BaselineReport(
        title="Add user authentication",
        reasoning="Need to secure the application with user login and session management",
        parent_task_id=None,
        tags=["auth", "security"],
    )


@pytest.fixture
def mock_task_breakdown() -> TaskBreakdown:
    """Mock task breakdown for testing."""
    return TaskBreakdown(
        items=[
            TaskBreakdownItem(
                title="Design authentication schema",
                description="Create database schema for users, sessions, and permissions",
                estimated_effort="4 hours",
                success_criteria=["Schema defined", "Migration scripts ready"],
                blockers=[],
                dependencies=[],
                tags=["database", "design"],
            ),
            TaskBreakdownItem(
                title="Implement login endpoint",
                description="Create POST /auth/login with JWT token generation",
                estimated_effort="8 hours",
                success_criteria=["Login working", "JWT tokens generated"],
                blockers=["Design authentication schema"],
                dependencies=[1],
                tags=["backend", "api"],
            ),
            TaskBreakdownItem(
                title="Add session management",
                description="Implement session validation and refresh logic",
                estimated_effort="6 hours",
                success_criteria=["Session middleware working", "Token refresh working"],
                blockers=["Implement login endpoint"],
                dependencies=[1],
                tags=["backend", "security"],
            ),
        ],
        summary="Breakdown authentication into 3 tasks: schema design, login, session management",
        created_at=datetime.now().isoformat(),
        title_original="Add user authentication",
        title_suggested="Implement user authentication with JWT",
    )


@pytest.fixture
def mock_created_task_ids() -> dict[str, str]:
    """Mock created task IDs for testing."""
    return {
        "Design authentication schema": f"bd-{uuid4().hex[:6]}",
        "Implement login endpoint": f"bd-{uuid4().hex[:6]}",
        "Add session management": f"bd-{uuid4().hex[:6]}",
    }


@pytest.fixture
def fresh_conversation(integration_config: Config) -> ConversationState:
    """Create a fresh conversation state for each test."""
    with patch("village.chat.conversation.generate_initial_prompt") as mock_gen:
        mock_gen.return_value = ("System prompt for testing", "embedded")
        return start_conversation(integration_config, mode="knowledge-share")


class TestBrainstormCommandInvocation:
    """Test /brainstorm command invocation and handler routing."""

    def test_brainstorm_command_invokes_handlers(
        self,
        integration_config: Config,
        fresh_conversation: ConversationState,
        mock_baseline_report: BaselineReport,
        mock_task_breakdown: TaskBreakdown,
        mock_created_task_ids: dict[str, str],
    ) -> None:
        """
        Verify /brainstorm command properly invokes handler and updates state.

        Tests that calling _handle_brainstorm with valid arguments:
        - Calls the brainstorm handler
        - Updates state with baseline information
        - Creates session snapshot
        - Creates draft tasks
        """
        state = fresh_conversation

        with (
            patch("village.chat.conversation.collect_baseline") as mock_collect,
            patch("village.chat.conversation.generate_task_breakdown") as mock_generate,
            patch(
                "village.chat.conversation.create_draft_tasks", new_callable=AsyncMock
            ) as mock_create,
            patch("village.chat.conversation.ensure_beads_initialized"),
            patch("village.chat.conversation.run_command_output", return_value=None),
            patch("village.chat.conversation.validate_dependencies", return_value=True),
            patch("village.chat.conversation.extract_beads_specs", return_value=[]),
        ):
            mock_collect.return_value = mock_baseline_report
            mock_generate.return_value = mock_task_breakdown
            mock_create.return_value = mock_created_task_ids

            state = anyio.run(
                lambda: _handle_brainstorm(["Add user authentication"], state, integration_config)
            )

            assert state.session_snapshot is not None
            assert state.session_snapshot.brainstorm_baseline is not None
            assert (
                state.session_snapshot.brainstorm_baseline["baseline_title"]
                == "Add user authentication"
            )
            assert len(state.session_snapshot.brainstorm_created_ids) == 3
            assert len(state.pending_enables) == 3


class TestBrainstormValidation:
    """Test /brainstorm command validation and error handling."""

    def test_brainstorm_without_title_errors(
        self, integration_config: Config, fresh_conversation: ConversationState
    ) -> None:
        """
        Verify /brainstorm without title shows appropriate error.

        Tests that calling _handle_brainstorm without arguments:
        - Shows error message about missing title
        - Session snapshot is None (error occurs during baseline collection)
        - No draft tasks created
        """
        state = fresh_conversation

        with (
            patch("village.chat.conversation.collect_baseline") as mock_collect,
            patch("village.chat.conversation.ensure_beads_initialized"),
        ):
            mock_collect.side_effect = ValueError("Title must be at least 3 characters")

            state = anyio.run(lambda: _handle_brainstorm([], state, integration_config))

            assert state.session_snapshot is None
            assert len(state.pending_enables) == 0

            error_messages = [
                msg for msg in state.messages if msg.role == "assistant" and "Error:" in msg.content
            ]
            assert len(error_messages) > 0
            assert "Error:" in error_messages[0].content


class TestBrainstormSessionSnapshot:
    """Test session snapshot creation during /brainstorm."""

    def test_brainstorm_creates_session_snapshot(
        self,
        integration_config: Config,
        fresh_conversation: ConversationState,
        mock_baseline_report: BaselineReport,
        mock_task_breakdown: TaskBreakdown,
        mock_created_task_ids: dict[str, str],
    ) -> None:
        """
        Verify /brainstorm creates proper session snapshot.

        Tests that calling _handle_brainstorm:
        - Creates session_snapshot with brainstorm_baseline
        - Sets batch_id with timestamp
        - Includes baseline data with title, reasoning, and creation timestamp
        """
        state = fresh_conversation

        with (
            patch("village.chat.conversation.collect_baseline") as mock_collect,
            patch("village.chat.conversation.generate_task_breakdown") as mock_generate,
            patch(
                "village.chat.conversation.create_draft_tasks", new_callable=AsyncMock
            ) as mock_create,
            patch("village.chat.conversation.ensure_beads_initialized"),
            patch("village.chat.conversation.run_command_output", return_value=None),
            patch("village.chat.conversation.validate_dependencies", return_value=True),
            patch("village.chat.conversation.extract_beads_specs", return_value=[]),
        ):
            mock_collect.return_value = mock_baseline_report
            mock_generate.return_value = mock_task_breakdown
            mock_create.return_value = mock_created_task_ids

            state = anyio.run(lambda: _handle_brainstorm(["Add auth"], state, integration_config))

            assert state.session_snapshot is not None
            assert state.session_snapshot.brainstorm_baseline is not None
            assert "baseline_title" in state.session_snapshot.brainstorm_baseline
            assert "baseline_reasoning" in state.session_snapshot.brainstorm_baseline
            assert "created_at" in state.session_snapshot.brainstorm_baseline
            assert state.session_snapshot.batch_id.startswith("batch-")


class TestBrainstormDraftTasks:
    """Test draft task creation during /brainstorm."""

    def test_brainstorm_creates_draft_tasks(
        self,
        integration_config: Config,
        fresh_conversation: ConversationState,
        mock_baseline_report: BaselineReport,
        mock_task_breakdown: TaskBreakdown,
        mock_created_task_ids: dict[str, str],
    ) -> None:
        """
        Verify /brainstorm creates draft tasks properly.

        Tests that calling _handle_brainstorm:
        - Generates task breakdown via generate_task_breakdown
        - Creates draft tasks via create_draft_tasks
        - Populates state.session_snapshot.brainstorm_created_ids
        - Adds created task IDs to pending_enables
        """
        state = fresh_conversation

        with (
            patch("village.chat.conversation.collect_baseline") as mock_collect,
            patch("village.chat.conversation.generate_task_breakdown") as mock_generate,
            patch(
                "village.chat.conversation.create_draft_tasks", new_callable=AsyncMock
            ) as mock_create,
            patch("village.chat.conversation.ensure_beads_initialized"),
            patch("village.chat.conversation.run_command_output", return_value=None),
            patch("village.chat.conversation.validate_dependencies", return_value=True),
            patch("village.chat.conversation.extract_beads_specs", return_value=[]),
        ):
            mock_collect.return_value = mock_baseline_report
            mock_generate.return_value = mock_task_breakdown
            mock_create.return_value = mock_created_task_ids

            state = anyio.run(lambda: _handle_brainstorm(["Test"], state, integration_config))

            mock_generate.assert_called_once()
            mock_create.assert_called_once()

            assert state.session_snapshot is not None
            assert len(state.session_snapshot.brainstorm_created_ids) == 3
            assert len(state.pending_enables) == 3
            assert all(tid in state.pending_enables for tid in mock_created_task_ids.values())


class TestBrainstormBeadsIntegration:
    """Test /brainstorm integration with existing Beads tasks."""

    def test_brainstorm_with_existing_beads_tasks(
        self,
        integration_config: Config,
        fresh_conversation: ConversationState,
        mock_baseline_report: BaselineReport,
        mock_task_breakdown: TaskBreakdown,
        mock_created_task_ids: dict[str, str],
    ) -> None:
        """
        Verify /brainstorm passes Beads context to generate_task_breakdown.

        Tests that calling _handle_brainstorm with existing Beads tasks:
        - Queries Beads for existing tasks via `bd list --json`
        - Passes Beads state to generate_task_breakdown as beads_state kwarg
        - New tasks can reference existing tasks appropriately
        """
        state = fresh_conversation

        existing_beads_json = (
            '[{"id":"bd-existing1","title":"Setup database","status":"open"},'
            '{"id":"bd-existing2","title":"Create API base","status":"open"}]'
        )

        with (
            patch("village.chat.conversation.collect_baseline") as mock_collect,
            patch("village.chat.conversation.generate_task_breakdown") as mock_generate,
            patch(
                "village.chat.conversation.create_draft_tasks", new_callable=AsyncMock
            ) as mock_create,
            patch("village.chat.conversation.ensure_beads_initialized"),
            patch("village.chat.conversation.run_command_output", return_value=existing_beads_json),
            patch("village.chat.conversation.validate_dependencies", return_value=True),
            patch("village.chat.conversation.extract_beads_specs", return_value=[]),
        ):
            mock_collect.return_value = mock_baseline_report
            mock_generate.return_value = mock_task_breakdown
            mock_create.return_value = mock_created_task_ids

            state = anyio.run(lambda: _handle_brainstorm(["Test"], state, integration_config))

            mock_generate.assert_called_once()
            call_args = mock_generate.call_args[0]
            call_kwargs = mock_generate.call_args[1]
            assert call_args[0] == mock_baseline_report
            assert call_args[1] == integration_config
            assert call_kwargs["beads_state"] == existing_beads_json


class TestBrainstormErrorHandling:
    """Test error handling in /brainstorm command."""

    def test_brainstorm_error_handling_generate_failure(
        self,
        integration_config: Config,
        fresh_conversation: ConversationState,
        mock_baseline_report: BaselineReport,
    ) -> None:
        """
        Verify /brainstorm handles generate_task_breakdown errors.

        Tests that calling _handle_brainstorm when generate_task_breakdown fails:
        - Catches ValueError exception
        - Displays appropriate error message
        - Session snapshot is created before error occurs
        - No draft tasks are created (brainstorm_created_ids is empty)
        """
        state = fresh_conversation

        with (
            patch("village.chat.conversation.collect_baseline") as mock_collect,
            patch("village.chat.conversation.generate_task_breakdown") as mock_generate,
            patch("village.chat.conversation.ensure_beads_initialized"),
            patch("village.chat.conversation.run_command_output", return_value=None),
        ):
            mock_collect.return_value = mock_baseline_report
            mock_generate.side_effect = ValueError("Invalid breakdown format")

            state = anyio.run(lambda: _handle_brainstorm(["Test"], state, integration_config))

            assert state.session_snapshot is not None
            assert len(state.session_snapshot.brainstorm_created_ids) == 0
            assert len(state.pending_enables) == 0

            error_messages = [
                msg for msg in state.messages if msg.role == "assistant" and "Error:" in msg.content
            ]
            assert len(error_messages) > 0

    def test_brainstorm_error_handling_subprocess_failure(
        self,
        integration_config: Config,
        fresh_conversation: ConversationState,
        mock_baseline_report: BaselineReport,
    ) -> None:
        """
        Verify /brainstorm handles subprocess errors from Sequential Thinking.

        Tests that calling _handle_brainstorm when Sequential Thinking fails:
        - Catches CalledProcessError
        - Displays helpful error message with retry guidance
        - Session snapshot is created before error occurs
        - No draft tasks are created
        """
        state = fresh_conversation

        with (
            patch("village.chat.conversation.collect_baseline") as mock_collect,
            patch("village.chat.conversation.generate_task_breakdown") as mock_generate,
            patch("village.chat.conversation.ensure_beads_initialized"),
            patch("village.chat.conversation.run_command_output", return_value=None),
        ):
            mock_collect.return_value = mock_baseline_report
            mock_generate.side_effect = subprocess.CalledProcessError(
                1, "opencode", stderr="Failed to generate breakdown"
            )

            state = anyio.run(lambda: _handle_brainstorm(["Test"], state, integration_config))

            assert state.session_snapshot is not None
            assert len(state.session_snapshot.brainstorm_created_ids) == 0
            assert len(state.pending_enables) == 0

            error_messages = [
                msg for msg in state.messages if msg.role == "assistant" and "Error:" in msg.content
            ]
            assert len(error_messages) > 0
            assert (
                "Sequential Thinking" in error_messages[-1].content
                or "Try:" in error_messages[-1].content
            )

    def test_brainstorm_error_handling_unexpected_failure(
        self,
        integration_config: Config,
        fresh_conversation: ConversationState,
        mock_baseline_report: BaselineReport,
    ) -> None:
        """
        Verify /brainstorm handles unexpected errors gracefully.

        Tests that calling _handle_brainstorm when an unexpected error occurs:
        - Catches generic Exception
        - Displays generic error message
        - Session snapshot is created before error occurs
        - No draft tasks are created
        """
        state = fresh_conversation

        with (
            patch("village.chat.conversation.collect_baseline") as mock_collect,
            patch("village.chat.conversation.generate_task_breakdown") as mock_generate,
            patch("village.chat.conversation.ensure_beads_initialized"),
            patch("village.chat.conversation.run_command_output", return_value=None),
        ):
            mock_collect.return_value = mock_baseline_report
            mock_generate.side_effect = RuntimeError("Unexpected system failure")

            state = anyio.run(lambda: _handle_brainstorm(["Test"], state, integration_config))

            assert state.session_snapshot is not None
            assert len(state.session_snapshot.brainstorm_created_ids) == 0
            assert len(state.pending_enables) == 0

            error_messages = [
                msg for msg in state.messages if msg.role == "assistant" and "Error:" in msg.content
            ]
            assert len(error_messages) > 0
            assert (
                "Unexpected" in error_messages[-1].content
                or "Try: /brainstorm again" in error_messages[-1].content
            )
