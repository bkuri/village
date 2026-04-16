import os  # noqa: F401 (used in skipif)
from pathlib import Path

import pytest

from village.config import OnboardConfig, _load_global_config, get_global_config
from village.onboard.detector import ProjectInfo
from village.onboard.interview import (
    _DEFAULT_QUESTIONS,
    InterviewEngine,
    InterviewResult,
)
from village.onboard.scaffolds import ScaffoldTemplate


def _make_engine(
    max_questions: int = 15,
    language: str = "python",
    framework: str | None = None,
    build_tool: str | None = None,
    test_runner: str | None = "pytest",
    linter: str | None = "ruff",
    project_name: str = "test-project",
    conventions: list[str] | None = None,
    preseeded_answers: dict[str, str] | None = None,
) -> InterviewEngine:
    config = OnboardConfig(max_questions=max_questions)
    project_info = ProjectInfo(
        language=language,
        framework=framework,
        build_tool=build_tool,
        test_runner=test_runner,
        linter=linter,
        project_name=project_name,
    )
    scaffold = ScaffoldTemplate(
        language=language,
        framework=framework,
        conventions=conventions or [],
    )
    return InterviewEngine(
        config=config, project_info=project_info, scaffold=scaffold, preseeded_answers=preseeded_answers
    )


class TestGetDefaultQuestions:
    def test_returns_up_to_max_questions(self) -> None:
        engine = _make_engine(max_questions=5)
        questions = engine.get_default_questions()
        assert len(questions) == 5

    def test_returns_all_default_when_max_high(self) -> None:
        engine = _make_engine(max_questions=50)
        questions = engine.get_default_questions()
        assert len(questions) == len(_DEFAULT_QUESTIONS)

    def test_adds_language_question_for_unknown(self) -> None:
        engine = _make_engine(language="unknown", test_runner=None)
        questions = engine.get_default_questions()
        assert "What programming language is this project written in?" in questions

    def test_no_language_question_for_known(self) -> None:
        engine = _make_engine(language="python")
        questions = engine.get_default_questions()
        assert "What programming language is this project written in?" not in questions

    def test_modifies_test_question_when_no_runner(self) -> None:
        engine = _make_engine(test_runner=None)
        questions = engine.get_default_questions()
        test_qs = [q for q in questions if "tests" in q.lower()]
        assert any("Do you have tests?" in q for q in test_qs)

    def test_keeps_original_test_question_with_runner(self) -> None:
        engine = _make_engine(test_runner="pytest")
        questions = engine.get_default_questions()
        assert "How do you run tests?" in questions


class TestRunDefault:
    def test_with_provided_answers(self) -> None:
        engine = _make_engine()
        answers = {
            "What does this project do?": "A CLI tool",
            "How do you run tests?": "pytest",
        }
        result = engine.run_default(answers)

        assert result.answers == answers
        assert "A CLI tool" in result.project_summary
        assert "pytest" in result.project_summary

    def test_with_no_answers(self) -> None:
        engine = _make_engine()
        result = engine.run_default()

        assert result.answers == {}
        assert result.project_summary == "No answers provided."
        assert len(result.raw_transcript) > 0

    def test_transcript_contains_all_questions(self) -> None:
        engine = _make_engine(max_questions=4)
        result = engine.run_default()

        questions = engine.get_default_questions()
        assert len(result.raw_transcript) == len(questions)
        for i, (q, _) in enumerate(result.raw_transcript):
            assert q == questions[i]

    def test_transcript_includes_provided_answers(self) -> None:
        engine = _make_engine()
        answers = {"What does this project do?": "Something cool"}
        result = engine.run_default(answers)

        matched = [(q, a) for q, a in result.raw_transcript if q == "What does this project do?"]
        assert len(matched) == 1
        assert matched[0][1] == "Something cool"

    def test_none_answers_defaults_to_empty(self) -> None:
        engine = _make_engine()
        result = engine.run_default(None)

        assert result.answers == {}


class TestInterviewResult:
    def test_default_values(self) -> None:
        result = InterviewResult()

        assert result.answers == {}
        assert result.project_summary == ""
        assert result.raw_transcript == []

    def test_with_values(self) -> None:
        answers = {"q1": "a1"}
        transcript: list[tuple[str, str]] = [("q1", "a1")]
        result = InterviewResult(
            answers=answers,
            project_summary="summary text",
            raw_transcript=transcript,
        )

        assert result.answers == answers
        assert result.project_summary == "summary text"
        assert result.raw_transcript == transcript


