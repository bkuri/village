"""Thinking refiners for domain-specific query refinement."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class QueryRefinement:
    """Refined query with analysis steps."""

    original_query: str
    refined_steps: list[str]
    context_hints: dict[str, object] = None

    def __post_init__(self) -> None:
        """Initialize context_hints if not provided."""
        if self.context_hints is None:
            self.context_hints = {}


class ThinkingRefiner(ABC):
    """Base class for domain-specific query refinement.

    Allows domains to break down vague or complex user queries into
    structured analysis steps using sequential thinking.

    Example:
        class TradingThinkingRefiner(ThinkingRefiner):
            async def refine_query(self, user_query: str) -> QueryRefinement:
                # Break "was aggressive better?" into analysis steps:
                # 1. Compare aggressive vs balanced risk profiles
                # 2. Analyze Sharpe ratios and drawdowns
                # 3. Check hit rate to 2x profit goal
                return QueryRefinement(
                    original_query=user_query,
                    refined_steps=[...],
                    context_hints={"asset_class": "crypto"}
                )
    """

    @abstractmethod
    async def should_refine(self, user_query: str) -> bool:
        """Determine if query needs refinement.

        Args:
            user_query: User's query

        Returns:
            True if query should be refined, False to use as-is
        """
        pass

    @abstractmethod
    async def refine_query(self, user_query: str) -> QueryRefinement:
        """Refine user query into analysis steps.

        Args:
            user_query: User's query

        Returns:
            QueryRefinement with refined steps and hints
        """
        pass


class DefaultThinkingRefiner(ThinkingRefiner):
    """Default no-op thinking refiner."""

    async def should_refine(self, user_query: str) -> bool:
        """Never refine queries."""
        return False

    async def refine_query(self, user_query: str) -> QueryRefinement:
        """Return query as single step."""
        return QueryRefinement(
            original_query=user_query,
            refined_steps=[user_query],
        )
