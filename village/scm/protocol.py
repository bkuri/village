"""SCM abstraction layer for version control operations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


@dataclass
class WorkspaceInfo:
    """SCM-agnostic workspace metadata."""

    path: Path
    branch: str
    commit: str


class SCM(Protocol):
    """Version control system protocol for Village operations."""

    kind: Literal["git", "jj"]

    def ensure_repo(self, repo_root: Path) -> None:
        """
        Ensure repository exists at path.

        Args:
            repo_root: Path to repository root

        Raises:
            RuntimeError: If not a valid repository
        """

    def check_clean(self, repo_root: Path) -> bool:
        """
        Check if repository has uncommitted changes.

        Args:
            repo_root: Path to repository root

        Returns:
            True if clean, False if dirty
        """

    def ensure_workspace(
        self,
        repo_root: Path,
        workspace_path: Path,
        base_ref: str = "HEAD",
    ) -> None:
        """
        Ensure workspace exists at path.

        Args:
            repo_root: Path to repository root
            workspace_path: Path where workspace should be created
            base_ref: Reference to base workspace on (branch, commit, tag)

        Raises:
            RuntimeError: If workspace creation fails
        """

    def remove_workspace(self, workspace_path: Path) -> bool:
        """
        Remove workspace at path.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            True if workspace was removed, False if it didn't exist
        """

    def list_workspaces(self, repo_root: Path) -> list[WorkspaceInfo]:
        """
        List all workspaces managed by this SCM.

        Args:
            repo_root: Path to repository root

        Returns:
            List of workspace information
        """