class TestBuildResult:
    def test_builds_summary_from_answers(self) -> None:
        engine = _make_engine()
        answers = {"What is it?": "A tool", "How to test?": "pytest"}
        transcript = [("What is it?", "A tool"), ("How to test?", "pytest")]
        result = engine._build_result(answers, transcript)

        assert "What is it?: A tool" in result.project_summary
        assert "How to test?: pytest" in result.project_summary

    def test_empty_answers_gives_no_answers_message(self) -> None:
        engine = _make_engine()
        result = engine._build_result({}, [])

        assert result.project_summary == "No answers provided."


class TestPreseededAnswers:
    def test_preseeded_answers_passed_to_run_default(self) -> None:
        engine = _make_engine(
            preseeded_answers={"What does this project do?": "A CLI tool"},
        )
        result = engine.run_default()
        assert result.answers["What does this project do?"] == "A CLI tool"

    def test_preseeded_answers_merged_with_provided(self) -> None:
        engine = _make_engine(
            preseeded_answers={"What does this project do?": "A CLI tool"},
        )
        result = engine.run_default(
            answers={"How do you run tests?": "pytest"},
        )
        assert result.answers["What does this project do?"] == "A CLI tool"
        assert result.answers["How do you run tests?"] == "pytest"

    def test_provided_answers_override_preseeded(self) -> None:
        engine = _make_engine(
            preseeded_answers={"What does this project do?": "original"},
        )
        result = engine.run_default(
            answers={"What does this project do?": "overridden"},
        )
        assert result.answers["What does this project do?"] == "overridden"

    def test_preseeded_answers_in_summary(self) -> None:
        engine = _make_engine(
            preseeded_answers={"What does this project do?": "A CLI tool"},
        )
        result = engine.run_default()
        assert "A CLI tool" in result.project_summary

    def test_empty_preseeded_answers(self) -> None:
        engine = _make_engine()
        result = engine.run_default()
        assert result.answers == {}
        assert result.project_summary == "No answers provided."


class TestMapExtractedToAnswers:
    def test_maps_all_fields(self) -> None:
        engine = _make_engine()
        extracted = {
            "overview": "A splitwise clone",
            "language": "python",
            "framework": "fastapi",
            "entry_point": "app/main.py",
            "build_commands": "uv sync",
            "test_commands": "pytest",
            "lint_commands": "ruff",
            "dependencies": "fastapi, click",
            "integrations": "splitwise API",
            "constraints": "No cloud calls",
            "directory_structure": "src/ for code",
            "active_work": "import feature",
            "versioning": "semver",
            "extra": "must support CSV import",
        }
        answers = engine._map_extracted_to_answers(extracted)
        assert answers["What does this project do?"] == "A splitwise clone"
        assert answers["What's the main entry point?"] == "app/main.py"
        assert answers["Anything else agents should know that I haven't asked about?"] == "must support CSV import"

    def test_skips_empty_fields(self) -> None:
        engine = _make_engine()
        extracted = {"overview": "A tool", "language": "", "framework": "none"}
        answers = engine._map_extracted_to_answers(extracted)
        assert len(answers) == 1
        assert "What does this project do?" in answers

    def test_empty_extracted(self) -> None:
        engine = _make_engine()
        answers = engine._map_extracted_to_answers({})
        assert answers == {}


class TestTranscriptToAnswers:
    def test_converts_transcript(self) -> None:
        engine = _make_engine()
        transcript = [("What is it?", "A tool"), ("How to test?", "pytest")]
        answers = engine._transcript_to_answers(transcript)
        assert answers == {"What is it?": "A tool", "How to test?": "pytest"}

    def test_skips_empty_answers(self) -> None:
        engine = _make_engine()
        transcript = [("What is it?", "A tool"), ("Skip this?", "")]
        answers = engine._transcript_to_answers(transcript)
        assert answers == {"What is it?": "A tool"}

    def test_empty_transcript(self) -> None:
        engine = _make_engine()
        answers = engine._transcript_to_answers([])
        assert answers == {}


class TestBuildOpeningContext:
    def test_with_preseeded_description(self) -> None:
        engine = _make_engine(preseeded_answers={"What does this project do?": "a splitwise clone"})
        ctx = engine._build_opening_context()
        assert "splitwise clone" in ctx

    def test_without_preseeded(self) -> None:
        engine = _make_engine()
        ctx = engine._build_opening_context()
        assert "new project" in ctx.lower()

    def test_includes_detected_info(self) -> None:
        engine = _make_engine(language="python", framework="fastapi", test_runner="pytest")
        ctx = engine._build_opening_context()
        assert "python" in ctx
        assert "fastapi" in ctx
        assert "pytest" in ctx


