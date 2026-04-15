"""Abstract stack backend interface."""

from abc import ABC, abstractmethod


class StackBackend(ABC):
    """Abstract interface for VCS-specific stack operations."""

    @abstractmethod
    def create_branch(self, name: str, base: str) -> str:
        """Create a branch at base. Return branch ref."""

    @abstractmethod
    def push_branch(self, name: str, remote: str = "origin") -> None:
        """Push branch to remote."""

    @abstractmethod
    def create_pr(
        self,
        head: str,
        base: str,
        title: str,
        body: str,
        draft: bool = False,
    ) -> str:
        """Create a pull request. Return PR URL."""

    @abstractmethod
    def rebase_onto(self, branch: str, new_base: str) -> None:
        """Rebase branch onto new base."""

    @abstractmethod
    def merge_pr(self, pr_ref: str) -> None:
        """Merge a pull request."""

    @abstractmethod
    def get_current_branch(self) -> str:
        """Return current branch name."""

    @abstractmethod
    def list_commits(self, base: str, head: str) -> list[str]:
        """List commit hashes between base and head."""

    @abstractmethod
    def get_default_trunk(self) -> str:
        """Return the default trunk branch name (main/master)."""
