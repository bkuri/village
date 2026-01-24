"""Integration tests for Village Chat workflow scenarios."""

import json
import subprocess
from unittest.mock import patch
from uuid import uuid4

import pytest

from village.chat.conversation import (
    _handle_discard,
    _handle_edit,
    _handle_enable,
    _handle_reset,
    _handle_submit,
    _switch_to_create_mode,
    start_conversation,
)
from village.chat.drafts import (
    draft_id_to_task_id,
    load_draft,
    save_draft,
)
from village.chat.state import load_session_state, save_session_state
from village.config import Config


@pytest.fixture
def integration_config(tmp_path):
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
def mock_bd_create(monkeypatch):
    """Mock bd create subprocess calls."""
    created_calls = []

    def fake_run_command(cmd, **kwargs):
        if len(cmd) > 1 and cmd[0] == "bd" and cmd[1] == "create":
            created_calls.append(
                {
                    "command": "create",
                    "args": cmd,
                    "task_id": f"bd-{uuid4().hex[:6]}",
                }
            )
            return f"Created task: {created_calls[-1]['task_id']}"

        if len(cmd) > 1 and cmd[0] == "bd" and cmd[1] == "delete":
            created_calls.append(
                {
                    "command": "delete",
                    "task_id": cmd[2] if len(cmd) > 2 else "unknown",
                }
            )
            return "Task deleted"

        return ""

    monkeypatch.setattr("village.chat.conversation.run_command_output", fake_run_command)
    return created_calls


@pytest.fixture
def fresh_conversation(integration_config):
    """Create a fresh conversation state for each test."""
    with patch("village.chat.conversation.generate_initial_prompt") as mock_gen:
        mock_gen.return_value = ("System prompt for testing", "embedded")
        return start_conversation(integration_config, mode="knowledge-share")


