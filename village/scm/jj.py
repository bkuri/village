"""Jujutsu (jj) SCM backend implementation."""

import logging
import shutil
from pathlib import Path
from typing import Literal

from village.probes.tools import SubprocessError, run_command_output_cwd
from village.scm.protocol import WorkspaceInfo

logger = logging.getLogger(__name__)  # type: ignore


class JJSCM:
    """Jujutsu (jj) implementation of SCM protocol."""

    kind: Literal["git", "jj"] = "jj"

    def ensure_repo(self, repo_root: Path) -> None:
        """
        Ensure Jujutsu repository exists at path.

        Args:
            repo_root: Path to Jujutsu repository root

        Raises:
            RuntimeError: If not a valid Jujutsu repository or jj binary not found
        """
        try:
            cmd = ["jj", "root"]
            result = run_command_output_cwd(cmd, cwd=repo_root)
            detected_root = Path(result).resolve()

            if detected_root != repo_root.resolve():
                raise RuntimeError(f"Path is not a Jujutsu repository root: {repo_root}")

            logger.debug(f"Jujutsu repository verified: {repo_root}")
        except SubprocessError as e:
            logger.error(f"Jujutsu repository check failed: {e}")
            raise RuntimeError(f"Not a Jujutsu repository: {repo_root}") from e

    def check_clean(self, repo_root: Path) -> bool:
        """
        Check if Jujutsu repository has uncommitted changes.

        Args:
            repo_root: Path to Jujutsu repository root

        Returns:
            True if clean, False if dirty

        Raises:
            RuntimeError: If status check fails
        """
        try:
            cmd = ["jj", "status"]
            result = run_command_output_cwd(cmd, cwd=repo_root)

            is_dirty = bool(result.strip())

            if is_dirty:
                logger.debug(f"Jujutsu repository is dirty: {repo_root}")
            else:
                logger.debug(f"Jujutsu repository is clean: {repo_root}")

            return not is_dirty
        except SubprocessError as e:
            logger.error(f"Failed to check Jujutsu status: {e}")
            raise RuntimeError(f"Failed to check repository status: {e}") from e

    def ensure_workspace(
        self,
        repo_root: Path,
        workspace_path: Path,
        base_ref: str = "HEAD",
    ) -> None:
        """
        Ensure Jujutsu workspace exists at path.

        Args:
            repo_root: Path to Jujutsu repository root
            workspace_path: Path where workspace should be created
            base_ref: Reference to base workspace on (branch, commit, tag)

        Raises:
            RuntimeError: If workspace creation fails
        """
        try:
            cmd = [
                "jj",
                "workspace",
                "add",
                str(workspace_path),
                "-r",
                base_ref,
            ]

            result = run_command_output_cwd(cmd, cwd=repo_root)
            logger.debug(f"Jujutsu workspace created: {workspace_path}")
            logger.debug(f"Output: {result}")
        except SubprocessError as e:
            logger.error(f"Failed to create Jujutsu workspace {workspace_path}: {e}")
            raise RuntimeError(f"Failed to create workspace: {e}") from e

    def remove_workspace(self, workspace_path: Path) -> bool:
        """
        Remove Jujutsu workspace at path.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            True if workspace was removed, False if it didn't exist

        Raises:
            RuntimeError: If workspace removal fails
        """
        if not workspace_path.exists():
            logger.debug(f"Workspace does not exist: {workspace_path}")
            return False

        try:
            cmd = ["jj", "workspace", "forget", str(workspace_path)]
            result = run_command_output_cwd(cmd, cwd=workspace_path)
            logger.debug(f"Jujutsu workspace forgotten: {workspace_path}")
            logger.debug(f"Output: {result}")

            if workspace_path.exists():
                shutil.rmtree(workspace_path)
                logger.debug(f"Removed workspace directory: {workspace_path}")

            return True
        except SubprocessError as e:
            logger.error(f"Failed to remove Jujutsu workspace {workspace_path}: {e}")
            raise RuntimeError(f"Failed to remove workspace: {e}") from e

    def list_workspaces(self, repo_root: Path) -> list[WorkspaceInfo]:
        """
        List all Jujutsu workspaces.

        Args:
            repo_root: Path to Jujutsu repository root

        Returns:
            List of WorkspaceInfo objects

        Raises:
            RuntimeError: If workspace listing fails
        """
        try:
            cmd = ["jj", "workspace", "list"]
            result = run_command_output_cwd(cmd, cwd=repo_root)

            workspaces: list[WorkspaceInfo] = []

            for line in result.splitlines():
                line = line.strip()
                if not line:
                    continue

                workspace_path = Path(line)
                if not workspace_path.exists():
                    logger.debug(f"Workspace path doesn't exist, skipping: {workspace_path}")
                    continue

                workspaces.append(WorkspaceInfo(path=workspace_path, branch="", commit=""))

            logger.debug(f"Listed {len(workspaces)} Jujutsu workspaces")
            return workspaces

        except SubprocessError as e:
            logger.error(f"Failed to list Jujutsu workspaces: {e}")
            raise RuntimeError(f"Failed to list workspaces: {e}") from e
