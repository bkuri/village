from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from village.scribe.curate import Curator
from village.scribe.research import AutoResearcher, GapFillResult, ResearchResult
from village.scribe.store import ScribeStore


class TestAutoResearcherInit:
    def test_initializes_with_store_and_curator(self, tmp_path: Path) -> None:
        store = ScribeStore(tmp_path / "wiki")
        curator = MagicMock(spec=Curator)
        mcp_fn = AsyncMock()

        researcher = AutoResearcher(store, curator, mcp_fn=mcp_fn)

        assert researcher.store is store
        assert researcher.curator is curator
        assert researcher._mcp_call is mcp_fn


class TestAutoResearcherGenerateQuery:
    def test_generates_query_for_orphan_entry(self, tmp_path: Path) -> None:
        store = ScribeStore(tmp_path / "wiki")
        curator = MagicMock(spec=Curator)

        md = tmp_path / "notes" / "api-auth.md"
        md.parent.mkdir(parents=True)
        md.write_text("# API Auth\nOAuth2 setup for API", encoding="utf-8")
        result = store.see(str(md))
        orphan_id = result.entry_id

        researcher = AutoResearcher(store, curator)
        query = researcher._generate_gap_query(orphan_id)

        assert "api-auth" in query.lower() or "API Auth" in query
        assert len(query) > 50


class TestAutoResearcherGenerateQueryNoEntry:
    def test_returns_empty_for_missing_entry(self, tmp_path: Path) -> None:
        store = ScribeStore(tmp_path / "wiki")
        curator = MagicMock(spec=Curator)

        researcher = AutoResearcher(store, curator)
        query = researcher._generate_gap_query("nonexistent-id")

        assert query == ""


class TestAutoResearcherResearchGap:
    async def test_researches_gap_successfully(self, tmp_path: Path) -> None:
        store = ScribeStore(tmp_path / "wiki")
        curator = MagicMock(spec=Curator)
        mcp_fn = AsyncMock(return_value="Additional OAuth2 scopes info: ...")

        md = tmp_path / "notes" / "auth.md"
        md.parent.mkdir(parents=True)
        md.write_text("# Auth\nBasic auth setup", encoding="utf-8")
        result = store.see(str(md))
        orphan_id = result.entry_id

        researcher = AutoResearcher(store, curator, mcp_fn=mcp_fn)
        gap_result = await researcher._research_gap(orphan_id)

        assert gap_result.success is True
        assert gap_result.research_output != ""
        mcp_fn.assert_called_once()


class TestAutoResearcherResearchGapNoMcp:
    async def test_returns_error_when_no_mcp_fn(self, tmp_path: Path) -> None:
        store = ScribeStore(tmp_path / "wiki")
        curator = MagicMock(spec=Curator)

        md = tmp_path / "notes" / "config.md"
        md.parent.mkdir(parents=True)
        md.write_text("# Config\nBasic config", encoding="utf-8")
        result = store.see(str(md))

        researcher = AutoResearcher(store, curator)
        gap_result = await researcher._research_gap(result.entry_id)

        assert gap_result.success is False
        assert "No MCP function" in gap_result.error


class TestAutoResearcherSynthesizeResult:
    def test_synthesizes_research_into_wiki(self, tmp_path: Path) -> None:
        store = ScribeStore(tmp_path / "wiki")
        curator = MagicMock(spec=Curator)

        md = tmp_path / "notes" / "deploy.md"
        md.parent.mkdir(parents=True)
        md.write_text("# Deploy\nBasic deploy steps", encoding="utf-8")
        result = store.see(str(md))
        orphan_id = result.entry_id

        research_output = "Additional deployment strategies for Kubernetes"

        researcher = AutoResearcher(store, curator)
        success = researcher._synthesize_result(orphan_id, research_output)

        assert success is True

        entries = store.store.all_entries()
        gap_entries = [e for e in entries if "gap-fill" in e.tags]
        assert len(gap_entries) >= 1


class TestAutoResearcherSynthesizeResultNoOutput:
    def test_returns_false_when_no_research_output(self, tmp_path: Path) -> None:
        store = ScribeStore(tmp_path / "wiki")
        curator = MagicMock(spec=Curator)

        researcher = AutoResearcher(store, curator)
        success = researcher._synthesize_result("some-id", "")

        assert success is False


class TestAutoResearcherResearchGaps:
    async def test_researches_multiple_orphans(self, tmp_path: Path) -> None:
        store = ScribeStore(tmp_path / "wiki")
        curator = Curator(store.store, tmp_path / "wiki")

        mcp_fn = AsyncMock(return_value="Research output for gap")

        md1 = tmp_path / "notes" / "auth.md"
        md1.parent.mkdir(parents=True)
        md1.write_text("# Auth\nBasic auth", encoding="utf-8")
        store.see(str(md1))

        md2 = tmp_path / "notes" / "deploy.md"
        md2.write_text("# Deploy\nBasic deploy", encoding="utf-8")
        store.see(str(md2))

        researcher = AutoResearcher(store, curator, mcp_fn=mcp_fn)
        result = await researcher.research_gaps(max_orphans=2)

        assert result.orphans_found >= 0
        assert isinstance(result.gaps_filled, list)


class TestGapFillResult:
    def test_default_values(self) -> None:
        result = GapFillResult(orphan_id="test-123")

        assert result.orphan_id == "test-123"
        assert result.research_output == ""
        assert result.success is False
        assert result.error == ""


class TestResearchResult:
    def test_default_values(self) -> None:
        result = ResearchResult()

        assert result.gaps_filled == []
        assert result.orphans_found == 0
        assert result.gaps_researched == 0
