"""Research Beads integrator for task management."""

from village.extensibility.beads_integrators import (
    BeadCreated,
    BeadsIntegrator,
    BeadSpec,
)


class ResearchBeadsIntegrator(BeadsIntegrator):
    """Beads integrator for research domain.

    Creates Beads tasks for research projects with metadata:
    - Research field
    - Methodology (qualitative/quantitative/mixed)
    - Number of sources
    - Research tags
    """

    def __init__(self) -> None:
        """Initialize research beads integrator."""

    async def should_create_bead(self, context: dict) -> bool:
        """Determine if bead should be created.

        Creates beads for research tasks.

        Args:
            context: Context dictionary with task info

        Returns:
            True if context contains research task
        """
        task_type = context.get("task_type", "")
        return "research" in task_type.lower() or "research" in str(context.values()).lower()

    async def create_bead_spec(self, context: dict) -> BeadSpec:
        """Create bead specification from context.

        Creates BeadSpec with research metadata:
        - research_field: Academic domain
        - methodology: qualitative/quantitative/mixed
        - sources: Number of sources cited

        Args:
            context: Context dictionary with task info

        Returns:
            BeadSpec for bead creation
        """
        title = context.get("title", "Research Task")
        description = context.get("description", "")

        research_field = self._extract_research_field(description)
        methodology = self._determine_methodology(description)
        sources = self._count_sources(description)

        tags = ["research", research_field.lower().replace(" ", "_")]

        metadata = {
            "research_field": research_field,
            "methodology": methodology,
            "sources": sources,
            "citation_style": "APA",
        }

        return BeadSpec(
            title=title,
            description=description,
            issue_type="task",
            priority=2,
            tags=tags,
            metadata=metadata,
        )

    async def on_bead_created(self, bead: BeadCreated, context: dict) -> None:
        """Handle bead creation.

        Logs bead creation to console.

        Args:
            bead: Created bead
            context: Original context
        """
        research_field = (
            bead.metadata.get("research_field", "Unknown") if bead.metadata else "Unknown"
        )
        print(f"[RESEARCH] Created bead {bead.bead_id} for {research_field} research")

    async def on_bead_updated(self, bead_id: str, updates: dict) -> None:
        """Handle bead update.

        Minimal implementation: does nothing.

        Args:
            bead_id: ID of updated bead
            updates: Dictionary of updates
        """
        pass

    def _extract_research_field(self, text: str) -> str:
        """Extract research field from text.

        Args:
            text: Text to analyze

        Returns:
            Research field name
        """
        common_fields = {
            "machine learning": "Machine Learning",
            "deep learning": "Deep Learning",
            "nlp": "Natural Language Processing",
            "computer vision": "Computer Vision",
            "ai safety": "AI Safety",
            "reinforcement learning": "Reinforcement Learning",
            "llm": "Large Language Models",
        }

        text_lower = text.lower()
        for keyword, field in common_fields.items():
            if keyword in text_lower:
                return field

        return "General Research"

    def _determine_methodology(self, text: str) -> str:
        """Determine research methodology from text.

        Args:
            text: Text to analyze

        Returns:
            Methodology (qualitative/quantitative/mixed)
        """
        text_lower = text.lower()

        qualitative_keywords = ["qualitative", "interview", "case study", "survey"]
        quantitative_keywords = ["quantitative", "experiment", "statistical", "data"]

        if any(kw in text_lower for kw in qualitative_keywords):
            return "qualitative"

        if any(kw in text_lower for kw in quantitative_keywords):
            return "quantitative"

        return "mixed"

    def _count_sources(self, text: str) -> int:
        """Count sources mentioned in text.

        Args:
            text: Text to analyze

        Returns:
            Number of sources
        """
        import re

        citation_patterns = [r"\[\d+\]", r"\(\w+,\s*\d{4}\)", r"\([^)]+\s+\d{4}\)"]
        count = 0

        for pattern in citation_patterns:
            matches = re.findall(pattern, text)
            count += len(matches)

        return count
