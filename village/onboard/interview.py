from dataclasses import dataclass, field

import click

from village.config import OnboardConfig
from village.onboard.detector import ProjectInfo
from village.onboard.scaffolds import ScaffoldTemplate


@dataclass
class InterviewResult:
    answers: dict[str, str] = field(default_factory=dict)
    project_summary: str = ""
    raw_transcript: list[tuple[str, str]] = field(default_factory=list)


_DEFAULT_QUESTIONS = [
    "What does this project do?",
    "What's the main entry point?",
    "How do you run tests?",
    "What linting or formatting tools do you use?",
    "What are the key dependencies?",
    "What external services or tools does this integrate with?",
    "What hard rules or constraints must agents follow?",
    "What are the key directories and their roles?",
    "What's currently being worked on?",
    "Does this project have a release or versioning strategy?",
    "Anything else agents should know that I haven't asked about?",
]


class InterviewEngine:
    def __init__(
        self,
        config: OnboardConfig,
        project_info: ProjectInfo,
        scaffold: ScaffoldTemplate,
        preseeded_answers: dict[str, str] | None = None,
    ) -> None:
        self.config = config
        self.project_info = project_info
        self.scaffold = scaffold
        self.preseeded_answers = preseeded_answers or {}

    def get_default_questions(self) -> list[str]:
        questions = list(_DEFAULT_QUESTIONS)
        if self.project_info.language == "unknown":
            questions.insert(1, "What programming language is this project written in?")
        if not self.project_info.test_runner:
            idx = next((i for i, q in enumerate(questions) if "tests" in q.lower()), 2)
            questions[idx] = "Do you have tests? What framework and commands do you use?"
        return questions[: self.config.max_questions]

    def run_default(self, answers: dict[str, str] | None = None) -> InterviewResult:
        if answers is None:
            answers = {}

        merged = dict(self.preseeded_answers)
        merged.update(answers)

        questions = self.get_default_questions()
        transcript: list[tuple[str, str]] = []

        for question in questions:
            answer = merged.get(question, "")
            transcript.append((question, answer))

        summary_parts = [f"{k}: {v}" for k, v in merged.items() if v]
        summary = "\n".join(summary_parts) if summary_parts else "No answers provided."

        return InterviewResult(
            answers=dict(merged),
            project_summary=summary,
            raw_transcript=transcript,
        )

    def run_interactive(self) -> InterviewResult:
        questions = self.get_default_questions()
        answers: dict[str, str] = dict(self.preseeded_answers)
        transcript: list[tuple[str, str]] = []

        preseeded_count = sum(1 for q in questions if q in self.preseeded_answers)
        remaining = len(questions) - preseeded_count

        if self.project_info.language != "unknown":
            click.echo(f"\nProject detected: {self.project_info.language}")
            if self.project_info.framework:
                click.echo(f"Framework: {self.project_info.framework}")
        else:
            click.echo("\nI'll need more details to determine the project type.")
        if remaining > 0:
            click.echo(f"I'll ask {remaining} question{'s' if remaining != 1 else ''}.\n")
        else:
            click.echo("All questions answered.\n")
        click.echo("Type your answer and press Enter. Empty line to skip. 'done' to finish.\n")

        for question in questions:
            if question in self.preseeded_answers:
                answer = self.preseeded_answers[question]
                transcript.append((question, answer))
                continue

            click.echo(f"? {question}")
            lines: list[str] = []

            try:
                while True:
                    try:
                        line = input()
                    except EOFError:
                        break

                    if not lines and line.lower() == "done":
                        click.echo("")
                        return self._build_result(answers, transcript)

                    if not lines and line.lower() == "skip":
                        break

                    if line == "" and lines:
                        break
                    if line == "" and not lines:
                        break

                    lines.append(line)
            except KeyboardInterrupt:
                click.echo("\n")
                break

            answer = "\n".join(lines)
            answers[question] = answer
            transcript.append((question, answer))
            click.echo("")

        return self._build_result(answers, transcript)

    def _build_result(self, answers: dict[str, str], transcript: list[tuple[str, str]]) -> InterviewResult:
        summary_parts = [f"{k}: {v}" for k, v in answers.items() if v]
        summary = "\n".join(summary_parts) if summary_parts else "No answers provided."

        return InterviewResult(
            answers=answers,
            project_summary=summary,
            raw_transcript=transcript,
        )