@pytest.fixture
def test_beads_db(tmp_path, monkeypatch):
    """Create a real Beads database for integration tests."""
    db_path = tmp_path / ".beads"

    result = subprocess.run(
        ["bd", "init"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        pytest.skip(f"Failed to initialize Beads DB: {result.stderr}")

    monkeypatch.setenv("BEADS_DIR", str(db_path))

    return tmp_path


class TestMultiDraftWorkflows:
    """Test scenarios with multiple drafts in one session."""

    def test_create_three_drafts_enable_all_submit(
        self, integration_config, mock_bd_create, fresh_conversation
    ):
        """Create 3 different task types, enable all, submit batch."""
        state = fresh_conversation

        drafts = []
        for i, (title, scope) in enumerate(
            [
                ("Feature: Add Redis caching", "feature"),
                ("Bug: Fix auth timeout", "fix"),
                ("Investigation: Performance bottleneck", "investigation"),
            ]
        ):
            state = _switch_to_create_mode([title], state, integration_config)
            draft_id = state.pending_enables[-1]
            draft = load_draft(draft_id, integration_config)
            draft.scope = scope
            save_draft(draft, integration_config)
            drafts.append(draft_id)

        assert len(drafts) == 3
        assert all(
            (integration_config.village_dir / "drafts" / f"{did}.json").exists() for did in drafts
        )

        assert len(state.pending_enables) == 3

        state = _handle_enable(["all"], state, integration_config)
        assert len(state.pending_enables) == 3

        state = _handle_submit(state, integration_config)
        assert len(mock_bd_create) == 3

        for draft_id in drafts:
            assert not (integration_config.village_dir / "drafts" / f"{draft_id}.json").exists()

    def test_create_four_enable_two_submit(
        self, integration_config, mock_bd_create, fresh_conversation
    ):
        """Create 4, enable selectively (2), submit only enabled."""
        state = fresh_conversation

        drafts = []
        for i in range(4):
            state = _switch_to_create_mode([f"Task {i + 1}"], state, integration_config)
            drafts.append(state.pending_enables[-1])

        state.pending_enables = []
        state = _handle_enable([drafts[1]], state, integration_config)
        state = _handle_enable([drafts[3]], state, integration_config)

        assert len(state.pending_enables) == 2

        state = _handle_submit(state, integration_config)
        assert len(mock_bd_create) == 2

        assert not (integration_config.village_dir / "drafts" / f"{drafts[1]}.json").exists()
        assert not (integration_config.village_dir / "drafts" / f"{drafts[3]}.json").exists()
        assert (integration_config.village_dir / "drafts" / f"{drafts[0]}.json").exists()
        assert (integration_config.village_dir / "drafts" / f"{drafts[2]}.json").exists()

    def test_create_enable_all_discard_one_submit(
        self, integration_config, mock_bd_create, fresh_conversation
    ):
        """Create 3, enable all, discard 1 before submit, submit 2."""
        state = fresh_conversation

        drafts = []
        for i in range(3):
            state = _switch_to_create_mode([f"Task {i + 1}"], state, integration_config)
            drafts.append(state.pending_enables[-1])

        state.pending_enables = []
        state = _handle_enable(["all"], state, integration_config)
        assert len(state.pending_enables) == 3

        state = _handle_discard([drafts[1]], state, integration_config)
        assert len(state.pending_enables) == 2

        assert not (integration_config.village_dir / "drafts" / f"{drafts[1]}.json").exists()

        state = _handle_submit(state, integration_config)
        assert len(mock_bd_create) == 2


class TestEditWorkflows:
    """Test editing and re-entering Q&A for existing drafts."""

    def test_create_edit_enable_submit(
        self, integration_config, mock_bd_create, fresh_conversation
    ):
        """Create draft, edit it, enable, submit."""
        state = fresh_conversation

        state = _switch_to_create_mode(["Initial Task"], state, integration_config)
        draft_id = state.pending_enables[-1]

        state = _handle_edit([draft_id], state, integration_config)
        assert state.mode == "task-create"

        draft = load_draft(draft_id, integration_config)
        draft.title = "Edited Task: Much Better Description"
        draft.description = "Added more details during editing"
        save_draft(draft, integration_config)

        state.pending_enables = []
        state = _handle_enable([draft_id], state, integration_config)

        state = _handle_submit(state, integration_config)
        assert len(mock_bd_create) == 1
        assert not (integration_config.village_dir / "drafts" / f"{draft_id}.json").exists()

    def test_create_multiple_edit_one_enable_all_submit(
        self, integration_config, mock_bd_create, fresh_conversation
    ):
        """Create 3, edit middle one, enable all, submit all 3."""
        state = fresh_conversation

        drafts = []
        for i in range(3):
            state = _switch_to_create_mode([f"Task {i + 1}"], state, integration_config)
            drafts.append(state.pending_enables[-1])

        state.pending_enables = []

        draft = load_draft(drafts[1], integration_config)
        draft.scope = "fix"
        draft.title = "Task 2 (edited to fix)"
        save_draft(draft, integration_config)

        state = _handle_enable(["all"], state, integration_config)
        state = _handle_submit(state, integration_config)

        assert len(mock_bd_create) == 3

    def test_create_edit_discard_create_new(
        self, integration_config, mock_bd_create, fresh_conversation
    ):
        """Create A, edit, discard, create different B, submit B."""
        state = fresh_conversation

        state = _switch_to_create_mode(["Task A"], state, integration_config)
        draft_a = state.pending_enables[-1]

        state = _handle_edit([draft_a], state, integration_config)
        state = _handle_discard([draft_a], state, integration_config)
        assert not (integration_config.village_dir / "drafts" / f"{draft_a}.json").exists()

        state.pending_enables = []

        state = _switch_to_create_mode(["Task B"], state, integration_config)
        draft_b = state.pending_enables[-1]

        state = _handle_submit(state, integration_config)
        assert len(mock_bd_create) == 1
        assert not (integration_config.village_dir / "drafts" / f"{draft_b}.json").exists()

    def test_create_enable_edit_before_submit(
        self, integration_config, mock_bd_create, fresh_conversation
    ):
        """Create, enable, edit before submit (all sequential)."""
        state = fresh_conversation

        state = _switch_to_create_mode(["Task"], state, integration_config)
        draft_id = state.pending_enables[-1]

        state = _handle_enable([draft_id], state, integration_config)

        draft = load_draft(draft_id, integration_config)
        draft.scope = "investigation"
        save_draft(draft, integration_config)

        state = _handle_submit(state, integration_config)
        assert len(mock_bd_create) == 1


class TestResetRollback:
    """Test session reset and rollback functionality."""

    def test_create_submit_reset(self, integration_config, mock_bd_create, fresh_conversation):
        """Create, submit, then reset."""
        state = fresh_conversation

        state = _switch_to_create_mode(["Task"], state, integration_config)
        draft_id = state.pending_enables[-1]
        state = _handle_enable([draft_id], state, integration_config)

        with patch("village.chat.conversation.run_command_output") as mock_bd:
            mock_bd.return_value = "Created: bd-a1b2c3"
            state = _handle_submit(state, integration_config)

        assert state.session_snapshot is not None
        assert len(state.session_snapshot.created_task_ids) > 0

        state = _handle_reset(state, integration_config)

        assert len(mock_bd_create) == 1

        assert len(state.pending_enables) == 0
        assert state.session_snapshot is not None
        assert len(state.session_snapshot.created_task_ids) == 0

        assert (integration_config.village_dir / "drafts" / f"{draft_id}.json").exists()

        assert "preserved" in state.messages[-1].content.lower()

    def test_create_multiple_submit_partial_reset(
        self, integration_config, mock_bd_create, fresh_conversation
    ):
        """Create 3, enable 2, submit 2, reset."""
        state = fresh_conversation

        drafts = []
        for i in range(3):
            state = _switch_to_create_mode([f"Task {i + 1}"], state, integration_config)
            drafts.append(state.pending_enables[-1])

        state.pending_enables = []

        state = _handle_enable([drafts[0]], state, integration_config)
        state = _handle_enable([drafts[2]], state, integration_config)

        with patch("village.chat.conversation.run_command_output") as mock_bd:
            mock_bd.return_value = "Created: bd-a1b2c3"
            state = _handle_submit(state, integration_config)

        state = _handle_reset(state, integration_config)
        assert mock_bd_create.call_count == 2

        for draft_id in drafts:
            assert (integration_config.village_dir / "drafts" / f"{draft_id}.json").exists()

    def test_reset_twice_error(self, integration_config, mock_bd_create, fresh_conversation):
        """Reset once (success), reset again (should error)."""
        state = fresh_conversation

        state = _switch_to_create_mode(["Task"], state, integration_config)
        draft_id = state.pending_enables[-1]
        state = _handle_enable([draft_id], state, integration_config)

        with patch("village.chat.conversation.run_command_output") as mock_bd:
            mock_bd.return_value = "Created: bd-a1b2c3"
            state = _handle_submit(state, integration_config)

        state = _handle_reset(state, integration_config)

        assert len(state.errors) > 0

        error_msg = state.errors[-1] if state.errors else ""
        assert "No tasks created" in error_msg
        assert "Draft not found" in error_msg


class TestSessionPersistence:
    """Test session state persistence across save/load."""

    def test_mode_state_persists(self, integration_config, mock_bd_create, fresh_conversation):
        """Save session in task-create mode, load and verify."""
        state = fresh_conversation

        state = _switch_to_create_mode(["Task"], state, integration_config)
        draft_id = state.pending_enables[-1]

        save_session_state(state, integration_config)

        loaded = load_session_state(integration_config)

        assert loaded.get("mode") == "task-create"
        assert draft_id in loaded.get("pending_enables", [])

        state2 = start_conversation(integration_config)
        assert state2.mode == "knowledge-share"

    def test_snapshot_tracks_created_tasks(
        self, integration_config, mock_bd_create, fresh_conversation
    ):
        """Create, submit, verify snapshot has task IDs."""
        state = fresh_conversation

        state = _switch_to_create_mode(["Task"], state, integration_config)
        draft_id = state.pending_enables[-1]
        state = _handle_enable([draft_id], state, integration_config)

        with patch("village.chat.conversation.run_command_output") as mock_bd:
            mock_bd.return_value = "Created: bd-a1b2c3"
            state = _handle_submit(state, integration_config)

        assert state.session_snapshot is not None
        assert len(state.session_snapshot.created_task_ids) > 0

        save_session_state(state, integration_config)

        loaded = load_session_state(integration_config)

    def test_context_diffs_preserved(self, integration_config, mock_bd_create, fresh_conversation):
        """Track context changes, save, load, verify."""
        state = fresh_conversation

        state.context_diffs["goals.md"] = "+5 lines"
        state.context_diffs["project.md"] = "modified"

        save_session_state(state, integration_config)

        loaded = load_session_state(integration_config)

        assert loaded.get("context_diffs") == {
            "goals.md": "+5 lines",
            "project.md": "modified",
        }


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_enable_nonexistent_draft_error(
        self, integration_config, mock_bd_create, fresh_conversation
    ):
        """User typos draft ID on enable."""
        state = fresh_conversation

        state = _handle_enable(["df-nonexist"], state, integration_config)

        assert len(state.errors) > 0
        assert "Draft not found" in state.errors[-1] if state.errors else ""
        assert state.pending_enables == []

    def test_submit_no_drafts_enabled_error(
        self, integration_config, mock_bd_create, fresh_conversation
    ):
        """Submit with empty pending_enables."""
        state = fresh_conversation

        state.pending_enables = []
        state = _handle_submit(state, integration_config)

        assert len(state.errors) > 0
        assert "No drafts enabled" in state.errors[-1] if state.errors else ""

    def test_discard_nonexistent_draft_error(
        self, integration_config, mock_bd_create, fresh_conversation
    ):
        """Discard draft that doesn't exist."""
        state = fresh_conversation

        state = _handle_discard(["df-missing"], state, integration_config)

        assert len(state.errors) > 0
        assert "Draft not found" in state.errors[-1] if state.errors else ""

    def test_mode_conflict_create_in_task_mode(
        self, integration_config, mock_bd_create, fresh_conversation
    ):
        """User calls /create while already in task-create mode."""
        state = fresh_conversation

        state = _switch_to_create_mode(["Task 1"], state, integration_config)
        first_draft = state.pending_enables[0]

        state = _switch_to_create_mode(["Task 2"], state, integration_config)

        assert len(state.pending_enables) >= 1


class TestBeadsIntegration:
    """Integration tests with real Beads database."""

    def test_real_bd_manifest_creation(self, test_beads_db, fresh_conversation):
        """Create real Beads task with manifest from Village draft."""
        config = Config(
            git_root=test_beads_db,
            village_dir=test_beads_db / ".village",
            worktrees_dir=test_beads_db / ".worktrees",
            tmux_session="test",
            default_agent="worker",
            max_workers=2,
        )
        config.village_dir.mkdir(parents=True, exist_ok=True)
        (config.village_dir / "drafts").mkdir(parents=True, exist_ok=True)

        state = fresh_conversation

        state = _switch_to_create_mode(["Test Feature"], state, config)
        draft_id = state.pending_enables[-1]

        draft = load_draft(draft_id, config)
        draft.description = "A real feature for testing"
        draft.scope = "feature"
        save_draft(draft, config)

        state = _handle_enable([draft_id], state, config)
        state = _handle_submit(state, config)

        result = subprocess.run(
            ["bd", "list", "--json"],
            cwd=test_beads_db,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        tasks = json.loads(result.stdout)
        assert len(tasks) > 0
        assert any(t.get("title") == "Test Feature" for t in tasks)

    def test_real_bd_draft_id_mapping(self, test_beads_db):
        """Create with df-a1b2c3 -> bd-a1b2c3 ID mapping."""
        draft_id = "df-a1b2c3"
        task_id = draft_id_to_task_id(draft_id)

        assert task_id == "bd-a1b2c3"

        result = subprocess.run(
            ["bd", "create", "--id", task_id, "Test Mapped ID"],
            cwd=test_beads_db,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        result = subprocess.run(
            ["bd", "show", task_id],
            cwd=test_beads_db,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Test Mapped ID" in result.stdout

    def test_real_bd_delete_recovery(self, test_beads_db, fresh_conversation):
        """Create real task, then delete via reset."""
        config = Config(
            git_root=test_beads_db,
            village_dir=test_beads_db / ".village",
            worktrees_dir=test_beads_db / ".worktrees",
            tmux_session="test",
            default_agent="worker",
            max_workers=2,
        )
        config.village_dir.mkdir(parents=True, exist_ok=True)
        (config.village_dir / "drafts").mkdir(parents=True, exist_ok=True)

        state = fresh_conversation

        state = _switch_to_create_mode(["Task to Delete"], state, config)
        draft_id = state.pending_enables[-1]
        state = _handle_enable([draft_id], state, config)
        state = _handle_submit(state, config)

        assert state.session_snapshot is not None
        created_id = state.session_snapshot.created_task_ids[0]

        result = subprocess.run(
            ["bd", "show", created_id],
            cwd=test_beads_db,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        state = _handle_reset(state, config)

        result = subprocess.run(
            ["bd", "show", created_id],
            cwd=test_beads_db,
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
