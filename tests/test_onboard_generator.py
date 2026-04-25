from pathlib import Path

from village.onboard.detector import ProjectInfo
from village.onboard.generator import Generator, InterviewResult
from village.onboard.scaffolds import ScaffoldTemplate


def _make_python_cli_scaffold() -> ScaffoldTemplate:
    return ScaffoldTemplate(
        language="python",
        framework="cli",
        build_commands=["uv sync", "uv pip install -e ."],
        test_commands=["uv run pytest", "uv run pytest tests/test_module.py"],
        lint_commands=["uv run ruff check .", "uv run ruff format ."],
        typecheck_commands=["uv run mypy src/"],
        common_deps=["click", "httpx"],
        directory_structure={
            "src/": "Source code",
            "tests/": "Test files",
            "pyproject.toml": "Project configuration",
        },
        conventions=[
            "Use pathlib.Path for file I/O",
            "Type hints on all params and returns",
        ],
    )


def _make_project_info() -> ProjectInfo:
    return ProjectInfo(
        language="python",
        framework="cli",
        build_tool="uv",
        test_runner="pytest",
        linter="ruff",
        project_name="myapp",
    )


class TestGenerateProducesAllFields:
    def test_agents_md_populated(self) -> None:
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=Path("/tmp/dummy"),
        )
        result = gen.generate()

        assert result.agents_md != ""
        assert "# myapp - Agent Development Guide" in result.agents_md

    def test_readme_md_populated(self) -> None:
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=Path("/tmp/dummy"),
        )
        result = gen.generate()

        assert result.readme_md != ""
        assert "# myapp" in result.readme_md

    def test_wiki_seeds_populated(self) -> None:
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=Path("/tmp/dummy"),
        )
        result = gen.generate()

        assert isinstance(result.wiki_seeds, list)

    def test_wiki_path_set(self) -> None:
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=Path("/tmp/dummy"),
        )
        result = gen.generate()

        assert result.wiki_path == Path("/tmp/dummy/wiki")


class TestWriteFiles:
    def test_creates_agents_md(self, tmp_path: Path) -> None:
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=tmp_path,
        )
        result = gen.generate()
        created = gen.write_files(result)

        assert "AGENTS.md" in created
        assert (tmp_path / "AGENTS.md").exists()
        content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert "# myapp - Agent Development Guide" in content

    def test_creates_readme_md(self, tmp_path: Path) -> None:
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=tmp_path,
        )
        result = gen.generate()
        created = gen.write_files(result)

        assert "README.md" in created
        assert (tmp_path / "README.md").exists()
        content = (tmp_path / "README.md").read_text(encoding="utf-8")
        assert "# myapp" in content

    def test_creates_wiki_seeds(self, tmp_path: Path) -> None:
        interview = InterviewResult(
            answers={
                "What does this project do?": "A CLI tool for managing tasks.",
                "What are the key dependencies?": "click, httpx",
            }
        )
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=interview,
            project_root=tmp_path,
        )
        result = gen.generate()
        created = gen.write_files(result)

        assert len(result.wiki_seeds) > 0
        for filename, _ in result.wiki_seeds:
            assert f"wiki/ingest/{filename}" in created
            assert (tmp_path / "wiki" / "ingest" / filename).exists()

    def test_no_wiki_seeds_skips_ingest_dir(self, tmp_path: Path) -> None:
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=tmp_path,
        )
        result = gen.generate()
        result.wiki_seeds = []
        created = gen.write_files(result)

        assert not (tmp_path / "wiki").exists()
        wiki_entries = [c for c in created if c.startswith("wiki/")]
        assert len(wiki_entries) == 0


class TestWikiSeedsValidMarkdown:
    def test_seeds_start_with_heading(self, tmp_path: Path) -> None:
        interview = InterviewResult(
            answers={
                "What does this project do?": "A CLI tool.",
                "What are the key dependencies?": "click",
                "What hard rules or constraints must agents follow?": "No print()",
                "What's currently being worked on?": "Refactoring the queue.",
            }
        )
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=interview,
            project_root=tmp_path,
        )
        result = gen.generate()

        for filename, content in result.wiki_seeds:
            assert content.startswith("# "), f"{filename} does not start with a heading"


class TestNoPlaceholders:
    def test_agents_md_no_fill_in(self) -> None:
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=Path("/tmp/dummy"),
        )
        result = gen.generate()

        assert "<fill in>" not in result.agents_md

    def test_agents_md_no_template_markers(self) -> None:
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=Path("/tmp/dummy"),
        )
        result = gen.generate()

        assert "Describe key conventions" not in result.agents_md
        assert "Brief description" not in result.agents_md


