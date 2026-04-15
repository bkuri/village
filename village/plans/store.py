"""Plan storage with CRUD operations."""

import json
import shutil
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from village.plans.models import Plan, PlanState


class PlanNotFoundError(Exception):
    """Raised when a plan is not found."""

    def __init__(self, slug: str) -> None:
        self.slug = slug
        super().__init__(f"Plan '{slug}' not found")


class SlugCollisionError(Exception):
    """Raised when a slug already exists."""

    def __init__(self, slug: str) -> None:
        self.slug = slug
        super().__init__(f"Plan '{slug}' already exists")


class PlanStore(ABC):
    """Abstract plan storage interface."""

    @abstractmethod
    def create(self, plan: Plan) -> Plan:
        """Create a new plan. Raises SlugCollisionError if slug exists."""

    @abstractmethod
    def get(self, slug: str) -> Plan:
        """Get a plan by slug. Raises PlanNotFoundError if not found."""

    @abstractmethod
    def update(self, plan: Plan) -> Plan:
        """Update an existing plan."""

    @abstractmethod
    def delete(self, slug: str) -> None:
        """Delete a plan."""

    @abstractmethod
    def list(self, state: PlanState | None = None) -> list[Plan]:
        """List plans, optionally filtered by state."""

    @abstractmethod
    def exists(self, slug: str) -> bool:
        """Check if a plan exists."""


class FilePlanStore(PlanStore):
    """JSON-based plan storage in .village/plans/{drafts,approved}/."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.drafts_dir = base_dir / "drafts"
        self.approved_dir = base_dir / "approved"

    def _plan_path(self, slug: str, state: PlanState) -> Path:
        """Get the path for a plan's JSON file."""
        dir_path = self.drafts_dir if state == PlanState.DRAFT else self.approved_dir
        return dir_path / slug / "plan.json"

    def _ensure_dirs(self) -> None:
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        self.approved_dir.mkdir(parents=True, exist_ok=True)

    def _get_plan_dir(self, slug: str, state: PlanState) -> Path:
        """Get the plan directory based on state."""
        if state == PlanState.DRAFT:
            return self.drafts_dir / slug
        return self.approved_dir / slug

    def create(self, plan: Plan) -> Plan:
        self._ensure_dirs()
        if self.exists(plan.slug):
            raise SlugCollisionError(plan.slug)

        dir_path = self._get_plan_dir(plan.slug, plan.state)
        dir_path.mkdir(parents=True, exist_ok=True)

        plan_path = dir_path / "plan.json"
        plan_path.write_text(plan.to_json(), encoding="utf-8")

        return plan

    def get(self, slug: str) -> Plan:
        for state in PlanState:
            if state in (PlanState.LANDED, PlanState.ABORTED, PlanState.PURGED):
                continue
            path = self._plan_path(slug, state)
            if path.exists():
                data = path.read_text(encoding="utf-8")
                return Plan.from_dict(json.loads(data))

        raise PlanNotFoundError(slug)

    def update(self, plan: Plan) -> Plan:
        if not self.exists(plan.slug):
            raise PlanNotFoundError(plan.slug)

        plan.updated_at = datetime.now(timezone.utc)

        # Check if we need to move the directory (DRAFT -> APPROVED)
        draft_path = self.drafts_dir / plan.slug
        approved_path = self.approved_dir / plan.slug

        # If plan is in drafts dir but state is not DRAFT, move it
        if draft_path.exists() and plan.state != PlanState.DRAFT:
            # Move from drafts to approved
            if approved_path.exists():
                # Clean up existing approved dir first
                shutil.rmtree(approved_path)
            shutil.move(str(draft_path), str(approved_path))
        # If plan is in approved dir but state is DRAFT, move it back
        elif approved_path.exists() and plan.state == PlanState.DRAFT:
            if draft_path.exists():
                shutil.rmtree(draft_path)
            shutil.move(str(approved_path), str(draft_path))

        dir_path = self._get_plan_dir(plan.slug, plan.state)
        dir_path.mkdir(parents=True, exist_ok=True)

        plan_path = dir_path / "plan.json"
        plan_path.write_text(plan.to_json(), encoding="utf-8")

        return plan

    def delete(self, slug: str) -> None:
        for state in PlanState:
            if state == PlanState.DRAFT:
                path = self.drafts_dir / slug
            else:
                path = self.approved_dir / slug
            if path.exists():
                shutil.rmtree(path)
                return
        raise PlanNotFoundError(slug)

    def list(self, state: PlanState | None = None) -> list[Plan]:
        self._ensure_dirs()
        plans = []

        dirs_to_check = []
        if state is None or state == PlanState.DRAFT:
            dirs_to_check.append(self.drafts_dir)
        if state is None or state not in (PlanState.DRAFT,):
            dirs_to_check.append(self.approved_dir)

        for dir_path in dirs_to_check:
            if not dir_path.exists():
                continue
            for plan_dir in dir_path.iterdir():
                if not plan_dir.is_dir():
                    continue
                plan_path = plan_dir / "plan.json"
                if plan_path.exists():
                    try:
                        data = plan_path.read_text(encoding="utf-8")
                        plan = Plan.from_dict(json.loads(data))
                        if state is None or plan.state == state:
                            plans.append(plan)
                    except Exception:
                        continue

        return sorted(plans, key=lambda p: p.created_at, reverse=True)

    def exists(self, slug: str) -> bool:
        return (self.drafts_dir / slug).exists() or (self.approved_dir / slug).exists()
