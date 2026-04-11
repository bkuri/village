from pathlib import Path

from village.keeper.store import KeeperStore


class TestSeeWithMarkdownFile:
    def test_ingests_markdown_file(self, tmp_path: Path) -> None:
        md_file = tmp_path / "notes" / "auth-setup.md"
        md_file.parent.mkdir(parents=True)
        md_file.write_text("# Auth Setup\nRequires VILLAGE_AUTH_KEY env var.", encoding="utf-8")

        elder = KeeperStore(tmp_path / "wiki")
        result = elder.see(str(md_file))

        assert result.status == "success"
        assert result.entry_id != ""
        assert result.title == "auth-setup"
        assert result.tags == ["auth-setup"]


class TestSeeWithTextFile:
    def test_ingests_text_file(self, tmp_path: Path) -> None:
        txt_file = tmp_path / "notes" / "deploy-guide.txt"
        txt_file.parent.mkdir(parents=True)
        txt_file.write_text("Deploy using kubectl apply -f manifest.yaml", encoding="utf-8")

        elder = KeeperStore(tmp_path / "wiki")
        result = elder.see(str(txt_file))

        assert result.status == "success"
        assert result.title == "deploy-guide"
        assert result.tags == ["deploy-guide"]


class TestSeeWithInvalidSource:
    def test_nonexistent_file_returns_error(self, tmp_path: Path) -> None:
        elder = KeeperStore(tmp_path / "wiki")
        result = elder.see(str(tmp_path / "nonexistent.md"))

        assert result.status == "error"
        assert result.entry_id == ""
        assert "not found" in result.error.lower() or "no such" in result.error.lower()


class TestLogAppended:
    def test_log_md_appended_after_see(self, tmp_path: Path) -> None:
        md_file = tmp_path / "notes" / "config-notes.md"
        md_file.parent.mkdir(parents=True)
        md_file.write_text("Configuration details here", encoding="utf-8")

        elder = KeeperStore(tmp_path / "wiki")
        result = elder.see(str(md_file))

        assert result.status == "success"
        assert elder.log_path.exists()

        log_content = elder.log_path.read_text(encoding="utf-8")
        assert "# Ingest Log" in log_content
        assert result.entry_id in log_content
        assert "config-notes" in log_content


class TestIndexUpdated:
    def test_index_md_updated_after_see(self, tmp_path: Path) -> None:
        md_file = tmp_path / "notes" / "testing-strategy.md"
        md_file.parent.mkdir(parents=True)
        md_file.write_text("Use pytest for all testing", encoding="utf-8")

        elder = KeeperStore(tmp_path / "wiki")
        result = elder.see(str(md_file))

        assert result.status == "success"
        index_path = elder.pages_dir / "index.md"
        assert index_path.exists()

        index_content = index_path.read_text(encoding="utf-8")
        assert "# Memory Index" in index_content
        assert result.entry_id in index_content


class TestFileMovedToProcessed:
    def test_ingest_file_moved_to_processed(self, tmp_path: Path) -> None:
        elder = KeeperStore(tmp_path / "wiki")
        elder._ensure_dirs()

        ingest_file = elder.ingest_dir / "readme.md"
        ingest_file.write_text("# Readme\nProject readme content", encoding="utf-8")

        result = elder.see(str(ingest_file))

        assert result.status == "success"
        assert not ingest_file.exists()
        processed_file = elder.processed_dir / "readme.md"
        assert processed_file.exists()
        content = processed_file.read_text(encoding="utf-8")
        assert "Project readme content" in content


class TestAskWithMatchingPages:
    def test_returns_relevant_pages(self, tmp_path: Path) -> None:
        elder = KeeperStore(tmp_path / "wiki")

        md1 = tmp_path / "auth.md"
        md1.write_text("# Auth Setup\nConfigure authentication tokens", encoding="utf-8")
        elder.see(str(md1))

        md2 = tmp_path / "deploy.md"
        md2.write_text("# Deploy Guide\nDeploy using kubectl apply", encoding="utf-8")
        elder.see(str(md2))

        result = elder.ask("auth")

        assert "auth" in result.answer.lower()
        assert len(result.sources) >= 1
        assert result.saved is False


class TestAskWithNoMatches:
    def test_returns_no_relevant_message(self, tmp_path: Path) -> None:
        elder = KeeperStore(tmp_path / "wiki")

        md = tmp_path / "cooking.md"
        md.write_text("# Cooking\nHow to bake bread", encoding="utf-8")
        elder.see(str(md))

        result = elder.ask("quantum physics")

        assert result.answer == "No relevant pages found."
        assert result.sources == []
        assert result.saved is False


class TestAskWithEmptyWiki:
    def test_returns_no_relevant_on_empty_wiki(self, tmp_path: Path) -> None:
        elder = KeeperStore(tmp_path / "wiki")
        result = elder.ask("anything")

        assert result.answer == "No relevant pages found."
        assert result.sources == []


class TestAskWithSave:
    def test_creates_new_page_when_save_true(self, tmp_path: Path) -> None:
        elder = KeeperStore(tmp_path / "wiki")

        md = tmp_path / "config.md"
        md.write_text("# Config\nSet VILLAGE_HOME directory", encoding="utf-8")
        elder.see(str(md))

        result = elder.ask("config", save=True)

        assert result.saved is True
        assert len(result.sources) >= 1

        entries = elder.store.all_entries()
        synthesized = [e for e in entries if "synthesized" in e.tags]
        assert len(synthesized) == 1
        assert synthesized[0].title.startswith("Q: config")


class TestAskSourcesPopulated:
    def test_sources_match_hit_ids(self, tmp_path: Path) -> None:
        elder = KeeperStore(tmp_path / "wiki")

        md1 = tmp_path / "logging.md"
        md1.write_text("# Logging\nConfigure structured logging", encoding="utf-8")
        elder.see(str(md1))

        md2 = tmp_path / "logrotate.md"
        md2.write_text("# Log Rotation\nRotate logs daily", encoding="utf-8")
        elder.see(str(md2))

        result = elder.ask("log")

        assert len(result.sources) >= 1
        assert all(isinstance(s, str) for s in result.sources)
        for source_id in result.sources:
            entry = elder.store.get(source_id)
            assert entry is not None
