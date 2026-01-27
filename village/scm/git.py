"""Git SCM backend implementation."""

import logging
from pathlib import Path
from typing import Literal

from village.probes.tools import SubprocessError, run_command_output_cwd
from village.scm.protocol import WorkspaceInfo

logger = logging.getLogger(__name__)


class GitSCM:
    """Git implementation of SCM protocol."""

    kind: Literal["git", "jj"] = "git"

    def ensure_repo(self, repo_root: Path) -> None:
        """
        Ensure Git repository exists at path.

        Args:
            repo_root: Path to Git repository root

        Raises:
            RuntimeError: If not a valid Git repository
        """
        try:
            cmd = ["git", "rev-parse", "--show-toplevel"]
            result = run_command_output_cwd(cmd, cwd=repo_root)
            detected_root = Path(result).resolve()

            if detected_root != repo_root.resolve():
                raise RuntimeError(f"Path is not a Git repository root: {repo_root}")

            logger.debug(f"Git repository verified: {repo_root}")
        except SubprocessError as e:
            logger.error(f"Git repository check failed: {e}")
            raise RuntimeError(f"Not a Git repository: {repo_root}") from e

    def check_clean(self, repo_root: Path) -> bool:
        """
        Check if Git repository has uncommitted changes.

        Args:
            repo_root: Path to Git repository root

        Returns:
            True if clean, False if dirty
        """
        try:
            cmd = ["git", "status", "--porcelain"]
            result = run_command_output_cwd(cmd, cwd=repo_root)

            is_dirty = bool(result.strip())

            if is_dirty:
                logger.debug(f"Git repository is dirty: {repo_root}")
            else:
                logger.debug(f"Git repository is clean: {repo_root}")

            return not is_dirty
        except SubprocessError as e:
            logger.error(f"Failed to check Git status: {e}")
            raise RuntimeError(f"Failed to check repository status: {e}") from e

    def ensure_workspace(
        self,
        repo_root: Path,
        workspace_path: Path,
        base_ref: str = "HEAD",
    ) -> None:
        """
        Ensure Git worktree exists at path.

        Args:
            repo_root: Path to Git repository root
            workspace_path: Path where worktree should be created
            base_ref: Reference to base worktree on (branch, commit, tag)

        Raises:
            RuntimeError: If worktree creation fails
        """
        try:
            cmd = [
                "git",
                "worktree",
                "add",
                str(workspace_path),
                "-b",
                base_ref,
            ]

            result = run_command_output_cwd(cmd, cwd=repo_root)
            logger.debug(f"Git worktree created: {workspace_path}")
            logger.debug(f"Output: {result}")
        except SubprocessError as e:
            logger.error(f"Failed to create Git worktree {workspace_path}: {e}")
            raise RuntimeError(f"Failed to create worktree: {e}") from e

    def remove_workspace(self, workspace_path: Path) -> bool:
        """
        Remove Git worktree at path.

        Args:
            workspace_path: Path to worktree directory

        Returns:
            True if worktree was removed, False if it didn't exist
        """
        if not workspace_path.exists():
            logger.debug(f"Worktree does not exist: {workspace_path}")
            return False

        try:
            cmd = ["git", "worktree", "remove", str(workspace_path)]
            result = run_command_output_cwd(cmd, cwd=workspace_path)
            logger.debug(f"Git worktree removed: {workspace_path}")
            logger.debug(f"Output: {result}")
            return True
        except SubprocessError as e:
            logger.error(f"Failed to remove Git worktree {workspace_path}: {e}")
            raise RuntimeError(f"Failed to remove worktree: {e}") from e

    def list_workspaces(self, repo_root: Path) -> list[WorkspaceInfo]:
        """
        List all Git worktrees.

        Args:
            repo_root: Path to Git repository root

        Returns:
            List of WorkspaceInfo objects
        """
        try:
            cmd = ["git", "worktree", "list", "--porcelain"]
            result = run_command_output_cwd(cmd, cwd=repo_root)

            workspaces: list[WorkspaceInfo] = []
            current_info: dict[str, str] = {}

            for line in result.splitlines():
                line = line.strip()
                if not line:
                    continue

                if line.startswith("worktree "):
                    if current_info:
                        info = self._parse_workspace_entry(current_info)
                        if info:
                            workspaces.append(info)

                    current_info = {"path": line[len("worktree ") :].strip()}

                elif line.startswith("HEAD "):
                    current_info["commit"] = line[len("HEAD ") :].strip()
                elif line.startswith("branch "):
                    current_info["branch"] = line[len("branch ") :].strip()
                elif line.startswith("detached"):
                    current_info["branch"] = "(detached)"

            if current_info:
                info = self._parse_workspace_entry(current_info)
                if info:
                    workspaces.append(info)

            logger.debug(f"Listed {len(workspaces)} Git worktrees")
            return workspaces

        except SubprocessError as e:
            logger.error(f"Failed to list Git worktrees: {e}")
            raise RuntimeError(f"Failed to list worktrees: {e}") from e

    def _parse_workspace_entry(self, entry: dict[str, str]) -> WorkspaceInfo | None:
        """Parse a single worktree entry from git worktree list output."""
        path = Path(entry.get("path", ""))
        branch = entry.get("branch", "")
        commit = entry.get("commit", "")

        if not path.exists():
            logger.debug(f"Worktree path doesn't exist, skipping: {path}")
            return None

        return WorkspaceInfo(path=path, branch=branch, commit=commit)

    def reset_workspace(self, workspace_path: Path) -> None:
        """
        Reset Git worktree to clean state (discard all modifications).

        Args:
            workspace_path: Path to worktree to reset

        Raises:
            RuntimeError: If workspace reset fails
        """
        if not workspace_path.exists():
            raise RuntimeError(f"Worktree does not exist: {workspace_path}")

        try:
            cmd = ["git", "reset", "--hard", "HEAD"]
            result = run_command_output_cwd(cmd, cwd=workspace_path)
            logger.debug(f"Git worktree reset: {workspace_path}")
            logger.debug(f"Output: {result}")

            cmd = ["git", "clean", "-fdx"]
            result = run_command_output_cwd(cmd, cwd=workspace_path)
            logger.debug(f"Git worktree cleaned: {workspace_path}")
            logger.debug(f"Output: {result}")

        except SubprocessError as e:
            logger.error(f"Failed to reset Git worktree {workspace_path}: {e}")
            raise RuntimeError(f"Failed to reset worktree: {e}") from e
