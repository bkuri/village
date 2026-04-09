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
