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
