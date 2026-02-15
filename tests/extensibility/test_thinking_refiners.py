"""Test ThinkingRefiner ABC and DefaultThinkingRefiner."""

import pytest

from village.extensibility.thinking_refiners import (
    DefaultThinkingRefiner,
    QueryRefinement,
    ThinkingRefiner,
)


class TestQueryRefinement:
    """Test QueryRefinement dataclass."""

    def test_query_refinement_initialization(self):
        """Test QueryRefinement initialization with required fields."""
        refinement = QueryRefinement(
            original_query="test query", refined_steps=["step 1", "step 2"]
        )
        assert refinement.original_query == "test query"
        assert refinement.refined_steps == ["step 1", "step 2"]
        assert refinement.context_hints == {}

    def test_query_refinement_with_context_hints(self):
        """Test QueryRefinement initialization with context hints."""
        context = {"domain": "trading", "asset": "crypto"}
        refinement = QueryRefinement(
            original_query="test",
            refined_steps=["step"],
            context_hints=context,
        )
        assert refinement.context_hints == context

    def test_query_refinement_none_context_hints_becomes_empty_dict(self):
        """Test that None context_hints becomes empty dict via post_init."""
        refinement = QueryRefinement(
            original_query="test",
            refined_steps=["step"],
            context_hints=None,
        )
        assert refinement.context_hints == {}

    def test_query_refinement_empty_refined_steps(self):
        """Test QueryRefinement with empty refined_steps."""
        refinement = QueryRefinement(original_query="test query", refined_steps=[])
        assert refinement.refined_steps == []

    def test_query_refinement_context_hints_mutation(self):
        """Test that context_hints dict can be mutated."""
        refinement = QueryRefinement(original_query="test", refined_steps=["step"])
        refinement.context_hints["new_key"] = "new_value"
        assert refinement.context_hints == {"new_key": "new_value"}


