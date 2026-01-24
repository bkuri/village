"""Test context file management."""

from pathlib import Path

from village.chat.context import (
    ContextUpdate,
    apply_context_update,
    get_current_context,
    get_context_dir,
    write_context_file,
)


def test_get_context_dir(tmp_path: Path, mock_config):
    """Test context directory creation."""
    context_dir = get_context_dir(mock_config)

    assert context_dir == tmp_path / ".village" / "context"
    assert context_dir.exists()


def test_write_context_file(tmp_path: Path):
    """Test writing context file."""
    context_dir = tmp_path / ".village" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    file_path = write_context_file(context_dir, "project.md", "# Project\\n\\nSummary")

    assert file_path == tmp_path / ".village" / "context" / "project.md"
    assert file_path.exists()
    assert file_path.read_text(encoding="utf-8") == "# Project\\n\\nSummary"


def test_write_context_file_invalid_name(tmp_path: Path):
    """Test writing context file with invalid name."""
    context_dir = tmp_path / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    try:
        write_context_file(context_dir, "invalid.md", "# Invalid")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Invalid context file name" in str(e)


def test_get_current_context(tmp_path: Path):
    """Test reading current context files."""
    context_dir = tmp_path / ".village" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    (context_dir / "project.md").write_text("# Project", encoding="utf-8")
    (context_dir / "goals.md").write_text("# Goals", encoding="utf-8")

    context_files = get_current_context(context_dir)

    assert len(context_files) == 2
    assert "project.md" in context_files
    assert "goals.md" in context_files
    assert context_files["project.md"].content == "# Project"
    assert context_files["goals.md"].content == "# Goals"


def test_apply_context_update(tmp_path: Path):
    """Test applying context update."""
    context_dir = tmp_path / ".village" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    update = ContextUpdate(
        writes={
            "project.md": "# New Project\\n\\nSummary...",
            "goals.md": "# New Goals\\n\\n- Goal 1",
        },
        notes=["Updated"],
        open_questions=[],
    )

    written = apply_context_update(context_dir, update)

    assert len(written) == 2
    assert "project.md" in written
    assert "goals.md" in written
    assert written["project.md"].read_text(encoding="utf-8") == "# New Project\\n\\nSummary..."
    assert written["goals.md"].read_text(encoding="utf-8") == "# New Goals\\n\\n- Goal 1"
