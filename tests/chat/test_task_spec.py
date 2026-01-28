"""Tests for TaskSpec dataclass."""

from village.chat.task_spec import TaskSpec


def test_task_spec_creation():
    """Test TaskSpec dataclass creation with all fields."""
    spec = TaskSpec(
        title="Refactor user API",
        description="Update user endpoints to follow new patterns",
        scope="refactor",
        blocks=["profile-feature"],
        blocked_by=["auth-migration"],
        success_criteria=[
            "User endpoints follow patterns",
            "All endpoints use new auth",
            "API documentation updated",
        ],
        estimate="4-6 hours",
        confidence="high",
    )

    assert spec.title == "Refactor user API"
    assert spec.description == "Update user endpoints to follow new patterns"
    assert spec.scope == "refactor"
    assert spec.blocks == ["profile-feature"]
    assert spec.blocked_by == ["auth-migration"]
    assert len(spec.success_criteria) == 3
    assert spec.estimate == "4-6 hours"
    assert spec.confidence == "high"


def test_task_spec_defaults():
    """Test TaskSpec with default confidence value."""
    spec = TaskSpec(
        title="Fix login bug",
        description="User cannot login with special characters",
        scope="fix",
        blocks=[],
        blocked_by=[],
        success_criteria=["Login works with special characters"],
        estimate="1 hour",
    )

    assert spec.confidence == "medium"


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


def test_scope_literal_types():
    """Test that only valid scope values are accepted."""
    valid_scopes = ["fix", "feature", "config", "docs", "test", "refactor"]

    for scope in valid_scopes:
        spec = TaskSpec(
            title="Test task",
            description="Test description",
            scope=scope,  # type: ignore[arg-type]
            blocks=[],
            blocked_by=[],
            success_criteria=["Test"],
            estimate="1 hour",
        )
        assert spec.scope == scope


def test_confidence_literal_types():
    """Test that only valid confidence values are accepted."""
    valid_confidences = ["high", "medium", "low"]

    for confidence in valid_confidences:
        spec = TaskSpec(
            title="Test task",
            description="Test description",
            scope="feature",
            blocks=[],
            blocked_by=[],
            success_criteria=["Test"],
            estimate="1 hour",
            confidence=confidence,  # type: ignore[arg-type]
        )
        assert spec.confidence == confidence


def test_multiple_success_criteria():
    """Test task spec with multiple success criteria."""
    criteria = [
        "First criterion",
        "Second criterion",
        "Third criterion",
        "Fourth criterion",
    ]

    spec = TaskSpec(
        title="Complex task",
        description="Task with multiple criteria",
        scope="feature",
        blocks=[],
        blocked_by=[],
        success_criteria=criteria,
        estimate="2 weeks",
    )

    assert len(spec.success_criteria) == 4
    assert spec.success_criteria == criteria


def test_multiple_blocks_and_blocked_by():
    """Test task spec with multiple dependencies."""
    spec = TaskSpec(
        title="Core feature",
        description="Core system feature",
        scope="feature",
        blocks=["feature-a", "feature-b", "feature-c"],
        blocked_by=["infra-upgrade", "data-migration"],
        success_criteria=["Core works"],
        estimate="1 month",
    )

    assert len(spec.blocks) == 3
    assert len(spec.blocked_by) == 2
    assert spec.has_dependencies() is True
