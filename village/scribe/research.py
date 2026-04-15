"""Auto-research engine for gap-filling in the Scribe knowledge base."""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from village.scribe.curate import Curator
from village.scribe.store import ScribeStore

logger = logging.getLogger(__name__)


@dataclass
class GapFillResult:
    orphan_id: str
    research_output: str = ""
    success: bool = False
    error: str = ""


@dataclass
class ResearchResult:
    gaps_filled: list[GapFillResult] = field(default_factory=list)
    orphans_found: int = 0
    gaps_researched: int = 0


class AutoResearcher:
    """Autonomous research for filling knowledge gaps in the wiki."""

    def __init__(
        self,
        store: ScribeStore,
        curator: Curator,
        mcp_fn: Optional[Callable[[Any, Any], Any]] = None,
    ) -> None:
        self.store = store
        self.curator = curator
        self._mcp_call = mcp_fn

    def _generate_gap_query(self, orphan_id: str) -> str:
        """Generate a research query for an orphan entry's knowledge gaps."""
        entry = self.store.store.get(orphan_id)
        if not entry:
            return ""

        title = entry.title
        text_preview = entry.text[:500] if entry.text else ""

        query = f"""Research what information is missing or could be added to enrich the topic: "{title}".

Current content summary:
{text_preview}

Provide 2-3 specific aspects that should be added or updated."""
        return query

    async def _research_gap(self, orphan_id: str) -> GapFillResult:
        """Research a single orphan entry."""
        result = GapFillResult(orphan_id=orphan_id)

        query = self._generate_gap_query(orphan_id)
        if not query:
            result.error = "Could not generate query"
            return result

        if not self._mcp_call:
            result.error = "No MCP function configured"
            return result

        try:
            research_output = await self._mcp_call("perplexity", query)
            result.research_output = str(research_output)
            result.success = True
        except Exception as e:
            result.error = str(e)
            logger.warning(f"Research failed for {orphan_id}: {e}")

        return result

    def _synthesize_result(self, orphan_id: str, research_output: str) -> bool:
        """Synthesize research result back into wiki."""
        if not research_output:
            return False

        entry = self.store.store.get(orphan_id)
        if not entry:
            return False

        tags = ["synthesized", "gap-fill", f"parent:{orphan_id}"]
        self.store.store.put(
            title=f"Gap Fill: {entry.title}",
            text=research_output,
            tags=tags,
            metadata={
                "synthesized_from": orphan_id,
                "type": "gap-fill",
            },
        )
        return True

    async def research_gaps(
        self,
        max_orphans: int = 5,
    ) -> ResearchResult:
        """Run auto-research on orphan entries."""
        result = ResearchResult()

        curate_result = self.curator.curate(check_urls=False)
        orphan_ids = curate_result.orphans[:max_orphans]
        result.orphans_found = len(orphan_ids)

        for orphan_id in orphan_ids:
            gap_result = await self._research_gap(orphan_id)
            result.gaps_filled.append(gap_result)

            if gap_result.success and gap_result.research_output:
                self._synthesize_result(orphan_id, gap_result.research_output)
                result.gaps_researched += 1

        return result