class TestEmptyInterviewAnswers:
    def test_uses_scaffold_defaults(self) -> None:
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=Path("/tmp/dummy"),
        )
        result = gen.generate()

        assert "# Build:" in result.agents_md
        assert "# Test:" in result.agents_md
        assert "# Lint:" in result.agents_md
        assert "uv run pytest" in result.agents_md
        assert "Use pathlib.Path for file I/O" in result.agents_md

    def test_overview_uses_default_text(self) -> None:
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=Path("/tmp/dummy"),
        )
        result = gen.generate()

        assert "Project description pending." in result.agents_md


class TestFullInterviewAnswers:
    def test_overrides_default_overview(self) -> None:
        interview = InterviewResult(
            answers={
                "What does this project do?": "A task runner for distributed agents.",
            }
        )
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=interview,
            project_root=Path("/tmp/dummy"),
        )
        result = gen.generate()

        assert "A task runner for distributed agents." in result.agents_md
        assert "Project description pending." not in result.agents_md

    def test_overrides_default_constraints(self) -> None:
        interview = InterviewResult(
            answers={
                "What hard rules or constraints must agents follow?": "- No cloud calls\n- File-based state only",
            }
        )
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=interview,
            project_root=Path("/tmp/dummy"),
        )
        result = gen.generate()

        assert "No cloud calls" in result.agents_md
        assert "File-based state only" in result.agents_md

    def test_readme_includes_dependencies(self) -> None:
        interview = InterviewResult(
            answers={
                "What are the key dependencies?": "click for CLI, httpx for HTTP",
            }
        )
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=interview,
            project_root=Path("/tmp/dummy"),
        )
        result = gen.generate()

        assert "## Dependencies" in result.readme_md
        assert "click for CLI" in result.readme_md

    def test_wiki_seeds_includes_all_three(self) -> None:
        interview = InterviewResult(
            answers={
                "What does this project do?": "A CLI tool.",
                "What's the main entry point?": "cli.py",
                "What are the key dependencies?": "click",
                "What hard rules or constraints must agents follow?": "No print()",
                "What's currently being worked on?": "Adding queue support.",
            }
        )
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=interview,
            project_root=Path("/tmp/dummy"),
        )
        result = gen.generate()

        filenames = [name for name, _ in result.wiki_seeds]
        assert "project-overview.md" in filenames
        assert "conventions.md" in filenames
        assert "active-development.md" in filenames


class TestGetAnswerSubstring:
    def test_case_insensitive_match(self) -> None:
        interview = InterviewResult(
            answers={
                "WHAT DOES THIS PROJECT DO?": "A big tool.",
            }
        )
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=interview,
            project_root=Path("/tmp/dummy"),
        )

        result = gen._get_answer("what does this project do?", "default")

        assert result == "A big tool."

    def test_partial_match(self) -> None:
        interview = InterviewResult(
            answers={
                "Can you tell me what the key dependencies are?": "click and httpx",
            }
        )
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=interview,
            project_root=Path("/tmp/dummy"),
        )

        result = gen._get_answer("key dependencies", "none")

        assert result == "click and httpx"

    def test_no_match_returns_default(self) -> None:
        interview = InterviewResult(answers={})
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=interview,
            project_root=Path("/tmp/dummy"),
        )

        result = gen._get_answer("nonexistent question", "fallback")

        assert result == "fallback"

    def test_empty_answer_returns_default(self) -> None:
        interview = InterviewResult(
            answers={
                "What does this project do?": "",
            }
        )
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=interview,
            project_root=Path("/tmp/dummy"),
        )

        result = gen._get_answer("What does this project do?", "default text")

        assert result == "default text"


