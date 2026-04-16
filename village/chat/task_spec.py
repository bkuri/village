"""Task specification dataclass for Village Chat."""

import logging
from dataclasses import dataclass, field
from typing import Any, Literal, cast

logger = logging.getLogger(__name__)


@dataclass
class TaskSpec:
    """Structured task specification with dependency tracking."""

    title: str
    description: str
    scope: Literal["fix", "feature", "config", "docs", "test", "refactor"]
    blocks: list[str]
    blocked_by: list[str]
    success_criteria: list[str]
    estimate: str
    confidence: Literal["high", "medium", "low"] = "medium"
    bump: Literal["major", "minor", "patch", "none"] | None = None
    search_hints: dict[str, list[str]] = field(default_factory=dict)

    def has_dependencies(self) -> bool:
        """
        Check if task has any dependencies.

        Returns:
            True if task blocks or is blocked by other tasks
        """
        return bool(self.blocks) or bool(self.blocked_by)

    def dependency_summary(self) -> str:
        """
        Generate a summary of task dependencies.

        Returns:
            Formatted dependency summary string
        """
        if not self.has_dependencies():
            return "No dependencies"

        parts = []
        if self.blocked_by:
            blocked_str = ", ".join(self.blocked_by)
            parts.append(f"blocked by: {blocked_str}")
        if self.blocks:
            blocks_str = ", ".join(self.blocks)
            parts.append(f"blocks: {blocks_str}")

        return "; ".join(parts)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TaskSpec":
        """Create TaskSpec from a dict, with safe defaults for missing fields."""
        return cls(
            title=str(d.get("title", "")),
            description=str(d.get("description", "")),
            scope=cast(Literal["fix", "feature", "config", "docs", "test", "refactor"], str(d.get("scope", "feature"))),
            blocks=list(d.get("blocks") or []),
            blocked_by=list(d.get("blocked_by") or []),
            success_criteria=list(d.get("success_criteria") or []),
            estimate=str(d.get("estimate", "unknown")),
            confidence=cast(Literal["high", "medium", "low"], str(d.get("confidence", "medium"))),
            search_hints=dict(d.get("search_hints") or {}),
        )
