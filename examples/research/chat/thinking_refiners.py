"""Research thinking refiner for query breakdown."""

from village.extensibility.thinking_refiners import QueryRefinement, ThinkingRefiner


class ResearchThinkingRefiner(ThinkingRefiner):
    """Thinking refiner for research domain.

    Breaks down research queries into systematic steps:
    1. Define research question
    2. Identify key terms and concepts
    3. Search academic databases
    4. Analyze and synthesize findings
    5. Generate citations and bibliography
    """

    def __init__(self) -> None:
        """Initialize research thinking refiner."""
        self._research_keywords = [
            "research",
            "study",
            "investigate",
            "analyze",
            "compare",
            "find papers",
            "literature review",
            "explore",
            "examine",
            "evaluate",
        ]

    async def should_refine(self, user_query: str) -> bool:
        """Determine if query is research-related.

        Args:
            user_query: User's query

        Returns:
            True if query is research-related
        """
        query_lower = user_query.lower()
        return any(keyword in query_lower for keyword in self._research_keywords)

    async def refine_query(self, user_query: str) -> QueryRefinement:
        """Refine research query into systematic steps.

        Args:
            user_query: User's research query

        Returns:
            QueryRefinement with research steps
        """
        research_field = self._extract_research_field(user_query)

        steps = [
            f"Define the research question: {user_query}",
            "Identify key terms, concepts, and search queries",
            "Search academic databases (Google Scholar, arXiv, etc.)",
            "Analyze and synthesize findings from multiple sources",
            "Generate citations and bibliography in appropriate format",
        ]

        context_hints = {
            "required_data_sources": ["knowledge_store", "perplexity"],
            "domain_context": {"research_field": research_field},
        }

        return QueryRefinement(
            original_query=user_query,
            refined_steps=steps,
            context_hints=context_hints,
        )

    def _extract_research_field(self, query: str) -> str:
        """Extract research field from query.

        Args:
            query: Research query

        Returns:
            Research field name
        """
        query_lower = query.lower()

        common_fields = {
            "machine learning": "Machine Learning",
            "deep learning": "Deep Learning",
            "nlp": "Natural Language Processing",
            "computer vision": "Computer Vision",
            "ai safety": "AI Safety",
            "reinforcement learning": "Reinforcement Learning",
            "supervised learning": "Supervised Learning",
            "llm": "Large Language Models",
            "quantum": "Quantum Computing",
            "blockchain": "Blockchain",
        }

        for keyword, field in common_fields.items():
            if keyword in query_lower:
                return field

        return "General Research"
