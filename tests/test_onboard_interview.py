from village.config import OnboardConfig
from village.onboard.detector import ProjectInfo
from village.onboard.interview import _DEFAULT_QUESTIONS, InterviewEngine, InterviewResult
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
    return InterviewEngine(config=config, project_info=project_info, scaffold=scaffold)


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


class TestBuildSystemPrompt:
    def test_includes_max_questions(self) -> None:
        engine = _make_engine(max_questions=7)
        prompt = engine._build_system_prompt()

        assert "7" in prompt
        assert "maximum of 7 questions" in prompt

    def test_mentions_interview_complete(self) -> None:
        engine = _make_engine()
        prompt = engine._build_system_prompt()

        assert "INTERVIEW_COMPLETE" in prompt


class TestBuildContextSeed:
    def test_includes_project_name(self) -> None:
        engine = _make_engine(project_name="my-cool-app")
        seed = engine._build_context_seed()

        assert "Project: my-cool-app" in seed

    def test_includes_language_when_known(self) -> None:
        engine = _make_engine(language="python")
        seed = engine._build_context_seed()

        assert "Language: python" in seed

    def test_omits_language_when_unknown(self) -> None:
        engine = _make_engine(language="unknown")
        seed = engine._build_context_seed()

        assert "Language:" not in seed

    def test_includes_framework(self) -> None:
        engine = _make_engine(framework="fastapi")
        seed = engine._build_context_seed()

        assert "Framework: fastapi" in seed

    def test_omits_framework_when_none(self) -> None:
        engine = _make_engine(framework=None)
        seed = engine._build_context_seed()

        assert "Framework:" not in seed

    def test_includes_build_tool(self) -> None:
        engine = _make_engine(build_tool="uv")
        seed = engine._build_context_seed()

        assert "Build tool: uv" in seed

    def test_includes_test_runner(self) -> None:
        engine = _make_engine(test_runner="pytest")
        seed = engine._build_context_seed()

        assert "Test runner: pytest" in seed

    def test_includes_linter(self) -> None:
        engine = _make_engine(linter="ruff")
        seed = engine._build_context_seed()

        assert "Linter: ruff" in seed

    def test_includes_conventions(self) -> None:
        engine = _make_engine(conventions=["Use pathlib.Path", "Type hints required", "No print()"])
        seed = engine._build_context_seed()

        assert "Common conventions:" in seed
        assert "Use pathlib.Path" in seed

    def test_limits_conventions_to_three(self) -> None:
        engine = _make_engine(conventions=["conv1", "conv2", "conv3", "conv4", "conv5"])
        seed = engine._build_context_seed()

        assert "conv1" in seed
        assert "conv4" not in seed


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
