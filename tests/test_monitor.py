"""Tests for Scribe polling-based file monitor."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from village.scribe.monitor import Monitor
from village.scribe.store import ScribeStore


class TestPollWithNewFile:
    def test_processes_new_file(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)
        store._ensure_dirs()

        ingest_dir = wiki_path / "ingest"
        (ingest_dir / "notes.md").write_text("# Notes\nSome content here", encoding="utf-8")

        mon = Monitor(wiki_path, store, poll_interval=5)
        results = mon.poll()

        assert len(results) == 1
        assert results[0]["file"] == "notes.md"
        assert results[0]["status"] == "success"
        assert results[0]["title"] == "notes"


class TestPollWithNoNewFiles:
    def test_returns_empty_when_no_files(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)
        store._ensure_dirs()

        mon = Monitor(wiki_path, store, poll_interval=5)
        results = mon.poll()

        assert results == []

    def test_returns_empty_when_all_seen(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)
        store._ensure_dirs()

        ingest_dir = wiki_path / "ingest"
        (ingest_dir / "old.md").write_text("# Old\nAlready seen", encoding="utf-8")

        mon = Monitor(wiki_path, store, poll_interval=5)
        mon.poll()
        results = mon.poll()

        assert results == []


class TestPollMultipleNewFiles:
    def test_processes_multiple_files(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)
        store._ensure_dirs()

        ingest_dir = wiki_path / "ingest"
        (ingest_dir / "alpha.md").write_text("# Alpha\nFirst file", encoding="utf-8")
        (ingest_dir / "bravo.txt").write_text("Second file content", encoding="utf-8")

        mon = Monitor(wiki_path, store, poll_interval=5)
        results = mon.poll()

        assert len(results) == 2
        filenames = [r["file"] for r in results]
        assert "alpha.md" in filenames
        assert "bravo.txt" in filenames


class TestSeenStatePersistence:
    def test_seen_files_persist_across_instances(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)
        store._ensure_dirs()

        ingest_dir = wiki_path / "ingest"
        (ingest_dir / "first.md").write_text("# First\nContent one", encoding="utf-8")

        mon1 = Monitor(wiki_path, store, poll_interval=5)
        results1 = mon1.poll()
        assert len(results1) == 1

        store2 = ScribeStore(wiki_path)
        mon2 = Monitor(wiki_path, store2, poll_interval=5)
        results2 = mon2.poll()
        assert results2 == []


class TestStop:
    def test_stop_sets_running_false(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)
        mon = Monitor(wiki_path, store, poll_interval=5)

        mon._running = True
        mon.stop()

        assert mon._running is False


class TestPollNoIngestDir:
    def test_returns_empty_when_no_ingest_dir(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)

        mon = Monitor(wiki_path, store, poll_interval=5)
        results = mon.poll()

        assert results == []


class TestStateFileCorruption:
    def test_handles_corrupted_state_file(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)
        store._ensure_dirs()

        state_path = tmp_path / ".village" / "monitor_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("not valid json{{{", encoding="utf-8")

        ingest_dir = wiki_path / "ingest"
        (ingest_dir / "recover.md").write_text("# Recover\nContent", encoding="utf-8")

        mon = Monitor(wiki_path, store, poll_interval=5)
        results = mon.poll()

        assert len(results) == 1
        assert results[0]["file"] == "recover.md"


class TestMonitorAutoResearchFlag:
    def test_auto_research_defaults_to_false(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)

        mon = Monitor(wiki_path, store, poll_interval=5)

        assert mon.auto_research is False

    def test_auto_research_can_be_enabled(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)

        mon = Monitor(wiki_path, store, poll_interval=5, auto_research=True)

        assert mon.auto_research is True


class TestMonitorSetResearcher:
    def test_set_researcher_stores_researcher(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)
        mon = Monitor(wiki_path, store, poll_interval=5)

        mock_researcher = MagicMock()
        mon.set_researcher(mock_researcher)

        assert mon._researcher is mock_researcher


class TestMonitorResearcherInitialization:
    def test_researcher_initializes_as_none(self, tmp_path: Path) -> None:
        wiki_path = tmp_path / "wiki"
        store = ScribeStore(wiki_path)

        mon = Monitor(wiki_path, store, poll_interval=5)

        assert mon._researcher is None