class TestDefaultThinkingRefiner:
    """Test DefaultThinkingRefiner behavior."""

    @pytest.mark.asyncio
    async def test_should_refine_always_returns_false(self):
        """Test that should_refine always returns False."""
        refiner = DefaultThinkingRefiner()
        query = "test query"
        result = await refiner.should_refine(query)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_refine_with_empty_query(self):
        """Test should_refine with empty query."""
        refiner = DefaultThinkingRefiner()
        result = await refiner.should_refine("")
        assert result is False

    @pytest.mark.asyncio
    async def test_should_refine_with_complex_query(self):
        """Test should_refine with complex query."""
        refiner = DefaultThinkingRefiner()
        result = await refiner.should_refine(
            "Compare aggressive vs balanced strategies from last week"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_refine_query_returns_pass_through(self):
        """Test that refine_query returns pass-through with single step."""
        refiner = DefaultThinkingRefiner()
        query = "test query"
        result = await refiner.refine_query(query)

        assert isinstance(result, QueryRefinement)
        assert result.original_query == query
        assert result.refined_steps == [query]
        assert result.context_hints == {}

    @pytest.mark.asyncio
    async def test_refine_query_preserves_query_content(self):
        """Test that refine_query preserves query content."""
        refiner = DefaultThinkingRefiner()
        query = "Analyze the backtest results"
        result = await refiner.refine_query(query)

        assert result.original_query == query
        assert result.refined_steps[0] == query

    @pytest.mark.asyncio
    async def test_refine_query_with_multiline_query(self):
        """Test refine_query with multiline query."""
        refiner = DefaultThinkingRefiner()
        query = "Line 1\nLine 2\nLine 3"
        result = await refiner.refine_query(query)

        assert result.original_query == query
        assert result.refined_steps == [query]

    @pytest.mark.asyncio
    async def test_refine_query_with_special_chars(self):
        """Test refine_query with special characters."""
        refiner = DefaultThinkingRefiner()
        query = "Test with 🎉 emojis & code ```blocks```"
        result = await refiner.refine_query(query)

        assert result.original_query == query
        assert result.refined_steps == [query]


class TestCustomThinkingRefiner:
    """Test custom ThinkingRefiner implementations."""

    @pytest.mark.asyncio
    async def test_custom_refiner_conditionally_refines(self):
        """Test custom refiner that conditionally refines queries."""

        class ConditionalRefiner(ThinkingRefiner):
            async def should_refine(self, user_query: str) -> bool:
                return "vs" in user_query

            async def refine_query(self, user_query: str) -> QueryRefinement:
                if "vs" not in user_query:
                    return QueryRefinement(
                        original_query=user_query,
                        refined_steps=[user_query],
                    )
                parts = user_query.split("vs")
                return QueryRefinement(
                    original_query=user_query,
                    refined_steps=[
                        f"Analyze {parts[0].strip()}",
                        f"Analyze {parts[1].strip()}",
                        "Compare the results",
                    ],
                )

        refiner = ConditionalRefiner()

        simple_query = "Run a backtest"
        assert await refiner.should_refine(simple_query) is False
        result = await refiner.refine_query(simple_query)
        assert result.refined_steps == [simple_query]

        complex_query = "Analyze aggressive vs balanced strategies"
        assert await refiner.should_refine(complex_query) is True
        result = await refiner.refine_query(complex_query)
        assert len(result.refined_steps) == 3
        assert "aggressive" in result.refined_steps[0]
        assert "balanced" in result.refined_steps[1]
        assert "Compare" in result.refined_steps[2]

    @pytest.mark.asyncio
    async def test_custom_refiner_with_context_hints(self):
        """Test custom refiner that adds context hints."""

        class ContextAwareRefiner(ThinkingRefiner):
            async def should_refine(self, user_query: str) -> bool:
                return True

            async def refine_query(self, user_query: str) -> QueryRefinement:
                return QueryRefinement(
                    original_query=user_query,
                    refined_steps=[user_query],
                    context_hints={
                        "detected_intent": "trading",
                        "complexity": "low",
                    },
                )

        refiner = ContextAwareRefiner()
        result = await refiner.refine_query("test query")

        assert result.context_hints == {
            "detected_intent": "trading",
            "complexity": "low",
        }

    @pytest.mark.asyncio
    async def test_custom_refiner_multi_step_breakdown(self):
        """Test custom refiner with multi-step breakdown."""

        class TradingRefiner(ThinkingRefiner):
            async def should_refine(self, user_query: str) -> bool:
                return "compare" in user_query.lower()

            async def refine_query(self, user_query: str) -> QueryRefinement:
                if "compare" not in user_query.lower():
                    return QueryRefinement(
                        original_query=user_query,
                        refined_steps=[user_query],
                    )
                return QueryRefinement(
                    original_query=user_query,
                    refined_steps=[
                        "Identify the strategies to compare",
                        "Gather performance metrics for each strategy",
                        "Analyze Sharpe ratios and drawdowns",
                        "Compare hit rates and profitability",
                        "Summarize findings and provide recommendation",
                    ],
                    context_hints={"analysis_type": "comparative"},
                )

        refiner = TradingRefiner()

        simple_query = "Run a test"
        assert await refiner.should_refine(simple_query) is False

        compare_query = "Compare strategy A with strategy B"
        assert await refiner.should_refine(compare_query) is True
        result = await refiner.refine_query(compare_query)

        assert len(result.refined_steps) == 5
        assert result.context_hints == {"analysis_type": "comparative"}

    @pytest.mark.asyncio
    async def test_custom_refiner_with_state(self):
        """Test custom refiner that maintains state."""

        class StatefulRefiner(ThinkingRefiner):
            def __init__(self):
                self.query_count = 0

            async def should_refine(self, user_query: str) -> bool:
                return self.query_count < 3

            async def refine_query(self, user_query: str) -> QueryRefinement:
                self.query_count += 1
                return QueryRefinement(
                    original_query=user_query,
                    refined_steps=[
                        f"Step 1: {user_query}",
                        f"Step 2: Analyze {user_query}",
                    ],
                )

        refiner = StatefulRefiner()

        query1 = await refiner.refine_query("query 1")
        assert len(query1.refined_steps) == 2
        assert await refiner.should_refine("query") is True

        query2 = await refiner.refine_query("query 2")
        assert len(query2.refined_steps) == 2
        assert await refiner.should_refine("query") is True

        query3 = await refiner.refine_query("query 3")
        assert len(query3.refined_steps) == 2
        assert await refiner.should_refine("query") is False

        assert refiner.query_count == 3


class TestThinkingRefinerABC:
    """Test that ThinkingRefiner ABC cannot be instantiated directly."""

    def test_thinking_refiner_cannot_be_instantiated(self):
        """Test that abstract ThinkingRefiner cannot be instantiated."""
        with pytest.raises(TypeError):
            ThinkingRefiner()

    def test_custom_refiner_must_implement_all_methods(self):
        """Test that custom refiner must implement all abstract methods."""

        class IncompleteRefiner(ThinkingRefiner):
            async def should_refine(self, user_query: str) -> bool:
                return True

        with pytest.raises(TypeError):
            IncompleteRefiner()
