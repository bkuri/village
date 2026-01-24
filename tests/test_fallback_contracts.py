"""Test fallback contract generation."""

from datetime import datetime
from pathlib import Path

from village.contracts import generate_fallback_contract


def test_generate_fallback_contract():
    """Test fallback contract generation."""
    task_id = "bd-a3f8"
    agent = "build"
    worktree_path = Path("/worktrees/bd-a3f8")
    git_root = Path("/repo")
    window_name = "build-1-bd-a3f8"
    created_at = datetime(2026, 1, 23, 12, 0, 0)

    contract = generate_fallback_contract(
        task_id,
        agent,
        worktree_path,
        git_root,
        window_name,
        created_at,
    )

    assert "# Task: bd-a3f8 (build)" in contract
    assert "## Goal" in contract
    assert "Work on task `bd-a3f8` in isolated workspace." in contract
    assert "## Constraints" in contract
    assert "## Inputs" in contract
    assert "Worktree path: `/worktrees/bd-a3f8`" in contract
    assert "Git root: `/repo`" in contract
    assert "Window name: `build-1-bd-a3f8`" in contract
    assert "Created: `2026-01-23T12:00:00`" in contract


def test_generate_fallback_contract_frontend():
    """Test fallback contract for different agent type."""
    task_id = "bd-b2f9"
    agent = "frontend"
    worktree_path = Path("/worktrees/bd-b2f9")
    git_root = Path("/repo")
    window_name = "frontend-0-bd-b2f9"
    created_at = datetime(2026, 1, 23, 13, 0, 0)

    contract = generate_fallback_contract(
        task_id,
        agent,
        worktree_path,
        git_root,
        window_name,
        created_at,
    )

    assert "# Task: bd-b2f9 (frontend)" in contract
    assert "Work on task `bd-b2f9`" in contract
