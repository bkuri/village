"""Tests for Scribe curation engine."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import httpx

from village.memory import MemoryStore
from village.scribe.curate import CurateResult, Curator


class TestFindOrphans:
    def test_finds_entry_with_no_inbound_refs(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="Orphan", text="no one links here", entry_id="orphan-1")
        store.put(title="Referenced", text="linked by another", entry_id="ref-1")

        store.put(
            title="Linker",
            text="links to ref-1",
            entry_id="linker-1",
            metadata={"related": "ref-1"},
        )

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        orphans = curator.find_orphans()

        assert "orphan-1" in orphans
        assert "linker-1" in orphans
        assert "ref-1" not in orphans

    def test_no_orphans_when_fully_connected(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="A", text="a", entry_id="a", metadata={"related": "b"})
        store.put(title="B", text="b", entry_id="b", metadata={"related": "a"})

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        orphans = curator.find_orphans()

        assert orphans == []

    def test_disconnected_graph_returns_no_orphans(self, tmp_path: Path) -> None:
        """When no entries have related metadata, the graph is disconnected.

        Orphan detection is meaningless in a disconnected graph — return
        an empty list instead of flagging every entry.
        """
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="Solo 1", text="s1", entry_id="solo-1")
        store.put(title="Solo 2", text="s2", entry_id="solo-2")

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        orphans = curator.find_orphans()

        assert orphans == []

    def test_single_entry_returns_no_orphans(self, tmp_path: Path) -> None:
        """A wiki with a single entry should never report it as an orphan."""
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="Only", text="solo", entry_id="only-1")

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        orphans = curator.find_orphans()

        assert orphans == []

    def test_related_as_list(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="Hub", text="hub", entry_id="hub", metadata={"related": ["a", "b"]})
        store.put(title="A", text="a", entry_id="a")
        store.put(title="B", text="b", entry_id="b")

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        orphans = curator.find_orphans()

        assert "hub" in orphans
        assert "a" not in orphans
        assert "b" not in orphans


class TestFindStale:
    def test_finds_old_entries(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        old_date = datetime.now(timezone.utc) - timedelta(days=120)

        store.put(title="Old entry", text="stale", entry_id="old-1", metadata={"created": old_date.isoformat()})

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        stale = curator.find_stale(max_age_days=90)

        assert len(stale) == 1
        assert stale[0].entry_id == "old-1"
        assert stale[0].age_days >= 120

    def test_no_stale_when_all_recent(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="Fresh", text="recent", entry_id="fresh-1")

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        stale = curator.find_stale(max_age_days=90)

        assert stale == []

    def test_mixed_old_and_new(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        old_date = datetime.now(timezone.utc) - timedelta(days=100)
        store.put(title="Old", text="old", entry_id="old-1", metadata={"created": old_date.isoformat()})
        store.put(title="New", text="new", entry_id="new-1")

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        stale = curator.find_stale(max_age_days=90)

        assert len(stale) == 1
        assert stale[0].entry_id == "old-1"


class TestCheckLinks:
    def test_reports_broken_link(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(
            title="Bad link",
            text="links to broken url",
            entry_id="bad-1",
            metadata={"source": "https://example.invalid/page"},
        )

        curator = Curator(store, tmp_path / "wiki", tmp_path)

        with patch("village.scribe.curate.httpx.head") as mock_head:
            mock_head.side_effect = httpx.ConnectError("connection refused")
            broken = curator.check_links()

        assert len(broken) == 1
        assert broken[0].entry_id == "bad-1"
        assert broken[0].status_code is None
        assert "connection refused" in broken[0].error

    def test_reports_404(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(
            title="Gone",
            text="page removed",
            entry_id="gone-1",
            metadata={"source": "https://example.com/deleted"},
        )

        curator = Curator(store, tmp_path / "wiki", tmp_path)

        with patch("village.scribe.curate.httpx.head") as mock_head:
            mock_head.return_value = httpx.Response(
                status_code=404, request=httpx.Request("HEAD", "https://example.com/deleted")
            )
            broken = curator.check_links()

        assert len(broken) == 1
        assert broken[0].status_code == 404

    def test_skips_non_url_sources(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="Local", text="local ref", entry_id="local-1", metadata={"source": "/local/path"})
        store.put(title="No source", text="no ref", entry_id="nosrc-1")

        curator = Curator(store, tmp_path / "wiki", tmp_path)

        with patch("village.scribe.curate.httpx.head") as mock_head:
            broken = curator.check_links()

        mock_head.assert_not_called()
        assert broken == []

    def test_healthy_link_not_reported(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(
            title="Good",
            text="valid link",
            entry_id="good-1",
            metadata={"source": "https://example.com/ok"},
        )

        curator = Curator(store, tmp_path / "wiki", tmp_path)

        with patch("village.scribe.curate.httpx.head") as mock_head:
            mock_head.return_value = httpx.Response(
                status_code=200, request=httpx.Request("HEAD", "https://example.com/ok")
            )
            broken = curator.check_links()

        assert broken == []


class TestGenerateVoice:
    def test_creates_voice_md(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="Test entry", text="some content", entry_id="t-1")

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        result = curator.generate_voice()

        assert result is True
        voice_path = tmp_path / "VOICE.md"
        assert voice_path.exists()
        content = voice_path.read_text(encoding="utf-8")
        assert "# Village Voice" in content

    def test_empty_store_returns_false(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        result = curator.generate_voice()

        assert result is False
        assert not (tmp_path / "VOICE.md").exists()

    def test_contains_recent_activity(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="First", text="content", entry_id="e-1")
        store.put(title="Second", text="content", entry_id="e-2")

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        curator.generate_voice()

        content = (tmp_path / "VOICE.md").read_text(encoding="utf-8")
        assert "## Recent Activity" in content
        assert "First" in content
        assert "Second" in content

    def test_contains_wiki_index(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="Indexed", text="content", entry_id="idx-1")

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        curator.generate_voice()

        content = (tmp_path / "VOICE.md").read_text(encoding="utf-8")
        assert "## Wiki Index" in content
        assert "[idx-1]" in content

    def test_contains_conventions(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(
            title="Use snake_case", text="Always use snake_case for functions", entry_id="conv-1", tags=["convention"]
        )

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        curator.generate_voice()

        content = (tmp_path / "VOICE.md").read_text(encoding="utf-8")
        assert "## Conventions" in content
        assert "Always use snake_case for functions" in content

    def test_contains_gotchas(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="Watch out", text="tmux pane IDs change on reload", entry_id="gotcha-1", tags=["gotcha"])

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        curator.generate_voice()

        content = (tmp_path / "VOICE.md").read_text(encoding="utf-8")
        assert "## Known Gotchas" in content
        assert "tmux pane IDs change on reload" in content


class TestCurate:
    def test_combines_all_checks(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        old_date = datetime.now(timezone.utc) - timedelta(days=120)
        store.put(title="Orphan", text="alone", entry_id="orph-1", metadata={"created": old_date.isoformat()})
        store.put(title="Fresh", text="recent", entry_id="fresh-1")

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        result = curator.curate(check_urls=False)

        assert isinstance(result, CurateResult)
        assert result.total_entries == 2
        assert result.orphans == []  # disconnected graph → no orphans
        assert len(result.stale_entries) == 1
        assert result.voice_updated is True
        assert result.broken_links == []

    def test_includes_url_check(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(
            title="Bad url",
            text="broken",
            entry_id="url-1",
            metadata={"source": "https://example.invalid/page"},
        )

        curator = Curator(store, tmp_path / "wiki", tmp_path)

        with patch("village.scribe.curate.httpx.head") as mock_head:
            mock_head.side_effect = httpx.ConnectError("fail")
            result = curator.curate(check_urls=True)

        assert len(result.broken_links) == 1
        assert result.broken_links[0].entry_id == "url-1"


class TestRebuildIndexExclude:
    def test_excludes_ids_from_index(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="Keep", text="active", entry_id="keep-1")
        store.put(title="Exclude", text="orphan", entry_id="orph-1")
        store.put(title="Also keep", text="active", entry_id="keep-2")

        store.rebuild_index(exclude={"orph-1"})

        index = (tmp_path / "wiki" / "index.md").read_text(encoding="utf-8")
        assert "keep-1" in index
        assert "keep-2" in index
        assert "orph-1" not in index

    def test_no_exclude_includes_all(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="A", text="a", entry_id="a-1")
        store.put(title="B", text="b", entry_id="b-1")

        store.rebuild_index()

        index = (tmp_path / "wiki" / "index.md").read_text(encoding="utf-8")
        assert "a-1" in index
        assert "b-1" in index

    def test_exclude_nonexistent_id_is_noop(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="A", text="a", entry_id="a-1")

        store.rebuild_index(exclude={"nonexistent"})

        index = (tmp_path / "wiki" / "index.md").read_text(encoding="utf-8")
        assert "a-1" in index

    def test_exclude_empty_set_includes_all(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="A", text="a", entry_id="a-1")

        store.rebuild_index(exclude=set())

        index = (tmp_path / "wiki" / "index.md").read_text(encoding="utf-8")
        assert "a-1" in index


class TestArchiveOrphans:
    def test_writes_orphans_md(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir(parents=True, exist_ok=True)

        store.put(title="Orphan page", text="alone", entry_id="orph-1", tags=["old"])
        store.put(title="Active", text="linked", entry_id="act-1")

        curator = Curator(store, wiki_path, tmp_path)
        archived, written = curator._archive_orphans(["orph-1"])

        assert archived == ["orph-1"]
        assert written is True

        orphans_md = wiki_path / "ORPHANS.md"
        assert orphans_md.exists()
        content = orphans_md.read_text(encoding="utf-8")
        assert "# Orphaned Entries" in content
        assert "orph-1" in content
        assert "Orphan page" in content
        assert "old" in content

    def test_orphans_md_has_table_format(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir(parents=True, exist_ok=True)

        store.put(
            title="Lonely",
            text="content",
            entry_id="lonely-1",
            metadata={"source": "https://example.com/doc"},
        )

        curator = Curator(store, wiki_path, tmp_path)
        curator._archive_orphans(["lonely-1"])

        content = (wiki_path / "ORPHANS.md").read_text(encoding="utf-8")
        assert "| ID | Title | Source | Age (days) | Tags |" in content
        assert "https://example.com/doc" in content

    def test_orphans_md_has_restore_note(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir(parents=True, exist_ok=True)

        store.put(title="Orphan", text="content", entry_id="o-1")

        curator = Curator(store, wiki_path, tmp_path)
        curator._archive_orphans(["o-1"])

        content = (wiki_path / "ORPHANS.md").read_text(encoding="utf-8")
        assert "excluded from the active wiki index" in content

    def test_empty_orphans_returns_empty(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir(parents=True, exist_ok=True)

        curator = Curator(store, wiki_path, tmp_path)
        archived, written = curator._archive_orphans([])

        assert archived == []
        assert written is False
        assert not (wiki_path / "ORPHANS.md").exists()

    def test_entry_files_not_deleted(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        wiki_path = tmp_path / "wiki"
        wiki_path.mkdir(parents=True, exist_ok=True)

        store.put(title="Orphan", text="content", entry_id="orph-1")

        curator = Curator(store, wiki_path, tmp_path)
        curator._archive_orphans(["orph-1"])

        entry_file = wiki_path / "entries" / "orph-1.md"
        assert entry_file.exists()


class TestCurateFix:
    def test_fix_false_does_nothing(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="Orphan", text="alone", entry_id="orph-1")

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        result = curator.curate(fix=False, check_urls=False)

        assert result.orphans_archived == []
        assert result.orphans_md_written is False
        assert result.curate_log == []
        assert not (tmp_path / "wiki" / "ORPHANS.md").exists()

    def test_fix_true_archives_orphans(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        wiki_path = tmp_path / "wiki"

        store.put(title="Active", text="linked", entry_id="act-1", metadata={"related": "orph-1"})
        store.put(title="Orphan", text="alone", entry_id="orph-1")

        curator = Curator(store, wiki_path, tmp_path)
        result = curator.curate(fix=True, check_urls=False)

        assert "orph-1" not in result.orphans
        assert "act-1" in result.orphans
        assert "act-1" in result.orphans_archived
        assert result.orphans_md_written is True
        assert (wiki_path / "ORPHANS.md").exists()

    def test_fix_excludes_orphans_from_voice(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        wiki_path = tmp_path / "wiki"

        store.put(title="Active", text="linked", entry_id="act-1", metadata={"related": "linked-1"})
        store.put(title="Linked", text="connected", entry_id="linked-1", metadata={"related": "act-1"})
        store.put(title="Orphan", text="alone", entry_id="orph-1")

        curator = Curator(store, wiki_path, tmp_path)
        curator.curate(fix=True, check_urls=False)

        voice = (tmp_path / "VOICE.md").read_text(encoding="utf-8")
        assert "act-1" in voice
        assert "linked-1" in voice
        assert "orph-1" not in voice

    def test_fix_excludes_orphans_from_index(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        wiki_path = tmp_path / "wiki"

        store.put(title="Active", text="linked", entry_id="act-1", metadata={"related": "linked-1"})
        store.put(title="Linked", text="connected", entry_id="linked-1", metadata={"related": "act-1"})
        store.put(title="Orphan", text="alone", entry_id="orph-1")

        curator = Curator(store, wiki_path, tmp_path)
        curator.curate(fix=True, check_urls=False)

        index = (wiki_path / "index.md").read_text(encoding="utf-8")
        assert "act-1" in index
        assert "linked-1" in index
        assert "orph-1" not in index

    def test_fix_populates_curate_log(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        wiki_path = tmp_path / "wiki"

        store.put(title="Hub", text="links to linked", entry_id="hub", metadata={"related": "linked"})
        store.put(title="Linked", text="connected", entry_id="linked")
        store.put(title="Orphan A", text="alone", entry_id="orph-a")
        store.put(title="Orphan B", text="also alone", entry_id="orph-b")

        curator = Curator(store, wiki_path, tmp_path)
        result = curator.curate(fix=True, check_urls=False)

        assert len(result.curate_log) == 1
        assert "archived 3 orphan(s)" in result.curate_log[0]
        assert "hub" in result.curate_log[0]  # hub is unreferenced
        assert "orph-a" in result.curate_log[0]
        assert "orph-b" in result.curate_log[0]

    def test_fix_appends_to_wiki_log(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        wiki_path = tmp_path / "wiki"

        store.put(title="Hub", text="links to linked", entry_id="hub", metadata={"related": "linked"})
        store.put(title="Linked", text="connected", entry_id="linked")
        store.put(title="Orphan", text="alone", entry_id="orph-1")

        curator = Curator(store, wiki_path, tmp_path)
        curator.curate(fix=True, check_urls=False)

        log = (wiki_path / "log.md").read_text(encoding="utf-8")
        assert "CURATE --fix" in log
        assert "orph-1" in log

    def test_fix_no_orphans_is_noop(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        wiki_path = tmp_path / "wiki"

        store.put(title="A", text="a", entry_id="a", metadata={"related": "b"})
        store.put(title="B", text="b", entry_id="b", metadata={"related": "a"})

        curator = Curator(store, wiki_path, tmp_path)
        result = curator.curate(fix=True, check_urls=False)

        assert result.orphans_archived == []
        assert result.orphans_md_written is False
        assert result.curate_log == []

    def test_entry_files_preserved_after_fix(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        wiki_path = tmp_path / "wiki"

        store.put(title="Orphan", text="alone", entry_id="orph-1")

        curator = Curator(store, wiki_path, tmp_path)
        curator.curate(fix=True, check_urls=False)

        entry_file = wiki_path / "entries" / "orph-1.md"
        assert entry_file.exists()


class TestCurateDiscovery:
    def test_curate_populates_discovered(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Readme", encoding="utf-8")
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "guide.md").write_text("# Guide", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        result = curator.curate(check_urls=False)

        assert len(result.discovered) == 2
        discovered_titles = {d.title for d in result.discovered}
        assert "README" in discovered_titles
        assert "guide" in discovered_titles

    def test_curate_fix_false_does_not_ingest(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Readme", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        result = curator.curate(fix=False, check_urls=False)

        assert len(result.discovered) == 1
        assert result.discovered_ingested == []
        assert len(store.all_entries()) == 0

    def test_curate_fix_true_auto_ingests(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Readme content here", encoding="utf-8")
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "architecture.md").write_text("# Architecture", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        result = curator.curate(fix=True, check_urls=False)

        assert len(result.discovered) == 2
        assert len(result.discovered_ingested) == 2
        assert len(store.all_entries()) == 2

        ingested_titles = {e.title for e in store.all_entries()}
        assert "README" in ingested_titles
        assert "architecture" in ingested_titles

    def test_curate_discovery_log_entries(self, tmp_path: Path) -> None:
        (tmp_path / "CHANGELOG.md").write_text("# Changelog", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        result = curator.curate(fix=False, check_urls=False)

        assert any("discovered 1 untracked project doc(s)" in log for log in result.curate_log)

    def test_curate_fix_discovery_log_entries(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("# Agents", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        result = curator.curate(fix=True, check_urls=False)

        log_text = " ".join(result.curate_log)
        assert "discovered 1 untracked project doc(s)" in log_text
        assert "ingested 1 discovered doc(s)" in log_text

    def test_curate_ingested_appears_in_voice(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Project Readme", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        result = curator.curate(fix=True, check_urls=False)

        assert result.voice_updated is True
        voice = (tmp_path / "VOICE.md").read_text(encoding="utf-8")
        assert "README" in voice

    def test_curate_no_discovery_when_empty(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        result = curator.curate(check_urls=False)

        assert result.discovered == []
        assert result.discovered_ingested == []

    def test_curate_skips_already_tracked(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Readme", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        store.put(title="README", text="content", entry_id="r1", metadata={"source": "./README.md"})

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        result = curator.curate(check_urls=False)

        assert result.discovered == []
        assert result.discovered_ingested == []
