from dataclasses import dataclass, field
from pathlib import Path

from village.onboard.detector import ProjectInfo
from village.onboard.models import InterviewResult
from village.onboard.scaffolds import ScaffoldTemplate
from village.scribe.curate import CONVENTIONAL_DIRS, CONVENTIONAL_ROOT_FILES, DEFAULT_EXCLUDE_PREFIXES


@dataclass
class GenerationResult:
    agents_md: str = ""
    readme_md: str = ""
    wiki_seeds: list[tuple[str, str]] = field(default_factory=list)
    wiki_path: Path = field(default_factory=Path)


class Generator:
    def __init__(
        self,
        project_info: ProjectInfo,
        scaffold: ScaffoldTemplate,
        interview: InterviewResult,
        project_root: Path,
    ) -> None:
        self.project_info = project_info
        self.scaffold = scaffold
        self.interview = interview
        self.project_root = project_root

    def _build_agents_md(self) -> str:
        sections: list[str] = []
        sections.append(f"# {self.project_info.project_name} - Agent Development Guide")
        sections.append("")

        sections.append("## Overview")
        overview = self._get_answer("What does this project do?", "Project description pending.")
        sections.append(overview)
        sections.append("")

        sections.append("## Build, Lint, and Test Commands")
        sections.append("```bash")

        user_build = self._get_answer("How do you run tests?", "")
        user_lint = self._get_answer("What linting or formatting tools do you use?", "")

        build_cmds = self.scaffold.build_commands
        test_cmds = self.scaffold.test_commands
        lint_cmds = self.scaffold.lint_commands

        for cmd in scaffold_section_label(build_cmds, "Build"):
            sections.append(f"{cmd}")
        for cmd in scaffold_section_label(test_cmds, "Test"):
            sections.append(f"{cmd}")
        if user_build and not any(user_build in c for c in test_cmds):
            sections.append(f"# Test (user): {user_build}")
        for cmd in scaffold_section_label(lint_cmds, "Lint"):
            sections.append(f"{cmd}")
        if user_lint and not any(user_lint in c for c in lint_cmds):
            sections.append(f"# Lint (user): {user_lint}")
        for cmd in scaffold_section_label(self.scaffold.typecheck_commands, "Typecheck"):
            sections.append(f"{cmd}")
        sections.append("```")
        sections.append("")

        sections.append("## Code Style Guidelines")
        conventions = list(self.scaffold.conventions)
        conventions_answer = self._get_answer("What hard rules or constraints must agents follow?", "")
        if conventions_answer:
            for line in conventions_answer.split("\n"):
                line = line.strip().lstrip("- ").strip()
                if line:
                    conventions.append(line)
        for conv in conventions:
            sections.append(f"- {conv}")
        sections.append("")

        sections.append("## Project Structure")
        if self.scaffold.directory_structure:
            sections.append("```")
            for path, desc in self.scaffold.directory_structure.items():
                sections.append(f"{path}  # {desc}")
            sections.append("```")
        else:
            arch = self._get_answer("What are the key directories and their roles?", "")
            if arch:
                sections.append("```")
                sections.append(arch)
                sections.append("```")
        sections.append("")

        sections.append("## Key Integration Points")
        integrations = self._get_answer("What external services or tools does this integrate with?", "None specified.")
        sections.append(integrations)
        sections.append("")

        sections.append("## Constraints")
        constraints = self._get_answer("What hard rules or constraints must agents follow?", "None specified.")
        sections.append(constraints)
        sections.append("")

        extra = self._get_answer("Anything else agents should know", "")
        if extra:
            sections.append("## Additional Notes")
            sections.append(extra)
            sections.append("")

        return "\n".join(sections)

    def _build_readme_md(self) -> str:
        sections: list[str] = []

        sections.append(f"# {self.project_info.project_name}")
        sections.append("")

        overview = self._get_answer("What does this project do?", "Project description goes here.")
        sections.append(overview)
        sections.append("")

        sections.append("## Getting Started")
        sections.append("```bash")
        if self.scaffold.build_commands:
            sections.append(f"{self.scaffold.build_commands[0]}")
        if self.scaffold.test_commands:
            sections.append(f"{self.scaffold.test_commands[0]}")
        sections.append("```")
        sections.append("")

        deps = self._get_answer("What are the key dependencies?", "")
        if deps:
            sections.append("## Dependencies")
            sections.append(deps)
            sections.append("")

        return "\n".join(sections)

    def _build_wiki_seeds(self) -> list[tuple[str, str]]:
        seeds: list[tuple[str, str]] = []

        overview = self._get_answer("What does this project do?", "")
        entry = self._get_answer("What's the main entry point?", "")
        deps = self._get_answer("What are the key dependencies?", "")

        if overview:
            content = f"# Project Overview\n\n{overview}"
            if entry:
                content += f"\n\n## Entry Point\n\n{entry}"
            if deps:
                content += f"\n\n## Key Dependencies\n\n{deps}"
            seeds.append(("project-overview.md", content))

        conventions = list(self.scaffold.conventions)
        constraints = self._get_answer("What hard rules or constraints must agents follow?", "")
        if constraints:
            conventions.extend(line.strip().lstrip("- ").strip() for line in constraints.split("\n") if line.strip())
        if conventions:
            content = "# Conventions\n\n" + "\n".join(f"- {c}" for c in conventions)
            seeds.append(("conventions.md", content))

        active = self._get_answer("What's currently being worked on?", "")
        if active:
            content = f"# Active Development\n\n{active}"
            seeds.append(("active-development.md", content))

        has_content = any(a for _, a in self.interview.raw_transcript) or any(m for _, m in self.interview.preamble)
        if has_content:
            transcript_lines: list[str] = [
                "# Onboarding Interview",
                "",
                "Transcript of the initial project interview. This provides rich"
                " context about the project's goals, design decisions, and the"
                " creator's intent. Useful for scribe queries and future onboarding.",
                "",
            ]
            for role, message in self.interview.preamble:
                transcript_lines.append(f"**{role}:** {message}")
                transcript_lines.append("")
            for q, a in self.interview.raw_transcript:
                transcript_lines.append(f"**Q:** {q}")
                transcript_lines.append(f"**A:** {a}")
                transcript_lines.append("")
            seeds.append(("interview-transcript.md", "\n".join(transcript_lines)))

        return seeds

    def _get_answer(self, question_substring: str, default: str) -> str:
        for q, a in self.interview.answers.items():
            if not a:
                continue
            q_lower = q.lower()
            sub_lower = question_substring.lower()
            if sub_lower in q_lower or q_lower in sub_lower:
                return a
        return default

    @staticmethod
    def _is_excluded(rel_path: str) -> bool:
        return any(
            rel_path.startswith(prefix) or rel_path == prefix.rstrip("/")
            for prefix in DEFAULT_EXCLUDE_PREFIXES
        )

    def _discover_existing_docs(
        self, existing_seed_names: set[str]
    ) -> list[tuple[str, str]]:
        onboard_generated = {"README.md", "AGENTS.md"}
        seeds: list[tuple[str, str]] = []

        for name in CONVENTIONAL_ROOT_FILES:
            if name in onboard_generated:
                continue
            if name in existing_seed_names:
                continue
            file_path = self.project_root / name
            if not file_path.is_file():
                continue
            if self._is_excluded(name):
                continue
            content = file_path.read_text(encoding="utf-8")
            seeds.append((name, content))

        for dir_name in CONVENTIONAL_DIRS:
            dir_path = self.project_root / dir_name
            if not dir_path.is_dir():
                continue
            for md_file in dir_path.rglob("*.md"):
                rel = str(md_file.relative_to(self.project_root))
                if self._is_excluded(rel):
                    continue
                if rel in existing_seed_names:
                    continue
                content = md_file.read_text(encoding="utf-8")
                seeds.append((rel, content))

        return seeds

    def generate(self) -> GenerationResult:
        wiki_path = self.project_root / "wiki"
        wiki_seeds = self._build_wiki_seeds()

        existing_names = {name for name, _ in wiki_seeds}
        wiki_seeds.extend(self._discover_existing_docs(existing_names))

        return GenerationResult(
            agents_md=self._build_agents_md(),
            readme_md=self._build_readme_md(),
            wiki_seeds=wiki_seeds,
            wiki_path=wiki_path,
        )

    def write_files(self, result: GenerationResult) -> list[str]:
        created: list[str] = []

        agents_path = self.project_root / "AGENTS.md"
        agents_path.write_text(result.agents_md, encoding="utf-8")
        created.append("AGENTS.md")

        readme_path = self.project_root / "README.md"
        readme_path.write_text(result.readme_md, encoding="utf-8")
        created.append("README.md")

        if result.wiki_seeds:
            ingest_dir = result.wiki_path / "ingest"
            ingest_dir.mkdir(parents=True, exist_ok=True)
            for filename, content in result.wiki_seeds:
                seed_path = ingest_dir / filename
                seed_path.write_text(content, encoding="utf-8")
                created.append(f"wiki/ingest/{filename}")

        return created


def scaffold_section_label(commands: list[str], label: str) -> list[str]:
    return [f"# {label}: {cmd}" for cmd in commands]
