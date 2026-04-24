"""Tests for TaskSpec dataclass."""

from village.chat.task_spec import TaskSpec


def test_has_dependencies_true():
    """Test has_dependencies returns True when task has dependencies."""
    spec_with_blocks = TaskSpec(
        title="Auth feature",
        description="Add authentication",
        scope="feature",
        blocks=["user-profile", "settings"],
        blocked_by=[],
        success_criteria=["Auth works"],
        estimate="2 days",
    )

    spec_blocked = TaskSpec(
        title="Profile feature",
        description="User profile management",
        scope="feature",
        blocks=[],
        blocked_by=["auth-feature"],
        success_criteria=["Profile accessible"],
        estimate="1 day",
    )

    assert spec_with_blocks.has_dependencies() is True
    assert spec_blocked.has_dependencies() is True


def test_has_dependencies_false():
    """Test has_dependencies returns False when task has no dependencies."""
    spec = TaskSpec(
        title="Standalone task",
        description="Independent task",
        scope="feature",
        blocks=[],
        blocked_by=[],
        success_criteria=["Task completed"],
        estimate="1 hour",
    )

    assert spec.has_dependencies() is False


def test_dependency_summary_no_dependencies():
    """Test dependency_summary returns correct message for no dependencies."""
    spec = TaskSpec(
        title="Standalone task",
        description="Independent task",
        scope="feature",
        blocks=[],
        blocked_by=[],
        success_criteria=["Task completed"],
        estimate="1 hour",
    )

    assert spec.dependency_summary() == "No dependencies"


def test_dependency_summary_blocks_only():
    """Test dependency_summary with only blocks."""
    spec = TaskSpec(
        title="Auth feature",
        description="Add authentication",
        scope="feature",
        blocks=["user-profile", "settings"],
        blocked_by=[],
        success_criteria=["Auth works"],
        estimate="2 days",
    )

    assert spec.dependency_summary() == "blocks: user-profile, settings"


def test_dependency_summary_blocked_by_only():
    """Test dependency_summary with only blocked_by."""
    spec = TaskSpec(
        title="Profile feature",
        description="User profile management",
        scope="feature",
        blocks=[],
        blocked_by=["auth-feature", "db-migration"],
        success_criteria=["Profile accessible"],
        estimate="1 day",
    )

    assert spec.dependency_summary() == "blocked by: auth-feature, db-migration"


def test_dependency_summary_both():
    """Test dependency_summary with both blocks and blocked_by."""
    spec = TaskSpec(
        title="API refactor",
        description="Refactor API endpoints",
        scope="refactor",
        blocks=["frontend-integration"],
        blocked_by=["auth-migration"],
        success_criteria=["API refactored"],
        estimate="4-6 hours",
    )

    summary = spec.dependency_summary()
    assert "blocked by: auth-migration" in summary
    assert "blocks: frontend-integration" in summary
