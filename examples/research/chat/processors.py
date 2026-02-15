"""Research chat processor for pre/post message processing."""

import re

from village.extensibility.processors import ChatProcessor


class ResearchChatProcessor(ChatProcessor):
    """Chat processor for research domain.

    Pre-processing: Extracts and normalizes research topics
    Post-processing: Adds citation formatting and source metadata
    """

    def __init__(self, citation_style: str = "APA") -> None:
        """Initialize research chat processor.

        Args:
            citation_style: Citation format (APA, MLA, Chicago)
        """
        self.citation_style = citation_style.upper()
        self._query_cache: dict[str, str] = {}

    async def pre_process(self, user_input: str) -> str:
        """Extract research topics and normalize query format.

        Args:
            user_input: Raw user input

        Returns:
            Normalized research query
        """
        normalized = user_input.strip()

        research_keywords = [
            "research",
            "study",
            "investigate",
            "analyze",
            "compare",
            "find papers",
            "literature review",
        ]

        is_research_query = any(keyword in normalized.lower() for keyword in research_keywords)

        if is_research_query:
            normalized = self._normalize_research_query(normalized)

        return normalized

    async def post_process(self, response: str) -> str:
        """Format response with citation styles and source metadata.

        Args:
            response: Raw LLM response

        Returns:
            Formatted response with citations
        """
        if self._has_citations(response):
            response = self._format_citations(response)

        return response

    def _normalize_research_query(self, query: str) -> str:
        """Normalize research query to standard format.

        Args:
            query: Research query

        Returns:
            Normalized query
        """
        query = re.sub(r"\s+", " ", query)
        query = query.strip()

        if not any(punct in query for punct in [".", "?", "!"]):
            if "research" not in query.lower():
                query = f"Research {query.lower()}"

        return query

    def _has_citations(self, response: str) -> bool:
        """Check if response contains citations.

        Args:
            response: Response to check

        Returns:
            True if citations detected
        """
        citation_patterns = [r"\[\d+\]", r"\(\w+,\s*\d{4}\)", r"\([^)]+\s+\d{4}\)"]
        return any(re.search(pattern, response) for pattern in citation_patterns)

    def _format_citations(self, response: str) -> str:
        """Format citations according to style.

        Args:
            response: Response with citations

        Returns:
            Response with formatted citations
        """
        if self.citation_style == "APA":
            response = re.sub(
                r"\[(\d+)\]",
                lambda m: f" (Source {m.group(1)})",
                response,
            )
        elif self.citation_style == "MLA":
            response = re.sub(
                r"\[(\d+)\]",
                lambda m: f" [{m.group(1)}]",
                response,
            )

        return response
