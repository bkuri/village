"""Jujutsu implementation of StackBackend."""

import subprocess
from pathlib import Path

from village.stack.backend import StackBackend


class JJStackBackend(StackBackend):
    """Jujutsu implementation of stack operations (stub)."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or Path.cwd()

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["jj"] + args,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=check,
        )

    def create_branch(self, name: str, base: str) -> str:
        self._run(["new", base, f"-m{name}"])
        return name

    def push_branch(self, name: str, remote: str = "origin") -> None:
        self._run(["git", "push", "--all", f"{remote}"])

    def create_pr(
        self,
        head: str,
        base: str,
        title: str,
        body: str,
        draft: bool = False,
    ) -> str:
        raise NotImplementedError("JJ PR creation not yet implemented")

    def rebase_onto(self, branch: str, new_base: str) -> None:
        self._run(["rebase", "-s", new_base, "-d", branch])

    def merge_pr(self, pr_ref: str) -> None:
        self._run(["squash", pr_ref])

    def get_current_branch(self) -> str:
        result = self._run(["status", "--no-pager"])
        for line in result.stdout.split("\n"):
            if line.startswith("The working copy is on branch: "):
                return line.replace("The working copy is on branch: ", "").strip()
        return "main"

    def list_commits(self, base: str, head: str) -> list[str]:
        result = self._run(["log", "-r", f"{base}..{head}", "--no-pager", "--format=%h"])
        return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]

    def get_default_trunk(self) -> str:
        return "main"
