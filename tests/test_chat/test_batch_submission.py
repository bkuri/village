"""Test batch submission and task creation workflow."""

from datetime import datetime
from unittest.mock import patch

import pytest

from village.chat.conversation import (
    ConversationState,
    _display_batch_summary,
    _handle_discard,
    _handle_drafts,
    _handle_edit,
    _handle_enable,
    _handle_reset,
    _handle_submit,
    _handle_task_subcommand,
    _prepare_batch_summary,
    _switch_to_create_mode,
    start_conversation,
)
from village.chat.drafts import DraftTask, generate_draft_id, load_draft, save_draft
from village.chat.state import SessionSnapshot, load_session_state, save_session_state


@pytest.fixture
def mock_config(tmp_path):
    """Create mock config for testing."""
    from village.config import Config

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
def mock_state():
    """Create mock conversation state."""
    return ConversationState(
        messages=[],
        context_files={},
        subcommand_results={},
        errors=[],
        mode="knowledge-share",
        pending_enables=[],
        session_snapshot=None,
        batch_submitted=False,
        context_diffs={},
    )


class TestModeSwitching:
    """Test mode switching between knowledge-share and task-create."""

    def test_switch_to_create_mode_creates_draft(self, mock_config, mock_state):
        """Test switching to task-create mode creates a draft."""
        state = _switch_to_create_mode(["Add Redis caching"], mock_state, mock_config)

        assert state.mode == "task-create"
        assert len(state.pending_enables) == 1
        assert len(state.messages) > 0
        assert state.session_snapshot is not None

    def test_switch_to_create_mode_without_title(self, mock_config, mock_state):
        """Test switching to task-create mode without title uses default."""
        state = _switch_to_create_mode([], mock_state, mock_config)

        assert state.mode == "task-create"
        draft_id = state.pending_enables[0]
        draft = load_draft(draft_id, mock_config)
        assert draft.title == "Untitled Task"

    @patch("village.chat.conversation.generate_mode_prompt")
    def test_start_conversation_with_mode_parameter(self, mock_generate, mock_config):
        """Test start_conversation respects mode parameter."""
        mock_generate.return_value = ("Test prompt", "embedded")

        state = start_conversation(mock_config, mode="task-create")

        assert state.mode == "task-create"
        assert state.session_snapshot is not None


class TestDraftManagement:
    """Test draft management operations."""

    def test_enable_single_draft(self, mock_config, mock_state):
        """Test enabling a single draft."""
        draft_id = generate_draft_id()
        draft = DraftTask(
            id=draft_id,
            created_at=datetime.now(),
            title="Test Task",
            description="Test",
            scope="feature",
        )
        save_draft(draft, mock_config)

        state = _handle_enable([draft_id], mock_state, mock_config)

        assert draft_id in state.pending_enables

    def test_enable_all_drafts(self, mock_config, mock_state):
        """Test enabling all drafts."""
        draft1 = DraftTask(
            id=generate_draft_id(),
            created_at=datetime.now(),
            title="Task 1",
            description="Test",
            scope="feature",
        )
        draft2 = DraftTask(
            id=generate_draft_id(),
            created_at=datetime.now(),
            title="Task 2",
            description="Test",
            scope="feature",
        )
        save_draft(draft1, mock_config)
        save_draft(draft2, mock_config)

        state = _handle_enable(["all"], mock_state, mock_config)

        assert len(state.pending_enables) == 2

    def test_enable_nonexistent_draft(self, mock_config, mock_state):
        """Test enabling non-existent draft shows error."""
        state = _handle_enable(["draft-nonexistent"], mock_state, mock_config)

        assert "Error: Draft not found" in state.messages[-1].content

    def test_edit_existing_draft(self, mock_config, mock_state):
        """Test editing existing draft switches mode."""
        draft = DraftTask(
            id=generate_draft_id(),
            created_at=datetime.now(),
            title="Original Title",
            description="Test",
            scope="feature",
        )
        save_draft(draft, mock_config)

        state = _handle_edit([draft.id], mock_state, mock_config)

        assert state.mode == "task-create"
        assert "Editing draft" in state.messages[-1].content

    def test_edit_nonexistent_draft(self, mock_config, mock_state):
        """Test editing non-existent draft shows error."""
        state = _handle_edit(["draft-nonexistent"], mock_state, mock_config)

        assert "Error: Draft not found" in state.messages[-1].content

    def test_discard_draft_removes_from_disk(self, mock_config, mock_state):
        """Test discarding draft removes from disk and pending."""
        draft = DraftTask(
            id=generate_draft_id(),
            created_at=datetime.now(),
            title="To Delete",
            description="Test",
            scope="feature",
        )
        save_draft(draft, mock_config)
        mock_state.pending_enables.append(draft.id)

        state = _handle_discard([draft.id], mock_state, mock_config)

        assert draft.id not in state.pending_enables
        assert not (mock_config.village_dir / "drafts" / f"{draft.id}.json").exists()

    def test_discard_nonexistent_draft(self, mock_config, mock_state):
        """Test discarding non-existent draft shows error."""
        state = _handle_discard(["draft-nonexistent"], mock_state, mock_config)

        assert "Error: Draft not found" in state.messages[-1].content

    def test_list_drafts_shows_all(self, mock_config, mock_state):
        """Test listing drafts shows all drafts."""
        draft1 = DraftTask(
            id=generate_draft_id(),
            created_at=datetime.now(),
            title="Task 1",
            description="Test",
            scope="feature",
        )
        draft2 = DraftTask(
            id=generate_draft_id(),
            created_at=datetime.now(),
            title="Task 2",
            description="Test",
            scope="fix",
        )
        save_draft(draft1, mock_config)
        save_draft(draft2, mock_config)

        state = _handle_drafts(mock_state, mock_config)

        assert "Draft tasks:" in state.messages[-1].content
        assert draft1.id in state.messages[-1].content
        assert draft2.id in state.messages[-1].content


