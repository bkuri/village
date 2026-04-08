"""Tests for Elder curation engine."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import httpx

from village.elder.curate import CurateResult, Curator
from village.memory import MemoryStore


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

    def test_all_orphans_in_empty_graph(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="Solo 1", text="s1", entry_id="solo-1")
        store.put(title="Solo 2", text="s2", entry_id="solo-2")

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        orphans = curator.find_orphans()

        assert set(orphans) == {"solo-1", "solo-2"}

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

        with patch("village.elder.curate.httpx.head") as mock_head:
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

        with patch("village.elder.curate.httpx.head") as mock_head:
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

        with patch("village.elder.curate.httpx.head") as mock_head:
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

        with patch("village.elder.curate.httpx.head") as mock_head:
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
        assert "orph-1" in result.orphans
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

        with patch("village.elder.curate.httpx.head") as mock_head:
            mock_head.side_effect = httpx.ConnectError("fail")
            result = curator.curate(check_urls=True)

        assert len(result.broken_links) == 1
        assert result.broken_links[0].entry_id == "url-1"
