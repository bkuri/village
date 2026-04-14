"""End-to-end integration tests for the onboarding pipeline.

Exercises the full flow: detect_project -> get_scaffold -> InterviewEngine -> Generator -> write_files.
Uses tmp_path for all file operations. No LLM or interactive input.
"""

from pathlib import Path

from village.config import OnboardConfig
from village.onboard.detector import detect_project
from village.onboard.generator import Generator
from village.onboard.generator import InterviewResult as GenInterviewResult
from village.onboard.interview import InterviewEngine
from village.onboard.scaffolds import get_scaffold


def _create_python_project(tmp_path: Path) -> Path:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname = 'myapp'\n\n[tool.pytest]\n[tool.ruff]\n",
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").touch()
    return tmp_path


def _run_pipeline(
    root: Path,
    answers: dict[str, str] | None = None,
    config: OnboardConfig | None = None,
) -> tuple[Generator, GenInterviewResult]:
    info = detect_project(root)
    scaffold = get_scaffold(info)
    cfg = config or OnboardConfig()
    engine = InterviewEngine(config=cfg, project_info=info, scaffold=scaffold)
    interview = engine.run_default(answers=answers or {})
    gen_interview = GenInterviewResult(
        answers=interview.answers,
        project_summary=interview.project_summary,
        raw_transcript=interview.raw_transcript,
    )
    gen = Generator(
        project_info=info,
        scaffold=scaffold,
        interview=gen_interview,
        project_root=root,
    )
    return gen, gen_interview


def _realistic_answers() -> dict[str, str]:
    return {
        "What does this project do?": "A CLI tool for managing distributed agent workflows.",
        "What's the main entry point?": "village/cli.py via click group.",
        "How do you run tests?": "uv run pytest",
        "What linting or formatting tools do you use?": "ruff for linting and formatting.",
        "What are the key dependencies?": "click, httpx, pydantic",
        "What external services or tools does this integrate with?": "tmux, git, beads",
        "What hard rules or constraints must agents follow?": "No print(), use click.echo(). No Any types.",
        "What are the key directories and their roles?": "village/ for source, tests/ for tests.",
        "What's currently being worked on?": "Onboarding flow integration tests.",
        "Does this project have a release or versioning strategy?": "Semver via village release.",
        "Anything else agents should know that I haven't asked about?": "Always use pathlib.Path.",
    }


class TestFullPipelineWithAnswers:
    """Scenario 1: Full pipeline with realistic interview answers."""

    def test_detect_python_project(self, tmp_path: Path) -> None:
        root = _create_python_project(tmp_path)
        info = detect_project(root)
        assert info.language == "python"
        assert info.build_tool == "uv"
        assert info.test_runner == "pytest"
        assert info.linter == "ruff"

    def test_scaffold_returned_for_python(self, tmp_path: Path) -> None:
        root = _create_python_project(tmp_path)
        info = detect_project(root)
        scaffold = get_scaffold(info)
        assert scaffold.language == "python"
        assert len(scaffold.build_commands) > 0
        assert len(scaffold.test_commands) > 0
        assert len(scaffold.lint_commands) > 0

    def test_interview_produces_result_with_answers(self, tmp_path: Path) -> None:
        root = _create_python_project(tmp_path)
        gen, _ = _run_pipeline(root, answers=_realistic_answers())
        assert gen is not None

    def test_generate_produces_all_outputs(self, tmp_path: Path) -> None:
        root = _create_python_project(tmp_path)
        gen, _ = _run_pipeline(root, answers=_realistic_answers())
        result = gen.generate()
        assert result.agents_md != ""
        assert result.readme_md != ""
        assert len(result.wiki_seeds) > 0

    def test_write_files_creates_disk_artifacts(self, tmp_path: Path) -> None:
        root = _create_python_project(tmp_path)
        gen, _ = _run_pipeline(root, answers=_realistic_answers())
        result = gen.generate()
        created = gen.write_files(result)

        assert "AGENTS.md" in created
        assert "README.md" in created
        assert (root / "AGENTS.md").exists()
        assert (root / "README.md").exists()

    def test_agents_md_contains_build_test_commands(self, tmp_path: Path) -> None:
        root = _create_python_project(tmp_path)
        gen, _ = _run_pipeline(root, answers=_realistic_answers())
        result = gen.generate()
        gen.write_files(result)

        agents_content = (root / "AGENTS.md").read_text(encoding="utf-8")
        assert "uv sync" in agents_content
        assert "pytest" in agents_content
        assert "ruff" in agents_content

    def test_wiki_seeds_written_to_ingest(self, tmp_path: Path) -> None:
        root = _create_python_project(tmp_path)
        gen, _ = _run_pipeline(root, answers=_realistic_answers())
        result = gen.generate()
        gen.write_files(result)

        ingest_dir = root / "wiki" / "ingest"
        assert ingest_dir.exists()
        assert ingest_dir.is_dir()
        seed_files = list(ingest_dir.iterdir())
        assert len(seed_files) > 0
        seed_names = [f.name for f in seed_files]
        assert "project-overview.md" in seed_names


