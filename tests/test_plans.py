"""Tests for plan storage."""

import pytest

from village.plans.models import Plan, PlanState
from village.plans.slug import generate_slug, slugify
from village.plans.store import FilePlanStore, PlanNotFoundError, SlugCollisionError


def test_slugify():
    assert slugify("Overhaul the authentication system") == "overhaul-authentication"
    assert slugify("Add new feature for users") == "add-feature-users"
    assert slugify("Fix bug #123") == "fix-bug-123"
    assert slugify("Implement v2 API") == "implement-v2-api"


def test_generate_slug():
    assert generate_slug("Test objective") == "test-objective"
    assert generate_slug("Test objective") == generate_slug("Test objective")


def test_plan_model():
    plan = Plan(slug="test-plan", objective="Test objective")
    assert plan.state == PlanState.DRAFT
    assert plan.slug == "test-plan"
    data = plan.to_dict()
    assert data["state"] == "draft"
    restored = Plan.from_dict(data)
    assert restored.slug == plan.slug
    assert restored.state == plan.state


def test_file_plan_store_create(tmp_path):
    store = FilePlanStore(tmp_path)
    plan = Plan(slug="test", objective="Test")
    created = store.create(plan)
    assert created.slug == "test"
    assert store.exists("test")


def test_file_plan_store_collision(tmp_path):
    store = FilePlanStore(tmp_path)
    store.create(Plan(slug="test", objective="Test"))
    with pytest.raises(SlugCollisionError):
        store.create(Plan(slug="test", objective="Test 2"))


def test_file_plan_store_get(tmp_path):
    store = FilePlanStore(tmp_path)
    plan = Plan(slug="test", objective="Test")
    store.create(plan)
    retrieved = store.get("test")
    assert retrieved.slug == "test"


def test_file_plan_store_not_found(tmp_path):
    store = FilePlanStore(tmp_path)
    with pytest.raises(PlanNotFoundError):
        store.get("nonexistent")


def test_file_plan_store_list(tmp_path):
    store = FilePlanStore(tmp_path)
    store.create(Plan(slug="plan1", objective="Plan 1"))
    store.create(Plan(slug="plan2", objective="Plan 2"))
    plans = store.list()
    assert len(plans) == 2
    plans_draft = store.list(PlanState.DRAFT)
    assert len(plans_draft) == 2


def test_file_plan_store_update(tmp_path):
    store = FilePlanStore(tmp_path)
    plan = Plan(slug="test", objective="Test")
    store.create(plan)
    plan.state = PlanState.APPROVED
    store.update(plan)
    updated = store.get("test")
    assert updated.state == PlanState.APPROVED


def test_file_plan_store_delete(tmp_path):
    store = FilePlanStore(tmp_path)
    plan = Plan(slug="test", objective="Test")
    store.create(plan)
    assert store.exists("test")
    store.delete("test")
    assert not store.exists("test")


def test_file_plan_store_update_moves_directory(tmp_path):
    """Test that updating from DRAFT to APPROVED moves the directory."""
    store = FilePlanStore(tmp_path)
    plan = Plan(slug="test-move", objective="Test move")
    store.create(plan)

    # Verify it's in drafts
    assert (tmp_path / "drafts" / "test-move").exists()
    assert not (tmp_path / "approved" / "test-move").exists()

    # Update to APPROVED
    plan.state = PlanState.APPROVED
    store.update(plan)

    # Verify it's moved to approved
    assert not (tmp_path / "drafts" / "test-move").exists()
    assert (tmp_path / "approved" / "test-move").exists()

    retrieved = store.get("test-move")
    assert retrieved.state == PlanState.APPROVED


def test_file_plan_store_list_by_state(tmp_path):
    """Test listing plans filtered by state."""
    store = FilePlanStore(tmp_path)

    plan1 = Plan(slug="plan-draft", objective="Draft plan")
    plan2 = Plan(slug="plan-approved", objective="Approved plan")

    store.create(plan1)
    store.create(plan2)

    plan2.state = PlanState.APPROVED
    store.update(plan2)

    drafts = store.list(PlanState.DRAFT)
    assert len(drafts) == 1
    assert drafts[0].slug == "plan-draft"

    approved = store.list(PlanState.APPROVED)
    assert len(approved) == 1
    assert approved[0].slug == "plan-approved"


def test_plan_to_json(tmp_path):
    """Test that to_json produces valid JSON."""
    store = FilePlanStore(tmp_path)
    plan = Plan(slug="json-test", objective="JSON test")
    created = store.create(plan)

    json_str = created.to_json()
    assert '"slug": "json-test"' in json_str
    assert '"objective": "JSON test"' in json_str
    assert '"state": "draft"' in json_str


def test_plan_roundtrip(tmp_path):
    """Test complete plan create, update, read cycle."""
    store = FilePlanStore(tmp_path)

    # Create
    plan = Plan(
        slug="roundtrip",
        objective="Test roundtrip",
        task_ids=["task-1", "task-2"],
        metadata={"key": "value"},
    )
    store.create(plan)

    # Read
    retrieved = store.get("roundtrip")
    assert retrieved.objective == "Test roundtrip"
    assert retrieved.task_ids == ["task-1", "task-2"]
    assert retrieved.metadata == {"key": "value"}

    # Update
    retrieved.task_ids.append("task-3")
    retrieved.metadata["new_key"] = "new_value"
    store.update(retrieved)

    # Verify update
    updated = store.get("roundtrip")
    assert updated.task_ids == ["task-1", "task-2", "task-3"]
    assert updated.metadata == {"key": "value", "new_key": "new_value"}
