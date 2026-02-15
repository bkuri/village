"""Task specification dataclass for Village Chat."""

import logging
from dataclasses import dataclass
from typing import Literal

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