class TestSkipInterviewScaffoldDefaults:
    """Scenario 2: Empty answers, generator uses scaffold defaults."""

    def test_generator_produces_output_with_empty_answers(self, tmp_path: Path) -> None:
        root = _create_python_project(tmp_path)
        gen, _ = _run_pipeline(root, answers={})
        result = gen.generate()
        assert result.agents_md != ""
        assert result.readme_md != ""

    def test_no_template_fill_in_markers_in_agents_md(self, tmp_path: Path) -> None:
        root = _create_python_project(tmp_path)
        gen, _ = _run_pipeline(root, answers={})
        result = gen.generate()
        gen.write_files(result)

        agents_content = (root / "AGENTS.md").read_text(encoding="utf-8")
        assert "<fill in>" not in agents_content

    def test_scaffold_commands_in_output_with_empty_answers(self, tmp_path: Path) -> None:
        root = _create_python_project(tmp_path)
        info = detect_project(root)
        scaffold = get_scaffold(info)
        gen, _ = _run_pipeline(root, answers={})
        result = gen.generate()

        for cmd in scaffold.build_commands:
            assert cmd in result.agents_md
        for cmd in scaffold.test_commands:
            assert cmd in result.agents_md


class TestUnknownLanguageProject:
    """Scenario 3: Project with no recognizable package file."""

    def test_detect_unknown_language(self, tmp_path: Path) -> None:
        info = detect_project(tmp_path)
        assert info.language == "unknown"
        assert info.needs_onboarding is True

    def test_generic_scaffold_returned(self, tmp_path: Path) -> None:
        info = detect_project(tmp_path)
        scaffold = get_scaffold(info)
        assert scaffold.language == "unknown"
        assert scaffold.framework is None

    def test_generator_handles_unknown_language(self, tmp_path: Path) -> None:
        gen, _ = _run_pipeline(
            tmp_path,
            answers={
                "What does this project do?": "A custom hardware project.",
                "What programming language is this project written in?": "VHDL",
            },
        )
        result = gen.generate()
        gen.write_files(result)

        assert (tmp_path / "AGENTS.md").exists()
        agents_content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        assert "VHDL" in agents_content or "hardware" in agents_content.lower()

    def test_unknown_language_gets_extra_question(self, tmp_path: Path) -> None:
        info = detect_project(tmp_path)
        scaffold = get_scaffold(info)
        config = OnboardConfig()
        engine = InterviewEngine(config=config, project_info=info, scaffold=scaffold)
        questions = engine.get_default_questions()
        language_questions = [q for q in questions if "language" in q.lower()]
        assert len(language_questions) == 1
        assert "What programming language" in language_questions[0]


class TestDetectorOnboardingStatus:
    """Scenario 4: Detection of needs_onboarding based on AGENTS.md state."""

    def test_no_agents_md_needs_onboarding(self, tmp_path: Path) -> None:
        info = detect_project(tmp_path)
        assert info.needs_onboarding is True
        assert info.has_existing_agents_md is False

    def test_complete_agents_md_no_onboarding(self, tmp_path: Path) -> None:
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text(
            "# Project Guide\n\n## Build\n\nRun make build.\n",
            encoding="utf-8",
        )
        info = detect_project(tmp_path)
        assert info.needs_onboarding is False
        assert info.has_existing_agents_md is True

    def test_template_agents_md_needs_onboarding(self, tmp_path: Path) -> None:
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text(
            "# Project Guide\n\nPlease <fill in> the details below.\n",
            encoding="utf-8",
        )
        info = detect_project(tmp_path)
        assert info.needs_onboarding is True
        assert info.has_existing_agents_md is True

    def test_agents_md_with_describe_key_conventions_needs_onboarding(self, tmp_path: Path) -> None:
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text(
            "# Guide\n\nDescribe key conventions here.\n",
            encoding="utf-8",
        )
        info = detect_project(tmp_path)
        assert info.needs_onboarding is True

    def test_agents_md_with_brief_description_needs_onboarding(self, tmp_path: Path) -> None:
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text(
            "# Guide\n\nBrief description of the project.\n",
            encoding="utf-8",
        )
        info = detect_project(tmp_path)
        assert info.needs_onboarding is True


class TestConfigIntegration:
    """Scenario 5: OnboardConfig defaults and max_questions behavior."""

    def test_default_config_values(self) -> None:
        config = OnboardConfig()
        assert config.max_questions == 15
        assert config.interview_model == "openrouter/anthropic/claude-3-haiku"
        assert config.skip_on_first_up is False
        assert config.ppc_mode == "onboard"
        assert config.self_critique is True

    def test_max_questions_limits_questions(self, tmp_path: Path) -> None:
        root = _create_python_project(tmp_path)
        info = detect_project(root)
        scaffold = get_scaffold(info)
        config = OnboardConfig(max_questions=3)
        engine = InterviewEngine(config=config, project_info=info, scaffold=scaffold)
        questions = engine.get_default_questions()
        assert len(questions) <= 3

    def test_max_questions_one(self, tmp_path: Path) -> None:
        root = _create_python_project(tmp_path)
        info = detect_project(root)
        scaffold = get_scaffold(info)
        config = OnboardConfig(max_questions=1)
        engine = InterviewEngine(config=config, project_info=info, scaffold=scaffold)
        questions = engine.get_default_questions()
        assert len(questions) == 1

    def test_config_from_dict(self) -> None:
        config = OnboardConfig.from_env_and_config(
            {
                "ONBOARD.MAX_QUESTIONS": "5",
                "ONBOARD.INTERVIEW_MODEL": "test-model",
            }
        )
        assert config.max_questions == 5
        assert config.interview_model == "test-model"

    def test_pipeline_with_limited_questions(self, tmp_path: Path) -> None:
        root = _create_python_project(tmp_path)
        gen, _ = _run_pipeline(
            root,
            answers={
                "What does this project do?": "A test project.",
                "What's the main entry point?": "main.py",
            },
            config=OnboardConfig(max_questions=2),
        )
        result = gen.generate()
        assert result.agents_md != ""
        assert "test project" in result.agents_md.lower()
