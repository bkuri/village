"""Test draft task storage."""

from datetime import datetime
from pathlib import Path

from village.chat.drafts import (
    DraftTask,
    delete_draft,
    generate_draft_id,
    list_drafts,
    load_draft,
    save_draft,
)


def test_generate_draft_id():
    """Test draft ID generation."""
    draft_id = generate_draft_id()

    assert draft_id.startswith("draft-")
    assert len(draft_id) == 14  # "draft-" + 8 hex chars


def test_save_and_load_draft(tmp_path: Path, mock_config):
    """Test saving and loading a draft."""
    draft = DraftTask(
        id="draft-abc123",
        created_at=datetime(2026, 1, 23, 15, 30, 0),
        title="Add Redis caching",
        description="Cache API responses",
        scope="feature",
        relates_to_goals=["improve-performance"],
        success_criteria=["Response < 100ms"],
        blockers=["Redis deployment TBD"],
        estimate="days",
        tags=["performance"],
        notes=["User mentioned this is high priority"],
    )

    file_path = save_draft(draft, mock_config)

    assert file_path.exists()
    assert file_path.name == "draft-abc123.json"

    loaded = load_draft("draft-abc123", mock_config)

    assert loaded.id == "draft-abc123"
    assert loaded.title == "Add Redis caching"
    assert loaded.description == "Cache API responses"
    assert loaded.scope == "feature"
    assert loaded.relates_to_goals == ["improve-performance"]
    assert loaded.success_criteria == ["Response < 100ms"]
    assert loaded.blockers == ["Redis deployment TBD"]
    assert loaded.estimate == "days"
    assert loaded.tags == ["performance"]
    assert loaded.notes == ["User mentioned this is high priority"]


def test_list_drafts(tmp_path: Path, mock_config):
    """Test listing drafts sorted by date."""
    draft1 = DraftTask(
        id="draft-abc123",
        created_at=datetime(2026, 1, 23, 10, 0, 0),
        title="Draft 1",
        description="First draft",
        scope="feature",
        success_criteria=[],
        blockers=[],
        estimate="unknown",
    )

    draft2 = DraftTask(
        id="draft-def456",
        created_at=datetime(2026, 1, 23, 12, 0, 0),
        title="Draft 2",
        description="Second draft",
        scope="fix",
        success_criteria=[],
        blockers=[],
        estimate="unknown",
    )

    draft3 = DraftTask(
        id="draft-ghi789",
        created_at=datetime(2026, 1, 22, 8, 0, 0),
        title="Draft 3",
        description="Third draft",
        scope="investigation",
        success_criteria=[],
        blockers=[],
        estimate="unknown",
    )

    # Save drafts
    save_draft(draft1, mock_config)
    save_draft(draft2, mock_config)
    save_draft(draft3, mock_config)

    # List drafts
    drafts = list_drafts(mock_config)

    assert len(drafts) == 3
    # Should be sorted newest first
    assert drafts[0].id == "draft-def456"  # 12:00
    assert drafts[1].id == "draft-abc123"  # 10:00
    assert drafts[2].id == "draft-ghi789"  # yesterday


def test_delete_draft(tmp_path: Path, mock_config):
    """Test deleting a draft."""
    draft = DraftTask(
        id="draft-abc123",
        created_at=datetime(2026, 1, 23, 15, 30, 0),
        title="Test draft",
        description="Test",
        scope="feature",
        success_criteria=[],
        blockers=[],
        estimate="unknown",
    )

    save_draft(draft, mock_config)

    # Verify it exists
    drafts_dir = mock_config.village_dir / "drafts"
    assert (drafts_dir / "draft-abc123.json").exists()

    # Delete it
    delete_draft("draft-abc123", mock_config)

    # Verify it's gone
    assert not (drafts_dir / "draft-abc123.json").exists()


def test_load_draft_not_found(tmp_path: Path, mock_config):
    """Test loading nonexistent draft raises error."""
    try:
        load_draft("draft-nonexistent", mock_config)
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError as e:
        assert "not found" in str(e).lower()


def test_delete_draft_not_found(tmp_path: Path, mock_config):
    """Test deleting nonexistent draft raises error."""
    try:
        delete_draft("draft-nonexistent", mock_config)
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError as e:
        assert "not found" in str(e).lower()


def test_list_drafts_with_invalid_json(tmp_path: Path, mock_config):
    """Test listing drafts handles invalid JSON gracefully."""
    # Create a valid draft
    valid_draft = DraftTask(
        id="draft-valid",
        created_at=datetime(2026, 1, 23, 15, 30, 0),
        title="Valid",
        description="Valid",
        scope="feature",
        success_criteria=[],
        blockers=[],
        estimate="unknown",
    )
    save_draft(valid_draft, mock_config)

    # Create an invalid JSON file
    drafts_dir = mock_config.village_dir / "drafts"
    invalid_file = drafts_dir / "draft-invalid.json"
    invalid_file.write_text("{ invalid json }", encoding="utf-8")

    # List should return only valid drafts
    drafts = list_drafts(mock_config)

    assert len(drafts) == 1
    assert drafts[0].id == "draft-valid"
