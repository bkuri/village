"""Test session state management."""

from datetime import datetime

from village.chat.conversation import ConversationState
from village.chat.state import (
    count_pending_changes,
    load_session_state,
    save_session_state,
    take_session_snapshot,
)


def test_save_and_load_session_state(tmp_path, mock_config):
    """Test saving and loading session state."""
    # Create .village directory
    mock_config.village_dir.mkdir(parents=True, exist_ok=True)

    state = ConversationState(
        mode="knowledge-share",
        pending_enables=["draft-1", "draft-2"],
        context_diffs={"goals.md": "added goal"},
        batch_submitted=False,
    )

    # Save state
    save_session_state(state, mock_config)

    # Load it back
    loaded = load_session_state(mock_config)

    assert loaded.get("mode") == "knowledge-share"
    assert loaded.get("pending_enables") == ["draft-1", "draft-2"]
    assert loaded.get("context_diffs") == {"goals.md": "added goal"}
    assert loaded.get("batch_submitted") is False


def test_count_pending_changes(tmp_path, mock_config):
    """Test counting pending changes."""
    # Create .village directory
    mock_config.village_dir.mkdir(parents=True, exist_ok=True)

    state = ConversationState(
        pending_enables=["draft-1", "draft-2"],
        context_diffs={"goals.md": "added", "project.md": "updated"},
    )

    save_session_state(state, mock_config)

    count = count_pending_changes(mock_config)

    # 2 enables + 2 context diffs = 4 pending
    assert count == 4


def test_take_session_snapshot(tmp_path, mock_config):
    """Test capturing session snapshot."""
    # Create .village directory
    mock_config.village_dir.mkdir(parents=True, exist_ok=True)

    state = ConversationState(
        mode="knowledge-share",
        pending_enables=["draft-1"],
        context_diffs={},
    )

    snapshot = take_session_snapshot(state, mock_config)

    assert snapshot.batch_id.startswith("batch-")
    assert isinstance(snapshot.start_time, datetime)
    assert snapshot.pending_enables == ["draft-1"]
    assert snapshot.initial_context_files == {}
    assert snapshot.current_context_files == {}
    assert snapshot.created_task_ids == []


def test_load_session_state_no_file(tmp_path, mock_config):
    """Test loading when no session file exists."""
    loaded = load_session_state(mock_config)

    # Should return empty dict when no file exists
    assert loaded == {}


def test_session_persistence_overwrites(tmp_path, mock_config):
    """Test that saving state overwrites existing state."""
    # Create .village directory
    mock_config.village_dir.mkdir(parents=True, exist_ok=True)

    state1 = ConversationState(
        mode="knowledge-share",
        pending_enables=["draft-1"],
        context_diffs={},
    )

    save_session_state(state1, mock_config)

    state2 = ConversationState(
        mode="task-create",
        pending_enables=["draft-2"],
        context_diffs={"goals.md": "new"},
    )

    save_session_state(state2, mock_config)

    loaded = load_session_state(mock_config)

    # Should load state2, not state1
    assert loaded.get("mode") == "task-create"
    assert loaded.get("pending_enables") == ["draft-2"]
    assert loaded.get("context_diffs") == {"goals.md": "new"}
