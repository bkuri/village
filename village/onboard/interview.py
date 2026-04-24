import json
import logging
import re
from typing import TYPE_CHECKING

import click

from village.config import OnboardConfig
from village.onboard.detector import ProjectInfo
from village.onboard.models import InterviewResult
from village.onboard.scaffolds import ScaffoldTemplate
from village.prompt import sync_confirm, sync_prompt

if TYPE_CHECKING:
    from village.llm.client import LLMClient

logger = logging.getLogger(__name__)


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

_SYSTEM_PROMPT = """\
You are a project onboarding assistant. Your job is to help the user \
describe their project through a natural conversation.

GOAL: In {max_questions} exchanges or fewer, learn enough about this project \
to generate a useful AGENTS.md, README.md, and initial wiki pages for AI agents.

WHAT TO EXTRACT (silently track these, do NOT ask about them directly):
- Project overview and purpose
- Programming language and framework
- Entry points
- Build, test, lint commands
- Key dependencies
- External integrations
- Hard rules / constraints for agents
- Directory structure
- Current work in progress
- Versioning strategy

RULES:
1. Each question must build on the LAST answer. Never ask a disconnected question.
2. Ask ONE focused question at a time. Never list multiple questions.
3. Be conversational and brief. 1-2 sentences max per response.
4. When the user says "no idea", "not sure", "none", etc., infer what you can \
and move to the most useful next topic. Do NOT repeat or rephrase the same question.
5. If the project is brand new (no code yet), focus on what it SHOULD do, not \
what tools it currently uses. Help refine the concept.
6. When you have enough information, respond with exactly: <complete/>
7. Output ONLY your conversational response. No labels, no prefixes, no markdown headers.

EXAMPLE FLOW for "a splitwise clone":
  Good: "A splitwise clone — so splitting expenses between people. \
What features matter most: group expenses, recurring bills, debt simplification?"
  Good (after answer): "Got it. Should users be able to import data from \
existing apps or spreadsheets?"
  Bad: "What programming language is this project written in?" (too specific too early)
  Bad: "What are the key dependencies?" (irrelevant for a new project)"""


