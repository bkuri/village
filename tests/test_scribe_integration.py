"""Integration tests for Scribe end-to-end flows."""

from pathlib import Path

from village.memory import MemoryStore
from village.scribe.crosslink import find_related, update_cross_references
from village.scribe.curate import Curator
from village.scribe.monitor import Monitor
from village.scribe.store import ScribeStore


class TestFullIngestFlow:
    def test_ingest_creates_page_and_updates_index(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)

        ingest_dir = wiki_path / "ingest"
        ingest_dir.mkdir(parents=True)
        source_file = ingest_dir / "guide.md"
        source_file.write_text("# Authentication Guide\n\nSet VILLAGE_AUTH_KEY env var.", encoding="utf-8")

        result = store.see(str(source_file))

        assert result.status == "success"
        assert store.store.get(result.entry_id) is not None
        assert (wiki_path / "pages" / "index.md").exists()
        assert (wiki_path / "log.md").exists()
        assert not source_file.exists()
        assert (wiki_path / "processed" / "guide.md").exists()

    def test_ingest_multiple_sources_with_crosslinks(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)

        store.store.put(
            title="Auth Setup",
            text="Configure VILLAGE_AUTH_KEY",
            tags=["auth", "env", "configuration"],
            entry_id="auth",
        )
        store.store.put(
            title="Config Setup",
            text="All env vars for configuration",
            tags=["config", "env", "configuration"],
            entry_id="config",
        )

        memory_store = store.store
        auth_entry = memory_store.get("auth")
        assert auth_entry is not None
        related = find_related(memory_store, auth_entry)
        assert len(related) > 0

        count = update_cross_references(memory_store, "auth", ["config"])
        assert count >= 1

        refreshed_auth = memory_store.get("auth")
        assert refreshed_auth is not None
        related_meta = refreshed_auth.metadata.get("related", [])
        assert "config" in related_meta


class TestQueryFlow:
    def test_ask_returns_relevant_results(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)

        store.store.put(
            title="Auth Setup", text="Configure VILLAGE_AUTH_KEY for authentication", tags=["auth"], entry_id="auth"
        )
        store.store.put(title="Git Hooks", text="Set up pre-commit hooks", tags=["git"], entry_id="git")

        result = store.ask("authentication")
        assert "auth" in result.sources
        assert "VILLAGE_AUTH_KEY" in result.answer

    def test_ask_with_save_creates_page(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)

        store.store.put(title="Auth", text="Use env vars for auth", tags=["auth"], entry_id="a")

        result = store.ask("auth", save=True)
        assert result.saved is True
        assert result.sources == ["a"]


class TestCurateFlow:
    def test_curate_connected_graph_finds_orphans(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        project_root = tmp_path
        store = ScribeStore(wiki_path)

        store.store.put(title="Hub", text="links to linked", entry_id="hub", metadata={"related": "linked"})
        store.store.put(title="Linked Page", text="connected", entry_id="linked")
        store.store.put(title="Lonely Page", text="No one links here", tags=["solo"], entry_id="orphan")

        curator = Curator(store.store, wiki_path, project_root)
        result = curator.curate(check_urls=False)

        assert "orphan" in result.orphans
        assert "hub" in result.orphans  # hub is not referenced by anyone
        assert "linked" not in result.orphans
        assert result.voice_updated is True
        assert (project_root / "VOICE.md").exists()

        voice = (project_root / "VOICE.md").read_text(encoding="utf-8")
        assert "Lonely Page" in voice
        assert "Wiki Index" in voice


class TestMonitorFlow:
    def test_monitor_processes_dropped_files(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)

        ingest_dir = wiki_path / "ingest"
        ingest_dir.mkdir(parents=True)

        monitor = Monitor(wiki_path, store, poll_interval=1)

        (ingest_dir / "notes.md").write_text("# My Notes\nSome observations.", encoding="utf-8")
        (ingest_dir / "extra.txt").write_text("Extra content", encoding="utf-8")

        results = monitor.poll()
        assert len(results) == 2
        assert all(r["status"] == "success" for r in results)

        results2 = monitor.poll()
        assert len(results2) == 0


class TestConfigIntegration:
    def test_memory_store_uses_configured_path(self, tmp_path: Path) -> None:
        custom_path = tmp_path / "custom" / "memory"
        store = MemoryStore(custom_path)

        entry_id = store.put(title="Test", text="Body", tags=["test"])
        assert store.get(entry_id) is not None
        assert (custom_path / "entries" / f"{entry_id}.md").exists()
        assert (custom_path / "index.md").exists()