class TestBatchSubmission:
    """Test batch submission workflow."""

    def test_submit_with_no_enabled_drafts(self, mock_config, mock_state):
        """Test submitting with no enabled drafts shows error."""
        state = _handle_submit(mock_state, mock_config)

        assert "Error: No drafts enabled" in state.messages[-1].content

    def test_submit_with_enabled_drafts(self, mock_config, mock_state):
        """Test submitting with enabled drafts creates tasks."""
        draft = DraftTask(
            id=generate_draft_id(),
            created_at=datetime.now(),
            title="Test Task",
            description="Test",
            scope="feature",
            estimate="days",
        )
        save_draft(draft, mock_config)
        mock_state.pending_enables.append(draft.id)

        state = _handle_submit(mock_state, mock_config)

        # Task creation message (now actually creates Beads tasks)
        assert "Created" in state.messages[-1].content
        assert "task(s) in Beads" in state.messages[-1].content

    def test_prepare_batch_summary(self, mock_config, mock_state):
        """Test preparing batch summary."""
        draft = DraftTask(
            id=generate_draft_id(),
            created_at=datetime.now(),
            title="Test Task",
            description="Test",
            scope="feature",
            estimate="days",
        )
        save_draft(draft, mock_config)
        mock_state.pending_enables.append(draft.id)

        summary = _prepare_batch_summary(mock_state, mock_config)

        assert summary["total_tasks"] == 1
        assert len(summary["drafts"]) == 1
        assert summary["drafts"][0]["id"] == draft.id
        assert summary["drafts"][0]["title"] == "Test Task"

    def test_display_batch_summary(self, mock_config):
        """Test displaying batch summary."""
        summary = {
            "total_tasks": 2,
            "drafts": [
                {
                    "id": "draft-abc123",
                    "title": "Task 1",
                    "scope": "feature",
                    "estimate": "days",
                },
                {
                    "id": "draft-def456",
                    "title": "Task 2",
                    "scope": "fix",
                    "estimate": "hours",
                },
            ],
            "context_changes": [],
        }

        output = _display_batch_summary(summary)

        assert "BATCH SUBMISSION REVIEW" in output
        assert "draft-abc123" in output
        assert "draft-def456" in output
        assert "PENDING TASK ENABLES (2)" in output


class TestReset:
    """Test session reset functionality."""

    def test_reset_with_no_created_tasks(self, mock_config, mock_state):
        """Test resetting with no created tasks shows error."""
        state = _handle_reset(mock_state, mock_config)

        assert "Error: No tasks created" in state.messages[-1].content

    def test_reset_with_created_tasks(self, mock_config, mock_state):
        """Test resetting deletes created tasks."""
        snapshot = SessionSnapshot(
            start_time=datetime.now(),
            batch_id="test-batch",
            initial_context_files={},
            current_context_files={},
            pending_enables=[],
            created_task_ids=["bd-test123", "bd-test456"],
        )
        mock_state.session_snapshot = snapshot

        with patch("village.chat.conversation.run_command_output"):
            state = _handle_reset(mock_state, mock_config)

        assert len(state.session_snapshot.created_task_ids) == 0
        assert len(state.pending_enables) == 0
        assert "Drafts preserved" in state.messages[-1].content


class TestSessionPersistence:
    """Test session state persistence."""

    def test_save_and_load_session_state(self, mock_config, mock_state):
        """Test saving and loading session state."""
        mock_state.pending_enables = ["draft-abc123", "draft-def456"]
        mock_state.context_diffs = {"goals.md": "+5 lines"}
        mock_state.batch_submitted = False

        save_session_state(mock_state, mock_config)

        loaded = load_session_state(mock_config)

        assert loaded["mode"] == "knowledge-share"
        assert loaded["pending_enables"] == ["draft-abc123", "draft-def456"]
        assert loaded["context_diffs"] == {"goals.md": "+5 lines"}
        assert loaded["batch_submitted"] is False

    def test_load_nonexistent_session_state(self, mock_config):
        """Test loading non-existent session returns empty dict."""
        session_file = mock_config.village_dir / "session.json"
        if session_file.exists():
            session_file.unlink()

        loaded = load_session_state(mock_config)

        assert loaded == {}


class TestTaskSubcommandRouting:
    """Test task subcommand routing."""

    def test_create_subcommand_routes_to_handler(self, mock_config, mock_state):
        """Test /create command routes to correct handler."""
        state = _handle_task_subcommand(mock_state, "create", ["Test Task"], mock_config)

        assert state.mode == "task-create"
        assert len(state.pending_enables) > 0

    def test_enable_subcommand_routes_to_handler(self, mock_config, mock_state):
        """Test /enable command routes to correct handler."""
        draft = DraftTask(
            id=generate_draft_id(),
            created_at=datetime.now(),
            title="Test Task",
            description="Test",
            scope="feature",
        )
        save_draft(draft, mock_config)

        state = _handle_task_subcommand(mock_state, "enable", [draft.id], mock_config)

        assert draft.id in state.pending_enables

    def test_discard_subcommand_routes_to_handler(self, mock_config, mock_state):
        """Test /discard command routes to correct handler."""
        draft = DraftTask(
            id=generate_draft_id(),
            created_at=datetime.now(),
            title="Test Task",
            description="Test",
            scope="feature",
        )
        save_draft(draft, mock_config)

        _handle_task_subcommand(mock_state, "discard", [draft.id], mock_config)

        assert not (mock_config.village_dir / "drafts" / f"{draft.id}.json").exists()