_EXTRACTION_PROMPT = """\
Based on the following interview transcript, extract structured project information.
Return a JSON object with these keys. Use empty strings for anything unknown.

Keys:
- "overview": What the project does (2-3 sentences)
- "language": Primary programming language
- "framework": Framework or "none"
- "entry_point": Main entry point
- "build_commands": How to build (comma-separated)
- "test_commands": How to test (comma-separated)
- "lint_commands": Linting/formatting tools (comma-separated)
- "dependencies": Key dependencies (comma-separated)
- "integrations": External services or tools
- "constraints": Hard rules agents must follow
- "directory_structure": Key directories and roles
- "active_work": What's currently being worked on
- "versioning": Release/versioning strategy
- "extra": Anything else agents should know

TRANSCRIPT:
{transcript}

Return ONLY the JSON object, no other text."""


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
        llm = self._get_llm_client()
        if llm is not None:
            try:
                return self._run_conversation(llm)
            except (ValueError, ConnectionError, TimeoutError):
                logger.warning("LLM interview failed, falling back to fixed questions", exc_info=True)

        return self._run_fixed_interactive()

    def _run_conversation(self, llm: "LLMClient") -> InterviewResult:
        transcript: list[tuple[str, str]] = []
        conversation: list[dict[str, str]] = []
        max_turns = self.config.max_questions

        system = _SYSTEM_PROMPT.format(max_questions=max_turns)

        opening_context = self._build_opening_context()
        conversation.append({"role": "user", "content": opening_context})

        first_question = self._sanitize_response(
            llm.call(
                prompt=opening_context,
                system_prompt=system,
                max_tokens=256,
                timeout=30,
            ).strip()
        )

        if first_question.startswith("<complete"):
            return self._build_result({}, [])

        current_question = first_question
        turn_count = 0

        while turn_count < max_turns:
            click.echo(f"\n{current_question}")
            try:
                user_input = sync_prompt("", show_default=False, prompt_suffix="  ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input or user_input.lower() == "done":
                break

            transcript.append((current_question, user_input))
            conversation.append({"role": "assistant", "content": current_question})
            conversation.append({"role": "user", "content": user_input})
            turn_count += 1

            conversation_text = self._format_conversation(conversation)
            response = llm.call(
                prompt=conversation_text,
                system_prompt=system,
                max_tokens=256,
                timeout=30,
            ).strip()

            if response.startswith("<complete"):
                break

            current_question = self._sanitize_response(response)

        click.echo("")

        extracted = self._extract_structured(llm, transcript)

        answers: dict[str, str] = {}
        if extracted:
            answers = self._map_extracted_to_answers(extracted)

        transcript_answers = self._transcript_to_answers(transcript)
        merged = self._merge_answers(answers, transcript_answers)
        preseeded = dict(self.preseeded_answers)
        for k, v in preseeded.items():
            if v:
                merged[k] = v

        return self._confirm_summary(merged, transcript)

    def _build_opening_context(self) -> str:
        parts: list[str] = []

        if self.preseeded_answers:
            desc = self.preseeded_answers.get("What does this project do?", "")
            if desc:
                parts.append(f"The user wants to build: {desc}")
        else:
            parts.append("The user is starting a new project and needs help describing it.")

        if self.project_info.language != "unknown":
            parts.append(f"Auto-detected language: {self.project_info.language}")
        if self.project_info.framework:
            parts.append(f"Auto-detected framework: {self.project_info.framework}")
        if self.project_info.test_runner:
            parts.append(f"Auto-detected test runner: {self.project_info.test_runner}")

        parts.append(
            "Ask your first question to start the conversation. Build on what you know to refine the project concept."
        )

        return " ".join(parts)

    def _format_conversation(self, conversation: list[dict[str, str]]) -> str:
        """Format conversation history as readable text for the LLM."""
        lines: list[str] = []
        for msg in conversation:
            role = msg["role"].capitalize()
            lines.append(f"[{role}]: {msg['content']}")
        return "\n".join(lines)

    def _sanitize_response(self, response: str) -> str:
        """Strip hallucinated role-prefixed turns from LLM output.

        The LLM sees conversation history formatted with [User]: / [Assistant]:
        prefixes and may continue that pattern, fabricating user responses.
        """
        response = re.split(r"\n\[User\]:", response, maxsplit=1)[0]
        response = re.split(r"\n\[Assistant\]:", response, maxsplit=1)[0]
        return response.strip()

    def _extract_structured(self, llm: "LLMClient", transcript: list[tuple[str, str]]) -> dict[str, str] | None:
        lines: list[str] = []
        for q, a in transcript:
            if a:
                lines.append(f"Q: {q}\nA: {a}")
        if not lines:
            return None

        transcript_text = "\n\n".join(lines)
        prompt = _EXTRACTION_PROMPT.format(transcript=transcript_text)

        try:
            raw = llm.call(prompt=prompt, system_prompt="Return only valid JSON.", max_tokens=1024, timeout=30)
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
                cleaned = cleaned.rsplit("```", 1)[0]
            result: dict[str, str] = json.loads(cleaned)
            return result
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to extract structured data: {e}")
            return None

    def _map_extracted_to_answers(self, extracted: dict[str, str]) -> dict[str, str]:
        mapping = {
            "overview": "What does this project do?",
            "entry_point": "What's the main entry point?",
            "test_commands": "How do you run tests?",
            "lint_commands": "What linting or formatting tools do you use?",
            "dependencies": "What are the key dependencies?",
            "integrations": "What external services or tools does this integrate with?",
            "constraints": "What hard rules or constraints must agents follow?",
            "directory_structure": "What are the key directories and their roles?",
            "active_work": "What's currently being worked on?",
            "versioning": "Does this project have a release or versioning strategy?",
            "extra": "Anything else agents should know that I haven't asked about?",
        }
        answers: dict[str, str] = {}
        for key, question in mapping.items():
            val = extracted.get(key, "").strip()
            if val:
                answers[question] = val
        return answers

    def _transcript_to_answers(self, transcript: list[tuple[str, str]]) -> dict[str, str]:
        answers: dict[str, str] = {}
        for q, a in transcript:
            if a:
                answers[q] = a
        return answers

    def _merge_answers(self, extracted: dict[str, str], transcript: dict[str, str]) -> dict[str, str]:
        """Merge LLM-extracted answers with raw transcript answers.

        Prefers the user's actual words from the transcript when a question
        substring matches. Falls back to LLM extraction for topics not
        covered in the transcript. This ensures the generated docs contain
        the user's voice, not LLM summaries.
        """
        merged: dict[str, str] = {}

        for key, val in extracted.items():
            if val:
                merged[key] = val

        for q, a in transcript.items():
            matched = False
            for key in list(merged.keys()):
                if q.lower() in key.lower() or key.lower() in q.lower():
                    merged[key] = a
                    matched = True
                    break
            if not matched and a:
                merged[q] = a

        return merged

    def _run_fixed_interactive(self) -> InterviewResult:
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
            try:
                answer = sync_prompt("", show_default=False, prompt_suffix="  ").strip()
            except (EOFError, KeyboardInterrupt):
                click.echo("")
                return self._build_result(answers, transcript)

            if answer.lower() == "done":
                click.echo("")
                return self._build_result(answers, transcript)

            answers[question] = answer
            transcript.append((question, answer))
            click.echo("")

        return self._confirm_summary(answers, transcript)

    def _confirm_summary(self, answers: dict[str, str], transcript: list[tuple[str, str]]) -> InterviewResult:
        click.echo("--- Summary ---")
        if answers:
            for key, val in answers.items():
                label = key.rstrip("?").strip()
                click.echo(f"  {label}")
                for line in val.split("\n"):
                    click.echo(f"    {line}")
        else:
            click.echo("  No details captured.")

        click.echo("")
        confirmed = self._prompt_confirm("Create project with these details?")
        if not confirmed:
            click.echo("Aborted.")
            return self._build_result({}, [])

        return self._build_result(answers, transcript)

    def _prompt_confirm(self, question: str) -> bool:
        try:
            response = sync_confirm(f"  {question}", default=True)
            return bool(response)
        except (click.exceptions.Abort, EOFError, KeyboardInterrupt):
            click.echo("")
            return False

    def _build_result(self, answers: dict[str, str], transcript: list[tuple[str, str]]) -> InterviewResult:
        summary_parts = [f"{k}: {v}" for k, v in answers.items() if v]
        summary = "\n".join(summary_parts) if summary_parts else "No answers provided."

        return InterviewResult(
            answers=answers,
            project_summary=summary,
            raw_transcript=transcript,
        )

    def _get_llm_client(self) -> "LLMClient | None":
        import os

        try:
            from village.config import LLMConfig, get_global_config
            from village.llm.factory import get_llm_client as _get_llm_client

            global_cfg = get_global_config()

            interview_model = self.config.interview_model
            if "/" not in interview_model:
                raise ValueError(f"Invalid interview_model format (expected provider/model): {interview_model}")

            provider, model = interview_model.split("/", 1)

            env_provider = os.getenv("VILLAGE_LLM_PROVIDER")
            if env_provider:
                provider = env_provider

            provider_key_envs = {
                "venice": "VENICE_API_KEY",
                "zai": "ZAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
            }
            api_key_env = provider_key_envs.get(provider, global_cfg.llm.api_key_env)
            if not os.getenv(api_key_env):
                api_key_env = global_cfg.llm.api_key_env

            global_cfg.llm = LLMConfig(
                provider=provider,
                model=model,
                api_key_env=api_key_env,
                timeout=global_cfg.llm.timeout,
                max_tokens=global_cfg.llm.max_tokens,
            )
            return _get_llm_client(global_cfg)
        except ValueError:
            logger.debug("No LLM client available for interview (missing API key or config)")
            return None
        except Exception:
            logger.warning("Unexpected error creating LLM client", exc_info=True)
            return None