class TestGetLlmClient:
    def test_returns_none_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("VILLAGE_LLM_PROVIDER", raising=False)
        engine = _make_engine()
        assert engine._get_llm_client() is None

    def test_returns_client_with_openrouter_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        engine = _make_engine()
        assert engine._get_llm_client() is not None

    @pytest.mark.skipif(
        "not os.environ.get('OLLAMA_HOST')",
        reason="Ollama not available in CI",
    )
    def test_returns_client_with_ollama(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VILLAGE_LLM_PROVIDER", "ollama")
        engine = _make_engine()
        assert engine._get_llm_client() is not None

    @pytest.mark.skipif(
        "not os.environ.get('CI') is None and not os.environ.get('VENICE_API_KEY')",
        reason="Venice API not available in CI",
    )
    def test_returns_client_with_venice(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VILLAGE_LLM_PROVIDER", "venice")
        monkeypatch.setenv("VENICE_API_KEY", "venice-key")
        engine = _make_engine()
        assert engine._get_llm_client() is not None

    @pytest.mark.skipif(
        "not os.environ.get('ZAI_API_KEY')",
        reason="ZAI API not available in CI",
    )
    def test_returns_client_with_zai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VILLAGE_LLM_PROVIDER", "zai")
        monkeypatch.setenv("ZAI_API_KEY", "zai-key")
        engine = _make_engine()
        assert engine._get_llm_client() is not None

    def test_returns_client_with_venice_fallback_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VILLAGE_LLM_PROVIDER", "venice")
        monkeypatch.delenv("VENICE_API_KEY", raising=False)
        monkeypatch.setenv("OPENROUTER_API_KEY", "fallback-key")
        engine = _make_engine()
        assert engine._get_llm_client() is not None


class TestLoadGlobalConfig:
    def test_returns_empty_when_no_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert _load_global_config() == {}

    def test_reads_provider_from_global_config(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        config_dir = tmp_path / "village"
        config_dir.mkdir()
        (config_dir / "config").write_text(
            "[llm]\nprovider = venice\nmodel = venice/llama\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        config = _load_global_config()
        assert config.get("llm.provider") == "venice"
        assert config.get("llm.model") == "venice/llama"

    def test_get_global_config_reads_provider(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        config_dir = tmp_path / "village"
        config_dir.mkdir()
        (config_dir / "config").write_text(
            "[llm]\nprovider = venice\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.setenv("OPENROUTER_API_KEY", "venice-key")
        gcfg = get_global_config()
        assert gcfg.llm.provider == "venice"


class TestConfirmSummary:
    def test_confirmed_returns_answers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        engine = _make_engine()
        answers = {"What does this project do?": "A tool"}
        transcript = [("What does this project do?", "A tool")]
        monkeypatch.setattr("click.confirm", lambda *a, **kw: True)
        monkeypatch.setattr("click.echo", lambda *a, **kw: None)
        result = engine._confirm_summary(answers, transcript)
        assert result.answers == answers
        assert "A tool" in result.project_summary

    def test_declined_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        engine = _make_engine()
        answers = {"What does this project do?": "A tool"}
        transcript = [("What does this project do?", "A tool")]
        monkeypatch.setattr("click.confirm", lambda *a, **kw: False)
        monkeypatch.setattr("click.echo", lambda *a, **kw: None)
        result = engine._confirm_summary(answers, transcript)
        assert result.answers == {}

    def test_empty_answers_shows_no_details(self, monkeypatch: pytest.MonkeyPatch) -> None:
        engine = _make_engine()
        echoed: list[str] = []
        monkeypatch.setattr("click.confirm", lambda *a, **kw: True)
        monkeypatch.setattr("click.echo", lambda msg="", **kw: echoed.append(msg) if msg else None)
        result = engine._confirm_summary({}, [])
        assert any("No details" in line for line in echoed if isinstance(line, str))
        assert result.answers == {}

    def test_keyboard_interrupt_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        engine = _make_engine()
        answers = {"What does this project do?": "A tool"}
        transcript = [("What does this project do?", "A tool")]

        def raise_abort(*a: object, **kw: object) -> None:
            raise KeyboardInterrupt()

        monkeypatch.setattr("click.confirm", raise_abort)
        monkeypatch.setattr("click.echo", lambda *a, **kw: None)
        result = engine._confirm_summary(answers, transcript)
        assert result.answers == {}


class TestFormatConversation:
    def test_formats_roles(self) -> None:
        engine = _make_engine()
        conversation = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
            {"role": "user", "content": "what's up?"},
        ]
        text = engine._format_conversation(conversation)
        assert "[User]: hello" in text
        assert "[Assistant]: hi there" in text
        assert "[User]: what's up?" in text

    def test_empty_conversation(self) -> None:
        engine = _make_engine()
        assert engine._format_conversation([]) == ""