class TestDiscoverExistingDocs:
    def test_finds_conventional_root_files(self, tmp_path: Path) -> None:
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\nAll notable changes.", encoding="utf-8")
        (tmp_path / "CONTRIBUTING.md").write_text("# Contributing\n\nPlease fork.", encoding="utf-8")

        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=tmp_path,
        )
        seeds = gen._discover_existing_docs(set())

        filenames = [name for name, _ in seeds]
        assert "CHANGELOG.md" in filenames
        assert "CONTRIBUTING.md" in filenames

    def test_finds_docs_directory_files(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "guide.md").write_text("# Guide\n\nHow to use.", encoding="utf-8")
        (docs_dir / "api.md").write_text("# API\n\nEndpoints.", encoding="utf-8")

        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=tmp_path,
        )
        seeds = gen._discover_existing_docs(set())

        filenames = [name for name, _ in seeds]
        assert "docs/guide.md" in filenames
        assert "docs/api.md" in filenames

    def test_skips_readme_and_agents_md(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# My App", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("# Agents Guide", encoding="utf-8")
        (tmp_path / "CHANGELOG.md").write_text("# Changelog", encoding="utf-8")

        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=tmp_path,
        )
        seeds = gen._discover_existing_docs(set())

        filenames = [name for name, _ in seeds]
        assert "README.md" not in filenames
        assert "AGENTS.md" not in filenames
        assert "CHANGELOG.md" in filenames

    def test_skips_excluded_paths(self, tmp_path: Path) -> None:
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        (wiki_dir / "index.md").write_text("# Wiki Index", encoding="utf-8")

        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=tmp_path,
        )
        seeds = gen._discover_existing_docs(set())

        filenames = [name for name, _ in seeds]
        assert not any("wiki" in f for f in filenames)

    def test_skips_nonexistent_files(self, tmp_path: Path) -> None:
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=tmp_path,
        )
        seeds = gen._discover_existing_docs(set())

        assert len(seeds) == 0

    def test_skips_docs_drafts_and_wip(self, tmp_path: Path) -> None:
        (tmp_path / "docs" / "drafts").mkdir(parents=True)
        (tmp_path / "docs" / "wip").mkdir(parents=True)
        (tmp_path / "docs" / "drafts" / "idea.md").write_text("# Idea", encoding="utf-8")
        (tmp_path / "docs" / "wip" / "scratch.md").write_text("# Scratch", encoding="utf-8")
        (tmp_path / "docs" / "guide.md").write_text("# Guide", encoding="utf-8")

        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=tmp_path,
        )
        seeds = gen._discover_existing_docs(set())

        filenames = [name for name, _ in seeds]
        assert "docs/guide.md" in filenames
        assert "docs/drafts/idea.md" not in filenames
        assert "docs/wip/scratch.md" not in filenames

    def test_skips_existing_seed_names(self, tmp_path: Path) -> None:
        (tmp_path / "CHANGELOG.md").write_text("# Changelog", encoding="utf-8")

        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=tmp_path,
        )
        seeds = gen._discover_existing_docs({"CHANGELOG.md"})

        filenames = [name for name, _ in seeds]
        assert "CHANGELOG.md" not in filenames

    def test_returns_content(self, tmp_path: Path) -> None:
        content = "# Changelog\n\n## 1.0.0\n\nInitial release."
        (tmp_path / "CHANGELOG.md").write_text(content, encoding="utf-8")

        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=tmp_path,
        )
        seeds = gen._discover_existing_docs(set())

        assert len(seeds) == 1
        assert seeds[0][1] == content


class TestGenerateIncludesDiscoveredDocs:
    def test_discovered_docs_appear_in_wiki_seeds(self, tmp_path: Path) -> None:
        (tmp_path / "CHANGELOG.md").write_text("# Changelog", encoding="utf-8")
        (tmp_path / "CONTRIBUTING.md").write_text("# Contributing", encoding="utf-8")

        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=tmp_path,
        )
        result = gen.generate()

        filenames = [name for name, _ in result.wiki_seeds]
        assert "CHANGELOG.md" in filenames
        assert "CONTRIBUTING.md" in filenames

    def test_no_duplicate_seeds_when_interview_and_discovered_overlap(self, tmp_path: Path) -> None:
        (tmp_path / "CHANGELOG.md").write_text("# Changelog", encoding="utf-8")

        interview = InterviewResult(
            answers={
                "What does this project do?": "A CLI tool.",
            }
        )
        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=interview,
            project_root=tmp_path,
        )
        result = gen.generate()

        filenames = [name for name, _ in result.wiki_seeds]
        assert filenames.count("CHANGELOG.md") == 1

    def test_discovered_docs_written_to_ingest(self, tmp_path: Path) -> None:
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 1.0.0", encoding="utf-8")

        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=tmp_path,
        )
        result = gen.generate()
        created = gen.write_files(result)

        assert (tmp_path / "wiki" / "ingest" / "CHANGELOG.md").exists()
        assert "wiki/ingest/CHANGELOG.md" in created

    def test_readme_and_agents_not_discovered_even_if_present(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("# Old README", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("# Old Agents", encoding="utf-8")

        gen = Generator(
            project_info=_make_project_info(),
            scaffold=_make_python_cli_scaffold(),
            interview=InterviewResult(),
            project_root=tmp_path,
        )
        result = gen.generate()

        filenames = [name for name, _ in result.wiki_seeds]
        assert "README.md" not in filenames
        assert "AGENTS.md" not in filenames
