from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from village.chat.conversation import ConversationState
from village.chat.drafts import DraftTask
from village.chat.state import SessionSnapshot
from village.chat.task_commands import (
    _display_batch_summary,
    _handle_discard,
    _handle_drafts,
    _handle_edit,
    _handle_enable,
    _handle_reset,
    _handle_submit,
    _prepare_batch_summary,
    _switch_to_create_mode,
    handle_task_subcommand,
)


def _make_config(tmp_path: Path) -> MagicMock:
    config = MagicMock()
    config.village_dir = tmp_path / ".village"
    config.village_dir.mkdir(parents=True, exist_ok=True)
    (config.village_dir / "drafts").mkdir(parents=True, exist_ok=True)
    (config.village_dir / "context").mkdir(parents=True, exist_ok=True)
    config.git_root = tmp_path
    return config


def _make_state(**overrides) -> ConversationState:
    defaults = {
        "messages": [],
        "context_files": {},
        "subcommand_results": {},
        "errors": [],
        "mode": "knowledge-share",
        "pending_enables": [],
        "session_snapshot": None,
        "batch_submitted": False,
        "context_diffs": {},
        "active_draft_id": None,
    }
    defaults.update(overrides)
    return ConversationState(**defaults)


class TestSwitchToCreateMode:
    def test_creates_draft_and_switches_mode(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        result = _switch_to_create_mode(["Build auth system"], state, config)

        assert result.mode == "task-create"
        assert len(result.pending_enables) == 1
        draft_id = result.pending_enables[0]
        assert draft_id.startswith("draft-")
        assert len(result.messages) == 1
        assert "Task creation mode enabled" in result.messages[0].content
        assert draft_id in result.messages[0].content

    def test_default_title_when_no_args(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        result = _switch_to_create_mode([], state, config)

        assert result.mode == "task-create"


class TestHandleEnable:
    def test_empty_args_returns_error(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        result = _handle_enable([], state, config)

        assert len(result.errors) == 1
        assert "requires <draft-id>" in result.errors[0]

    def test_enable_all(self, tmp_path: Path):
        config = _make_config(tmp_path)
        draft1 = DraftTask(
            id="draft-aaaa",
            created_at=datetime.now(timezone.utc),
            title="Task A",
            description="",
            scope="feature",
        )
        draft2 = DraftTask(
            id="draft-bbbb",
            created_at=datetime.now(timezone.utc),
            title="Task B",
            description="",
            scope="fix",
        )
        from village.chat.drafts import save_draft

        save_draft(draft1, config)
        save_draft(draft2, config)

        state = _make_state(pending_enables=["draft-aaaa"])
        result = _handle_enable(["all"], state, config)

        assert "draft-bbbb" in result.pending_enables
        assert "Enabled 1 drafts" in result.messages[-1].content

    def test_enable_single_draft(self, tmp_path: Path):
        config = _make_config(tmp_path)
        draft = DraftTask(
            id="draft-cccc",
            created_at=datetime.now(timezone.utc),
            title="Task C",
            description="",
            scope="feature",
        )
        from village.chat.drafts import save_draft

        save_draft(draft, config)

        state = _make_state()
        result = _handle_enable(["draft-cccc"], state, config)

        assert "draft-cccc" in result.pending_enables
        assert "Enabled draft: draft-cccc" in result.messages[-1].content

    def test_enable_nonexistent_draft(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        result = _handle_enable(["draft-missing"], state, config)

        assert len(result.errors) == 1
        assert "Draft not found" in result.errors[0]

    def test_enable_already_enabled_draft(self, tmp_path: Path):
        config = _make_config(tmp_path)
        draft = DraftTask(
            id="draft-dddd",
            created_at=datetime.now(timezone.utc),
            title="Task D",
            description="",
            scope="feature",
        )
        from village.chat.drafts import save_draft

        save_draft(draft, config)

        state = _make_state(pending_enables=["draft-dddd"])
        result = _handle_enable(["draft-dddd"], state, config)

        assert result.pending_enables.count("draft-dddd") == 1


class TestHandleEdit:
    def test_empty_args_returns_error(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        result = _handle_edit([], state, config)

        assert len(result.errors) == 1
        assert "requires <draft-id>" in result.errors[0]

    def test_edit_existing_draft(self, tmp_path: Path):
        config = _make_config(tmp_path)
        draft = DraftTask(
            id="draft-eeee",
            created_at=datetime.now(timezone.utc),
            title="Edit Me",
            description="desc",
            scope="feature",
        )
        from village.chat.drafts import save_draft

        save_draft(draft, config)

        state = _make_state()
        result = _handle_edit(["draft-eeee"], state, config)

        assert result.mode == "task-create"
        assert result.active_draft_id == "draft-eeee"
        assert "Editing draft: draft-eeee" in result.messages[-1].content

    def test_edit_nonexistent_draft(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        result = _handle_edit(["draft-missing"], state, config)

        assert len(result.errors) == 1
        assert "Draft not found" in result.errors[0]


class TestHandleDiscard:
    def test_empty_args_returns_error(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        result = _handle_discard([], state, config)

        assert len(result.errors) == 1
        assert "requires <draft-id>" in result.errors[0]

    def test_discard_existing_draft(self, tmp_path: Path):
        config = _make_config(tmp_path)
        draft = DraftTask(
            id="draft-ffff",
            created_at=datetime.now(timezone.utc),
            title="Discard Me",
            description="",
            scope="feature",
        )
        from village.chat.drafts import save_draft

        save_draft(draft, config)

        state = _make_state(pending_enables=["draft-ffff"])
        result = _handle_discard(["draft-ffff"], state, config)

        assert "draft-ffff" not in result.pending_enables
        assert "Discarded draft: draft-ffff" in result.messages[-1].content

    def test_discard_nonexistent_draft(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        result = _handle_discard(["draft-missing"], state, config)

        assert len(result.errors) == 1
        assert "Draft not found" in result.errors[0]


class TestHandleSubmit:
    def test_no_pending_enables(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state(pending_enables=[])

        result = _handle_submit(state, config)

        assert len(result.errors) == 1
        assert "No drafts enabled" in result.errors[0]

    def test_submit_with_draft_specs_fallback(self, tmp_path: Path):
        config = _make_config(tmp_path)
        draft = DraftTask(
            id="draft-gggg",
            created_at=datetime.now(timezone.utc),
            title="Submit Task",
            description="A task to submit",
            scope="feature",
        )
        from village.chat.drafts import save_draft

        save_draft(draft, config)

        state = _make_state(pending_enables=["draft-gggg"])

        with patch("village.chat.state.load_session_state", return_value={}):
            with patch("village.chat.task_commands.asyncio.run") as mock_run:
                mock_run.return_value = {"bd-new": "bd-new"}
                result = _handle_submit(state, config)

        assert result.batch_submitted is True
        assert result.pending_enables == []
        assert "Created 1 task(s)" in result.messages[-1].content

    def test_submit_draft_not_found_skipped(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state(pending_enables=["draft-missing"])

        with patch("village.chat.state.load_session_state", return_value={}):
            result = _handle_submit(state, config)

        assert len(result.errors) == 1
        assert "No valid tasks" in result.errors[0]

    def test_submit_with_breakdown(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state(pending_enables=["draft-1"])

        breakdown = MagicMock()
        breakdown.items.return_value = [("task1", "spec1")]

        session_data = {
            "session_snapshot": {
                "task_breakdown": breakdown,
                "brainstorm_baseline": {},
            }
        }

        with patch("village.chat.state.load_session_state", return_value=session_data):
            with patch("village.chat.task_commands.extract_task_specs", return_value=[]) as mock_extract:
                _handle_submit(state, config)

                mock_extract.assert_called_once()
                assert mock_extract.call_args[0][2] == config.git_root.name

    def test_submit_exception_handling(self, tmp_path: Path):
        config = _make_config(tmp_path)
        draft = DraftTask(
            id="draft-hhhh",
            created_at=datetime.now(timezone.utc),
            title="Error Task",
            description="",
            scope="feature",
        )
        from village.chat.drafts import save_draft

        save_draft(draft, config)

        state = _make_state(pending_enables=["draft-hhhh"])

        with patch("village.chat.state.load_session_state", return_value={}):
            with patch("village.chat.task_commands.asyncio.run", side_effect=Exception("boom")):
                result = _handle_submit(state, config)

        assert len(result.errors) == 1
        assert "boom" in result.errors[0]


class TestHandleReset:
    def test_no_session_snapshot(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state(session_snapshot=None)

        result = _handle_reset(state, config)

        assert "No tasks created in this session" in result.messages[-1].content

    def test_no_created_tasks(self, tmp_path: Path):
        config = _make_config(tmp_path)
        snapshot = SessionSnapshot(
            start_time=datetime.now(timezone.utc),
            batch_id="b1",
            initial_context_files={},
            current_context_files={},
            pending_enables=[],
            created_task_ids=[],
        )
        state = _make_state(session_snapshot=snapshot)

        result = _handle_reset(state, config)

        assert "No tasks created in this session" in result.messages[-1].content

    def test_reset_deletes_tasks_and_restores_context(self, tmp_path: Path):
        config = _make_config(tmp_path)
        snapshot = SessionSnapshot(
            start_time=datetime.now(timezone.utc),
            batch_id="b1",
            initial_context_files={"goals.md": "# Goals\n"},
            current_context_files={},
            pending_enables=["draft-x"],
            created_task_ids=["bd-001", "bd-002"],
        )
        state = _make_state(session_snapshot=snapshot, pending_enables=["draft-x"])

        mock_store = MagicMock()
        with patch("village.chat.task_commands.get_task_store", return_value=mock_store):
            result = _handle_reset(state, config)

        assert mock_store.delete_task.call_count == 2
        assert result.pending_enables == []
        assert result.session_snapshot.created_task_ids == []
        assert result.active_draft_id is None
        assert "Rolled back 2 tasks" in result.messages[-1].content

        restored = config.village_dir / "context" / "goals.md"
        assert restored.read_text(encoding="utf-8") == "# Goals\n"

    def test_reset_handles_delete_error(self, tmp_path: Path):
        from village.tasks import TaskStoreError

        config = _make_config(tmp_path)
        snapshot = SessionSnapshot(
            start_time=datetime.now(timezone.utc),
            batch_id="b1",
            initial_context_files={},
            current_context_files={},
            pending_enables=[],
            created_task_ids=["bd-001"],
        )
        state = _make_state(session_snapshot=snapshot)

        mock_store = MagicMock()
        mock_store.delete_task.side_effect = TaskStoreError("not found")
        with patch("village.chat.task_commands.get_task_store", return_value=mock_store):
            result = _handle_reset(state, config)

        assert "Rolled back 0 tasks" in result.messages[-1].content


class TestHandleDrafts:
    def test_no_drafts(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        result = _handle_drafts(state, config)

        assert "No drafts found" in result.messages[-1].content

    def test_lists_drafts_with_enabled_marker(self, tmp_path: Path):
        config = _make_config(tmp_path)
        draft = DraftTask(
            id="draft-iiii",
            created_at=datetime.now(timezone.utc),
            title="Draft Title",
            description="",
            scope="feature",
        )
        from village.chat.drafts import save_draft

        save_draft(draft, config)

        state = _make_state(pending_enables=["draft-iiii"])
        result = _handle_drafts(state, config)

        content = result.messages[-1].content
        assert "Draft tasks:" in content
        assert "[✓] draft-iiii" in content
        assert "[feature]" in content
        assert "Draft Title" in content

    def test_lists_drafts_with_disabled_marker(self, tmp_path: Path):
        config = _make_config(tmp_path)
        draft = DraftTask(
            id="draft-jjjj",
            created_at=datetime.now(timezone.utc),
            title="Another Draft",
            description="",
            scope="fix",
        )
        from village.chat.drafts import save_draft

        save_draft(draft, config)

        state = _make_state(pending_enables=[])
        result = _handle_drafts(state, config)

        content = result.messages[-1].content
        assert "[ ] draft-jjjj" in content
        assert "[fix]" in content


class TestPrepareBatchSummary:
    def test_with_drafts(self, tmp_path: Path):
        config = _make_config(tmp_path)
        draft = DraftTask(
            id="draft-kkkk",
            created_at=datetime.now(timezone.utc),
            title="Summary Task",
            description="desc",
            scope="feature",
            estimate="3d",
        )
        from village.chat.drafts import save_draft

        save_draft(draft, config)

        state = _make_state(pending_enables=["draft-kkkk"], context_diffs={"goals.md": "diff"})
        result = _prepare_batch_summary(state, config)

        assert result["total_tasks"] == 1
        assert result["drafts"][0]["id"] == "draft-kkkk"
        assert result["drafts"][0]["scope"] == "feature"
        assert len(result["context_changes"]) == 1
        assert result["context_changes"][0]["file"] == "goals.md"

    def test_draft_not_found_skipped(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state(pending_enables=["draft-missing"])
        result = _prepare_batch_summary(state, config)

        assert result["total_tasks"] == 0
        assert result["drafts"] == []


class TestDisplayBatchSummary:
    def test_with_drafts_and_changes(self):
        summary = {
            "total_tasks": 2,
            "drafts": [
                {"id": "draft-a", "scope": "feature", "title": "Task A"},
                {"id": "draft-b", "scope": "fix", "title": "Task B"},
            ],
            "context_changes": [{"file": "goals.md", "change": "modified"}],
        }
        output = _display_batch_summary(summary)
        assert "BATCH SUBMISSION REVIEW" in output
        assert "draft-a [feature]" in output
        assert "draft-b [fix]" in output
        assert "goals.md: modified" in output

    def test_empty_drafts(self):
        summary = {"total_tasks": 0, "drafts": [], "context_changes": []}
        output = _display_batch_summary(summary)
        assert "No tasks enabled for submission" in output
        assert "No context changes" in output


class TestHandleTaskSubcommand:
    def test_routes_to_create(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        with patch("village.chat.task_commands._switch_to_create_mode", return_value=state) as mock:
            with patch("village.chat.task_commands.save_session_state"):
                handle_task_subcommand(state, "create", ["My Task"], config)
                mock.assert_called_once_with(["My Task"], state, config)

    def test_routes_to_enable(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        with patch("village.chat.task_commands._handle_enable", return_value=state) as mock:
            with patch("village.chat.task_commands.save_session_state"):
                handle_task_subcommand(state, "enable", ["draft-x"], config)
                mock.assert_called_once_with(["draft-x"], state, config)

    def test_routes_to_edit(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        with patch("village.chat.task_commands._handle_edit", return_value=state) as mock:
            with patch("village.chat.task_commands.save_session_state"):
                handle_task_subcommand(state, "edit", ["draft-x"], config)
                mock.assert_called_once_with(["draft-x"], state, config)

    def test_routes_to_discard(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        with patch("village.chat.task_commands._handle_discard", return_value=state) as mock:
            with patch("village.chat.task_commands.save_session_state"):
                handle_task_subcommand(state, "discard", ["draft-x"], config)
                mock.assert_called_once_with(["draft-x"], state, config)

    def test_routes_to_submit(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        with patch("village.chat.task_commands._handle_submit", return_value=state) as mock:
            with patch("village.chat.task_commands.save_session_state"):
                handle_task_subcommand(state, "submit", [], config)
                mock.assert_called_once_with(state, config)

    def test_routes_to_reset(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        with patch("village.chat.task_commands._handle_reset", return_value=state) as mock:
            with patch("village.chat.task_commands.save_session_state"):
                handle_task_subcommand(state, "reset", [], config)
                mock.assert_called_once_with(state, config)

    def test_routes_to_drafts(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        with patch("village.chat.task_commands._handle_drafts", return_value=state) as mock:
            with patch("village.chat.task_commands.save_session_state"):
                handle_task_subcommand(state, "drafts", [], config)
                mock.assert_called_once_with(state, config)

    def test_unknown_command_ignores(self, tmp_path: Path):
        config = _make_config(tmp_path)
        state = _make_state()

        with patch("village.chat.task_commands.save_session_state"):
            result = handle_task_subcommand(state, "unknown", [], config)
            assert result is state
