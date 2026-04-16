"""Git implementation of StackBackend."""

import subprocess
from pathlib import Path

from village.probes.tools import run_command
from village.stack.backend import StackBackend


class GitStackBackend(StackBackend):
    """Git implementation of stack operations."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or Path.cwd()

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        return run_command(
            ["git"] + args,
            cwd=self.repo_root,
            capture=True,
            check=check,
        )

    def create_branch(self, name: str, base: str) -> str:
        self._run(["checkout", "-b", name, base])
        return name

    def push_branch(self, name: str, remote: str = "origin") -> None:
        self._run(["push", "-u", remote, name])

    def create_pr(
        self,
        head: str,
        base: str,
        title: str,
        body: str,
        draft: bool = False,
    ) -> str:
        gh_args = ["pr", "create", "--head", head, "--base", base, "--title", title]
        if draft:
            gh_args.append("--draft")
        body_file = self.repo_root / ".pr_body.txt"
        body_file.write_text(body, encoding="utf-8")
        gh_args.extend(["--body-file", str(body_file)])
        result = run_command(
            ["gh"] + gh_args,
            cwd=self.repo_root,
            capture=True,
            check=False,
        )
        body_file.unlink(missing_ok=True)
        if result.returncode != 0:
            raise RuntimeError(f"gh pr create failed: {result.stderr}")
        return result.stdout.strip()

    def rebase_onto(self, branch: str, new_base: str) -> None:
        current = self.get_current_branch()
        if current == branch:
            self._run(["rebase", new_base])
        else:
            self._run(["checkout", branch])
            self._run(["rebase", new_base])
            self._run(["checkout", current])

    def merge_pr(self, pr_ref: str) -> None:
        result = run_command(
            ["gh", "pr", "merge", pr_ref, "--squash", "--delete-branch"],
            cwd=self.repo_root,
            capture=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"gh pr merge failed: {result.stderr}")

    def get_current_branch(self) -> str:
        result = self._run(["branch", "--show-current"])
        return result.stdout.strip()

    def list_commits(self, base: str, head: str) -> list[str]:
        result = self._run(
            ["log", f"{base}..{head}", "--format=%H", "--reverse"],
            check=False,
        )
        return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]

    def get_default_trunk(self) -> str:
        for trunk in ["main", "master"]:
            result = self._run(["rev-parse", "--verify", trunk], check=False)
            if result.returncode == 0:
                return trunk
        return "main"
