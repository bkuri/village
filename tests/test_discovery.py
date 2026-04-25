"""Tests for auto-discovery of project files in Curator."""

from pathlib import Path

from village.memory import MemoryStore
from village.scribe.curate import Curator


class TestIsExcluded:
    def test_default_excludes(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)

        assert curator._is_excluded(".git/HEAD")
        assert curator._is_excluded(".village/config")
        assert curator._is_excluded("wiki/pages/index.md")
        assert curator._is_excluded("node_modules/foo/bar.md")
        assert curator._is_excluded("docs/drafts/idea.md")
        assert curator._is_excluded("docs/wip/notes.md")
        assert curator._is_excluded("docs/original/raw.md")

    def test_includes_normal_docs(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)

        assert not curator._is_excluded("docs/architecture.md")
        assert not curator._is_excluded("docs/guides/setup.md")
        assert not curator._is_excluded("README.md")

    def test_extra_excludes(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)

        assert not curator._is_excluded("internal/secret.md")
        assert curator._is_excluded("internal/secret.md", extra_excludes=("internal/",))

    def test_prefix_without_trailing_slash(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)

        # ".git" as a file should also match
        assert curator._is_excluded(".git")


class TestKnownSources:
    def test_empty_store(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)

        assert curator._known_sources() == set()

    def test_collects_source_paths(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        store.put(title="Readme", text="content", entry_id="r1", metadata={"source": "./README.md"})
        store.put(title="Guide", text="content", entry_id="g1", metadata={"source": "docs/guide.md"})

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        sources = curator._known_sources()

        assert "./README.md" in sources
        assert "docs/guide.md" in sources


class TestFindUndiscovered:
    def test_finds_root_files(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Readme", encoding="utf-8")
        (tmp_path / "CHANGELOG.md").write_text("# Changelog", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        discovered = curator.find_undiscovered()

        paths = [str(d.path.relative_to(tmp_path)) for d in discovered]
        assert "README.md" in paths
        assert "CHANGELOG.md" in paths

    def test_finds_docs_directory(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "architecture.md").write_text("# Architecture", encoding="utf-8")
        (docs_dir / "guides").mkdir()
        (docs_dir / "guides" / "setup.md").write_text("# Setup Guide", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        discovered = curator.find_undiscovered()

        paths = [str(d.path.relative_to(tmp_path)) for d in discovered]
        assert "docs/architecture.md" in paths
        assert "docs/guides/setup.md" in paths

    def test_skips_already_tracked(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Readme", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        store.put(title="README", text="content", entry_id="r1", metadata={"source": "./README.md"})

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        discovered = curator.find_undiscovered()

        paths = [str(d.path.relative_to(tmp_path)) for d in discovered]
        assert "README.md" not in paths

    def test_skips_already_tracked_without_dot_slash(self, tmp_path: Path) -> None:
        (tmp_path / "CHANGELOG.md").write_text("# Changelog", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        store.put(title="Changelog", text="content", entry_id="c1", metadata={"source": "CHANGELOG.md"})

        curator = Curator(store, tmp_path / "wiki", tmp_path)
        discovered = curator.find_undiscovered()

        paths = [str(d.path.relative_to(tmp_path)) for d in discovered]
        assert "CHANGELOG.md" not in paths

    def test_skips_excluded_paths(self, tmp_path: Path) -> None:
        # docs/drafts/ is excluded by default
        drafts_dir = tmp_path / "docs" / "drafts"
        drafts_dir.mkdir(parents=True)
        (drafts_dir / "idea.md").write_text("# Idea", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        discovered = curator.find_undiscovered()

        paths = [str(d.path.relative_to(tmp_path)) for d in discovered]
        assert "docs/drafts/idea.md" not in paths

    def test_skips_nonexistent_files(self, tmp_path: Path) -> None:
        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        discovered = curator.find_undiscovered()

        # No files created → nothing discovered
        assert discovered == []

    def test_skips_non_md_in_docs(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "image.png").write_bytes(b"png")
        (docs_dir / "data.json").write_text("{}", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        discovered = curator.find_undiscovered()

        paths = [str(d.path.relative_to(tmp_path)) for d in discovered]
        assert all(p.endswith(".md") for p in paths)

    def test_title_is_file_stem(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Readme", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        discovered = curator.find_undiscovered()

        assert len(discovered) == 1
        assert discovered[0].title == "README"

    def test_extra_excludes(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "internal").mkdir()
        (docs_dir / "internal" / "secret.md").write_text("# Secret", encoding="utf-8")
        (docs_dir / "public.md").write_text("# Public", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        discovered = curator.find_undiscovered(extra_excludes=("docs/internal/",))

        paths = [str(d.path.relative_to(tmp_path)) for d in discovered]
        assert "docs/public.md" in paths
        assert "docs/internal/secret.md" not in paths

    def test_mixed_root_and_docs(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Readme", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("# Agents", encoding="utf-8")
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "guide.md").write_text("# Guide", encoding="utf-8")

        store = MemoryStore(tmp_path / "wiki")
        curator = Curator(store, tmp_path / "wiki", tmp_path)
        discovered = curator.find_undiscovered()

        paths = [str(d.path.relative_to(tmp_path)) for d in discovered]
        assert len(paths) == 3
        assert "README.md" in paths
        assert "AGENTS.md" in paths
        assert "docs/guide.md" in paths
