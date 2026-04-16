"""Analyzer for git hygiene issues."""

import subprocess

from village.doctor.base import Analyzer, AnalyzerResult, Finding
from village.logging import get_logger
from village.probes.tools import SubprocessError, run_command

logger = get_logger(__name__)


class GitAnalyzer(Analyzer):
    """Detect git hygiene issues like stale branches."""

    name = "git"
    description = "Detect stale branches and worktree issues"
    category = "git"

    def is_available(self) -> bool:
        """Check if we're in a git repo."""
        try:
            run_command(
                ["git", "rev-parse", "--is-inside-work-tree"],
                capture=True,
                check=True,
            )
            return True
        except (SubprocessError, FileNotFoundError):
            return False

    def run(self) -> AnalyzerResult:
        """Check for git issues."""
        findings = []

        try:
            result = subprocess.run(
                ["git", "branch", "--merged", "main"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            for line in result.stdout.split("\n"):
                line = line.strip()
                if line and not line.startswith("*") and line not in ("main", "master"):
                    findings.append(
                        Finding(
                            id=f"git-branch-{hash(line) % 10000:04d}",
                            title=f"Merged branch: {line}",
                            description=(
                                f"Branch '{line}' has been merged into main and can be deleted.\n\n"
                                f"Run `git branch -d {line}` to remove."
                            ),
                            severity="low",
                            category="git",
                            metadata={"branch": line, "type": "merged"},
                        )
                    )
        except Exception as e:
            logger.warning(f"Failed to check merged branches: {e}")

        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            worktrees = []
            current: dict[str, str] = {}
            for line in result.stdout.split("\n"):
                if line.startswith("worktree "):
                    if current:
                        worktrees.append(current)
                    current = {"path": line.split(" ", 1)[1]}
                elif line.startswith("HEAD "):
                    current["head"] = line.split(" ", 1)[1]
                elif line.startswith("branch "):
                    current["branch"] = line.split(" ", 1)[1]
            if current:
                worktrees.append(current)

            for wt in worktrees:
                path = wt.get("path", "")
                if path and ".worktrees" not in path and len(worktrees) > 1:
                    findings.append(
                        Finding(
                            id=f"git-worktree-{hash(path) % 10000:04d}",
                            title=f"Non-standard worktree: {path}",
                            description=f"Worktree at '{path}' is outside the standard .worktrees/ directory.",
                            severity="low",
                            category="git",
                            metadata={"path": path, "type": "worktree"},
                        )
                    )
        except Exception as e:
            logger.warning(f"Failed to check worktrees: {e}")

        return AnalyzerResult(
            analyzer_name=self.name,
            analyzer_description=self.description,
            findings=findings,
        )
