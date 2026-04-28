"""Commit engine — sole committer for agent worktrees.

The CommitEngine is the only way to commit changes to a worktree. Agents
cannot run ``git commit`` directly (it is classified as Tier 2/3 in the
classifier). Instead, the engine:

- Validates every changed file at commit-time (not write-time)
- Filters to ``allowed_paths`` only
- Rejects commits touching ``specs/``, ``.village/``, or non-allowed paths
- Uses low-level git plumbing (``read-tree``, ``hash-object``,
  ``update-index``, ``write-tree``, ``commit-tree``) for tamper-proof
  snapshots — reads file content from disk at commit-moment and hashes it,
  preventing race conditions with ``git add``.
- Commits with the role's git identity (``GIT_AUTHOR_*``, ``GIT_COMMITTER_*``)
"""

from __future__ import annotations

import fnmatch
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from village.execution.scanner import ContentScanner, ScanViolation
from village.rules.schema import RulesConfig

logger = logging.getLogger(__name__)

# Paths that are always rejected for commit — agents must never touch these
# Both the bare name (for directory-level porcelain entries) and /** patterns
# (for individual files inside) are included.
_PROTECTED_PATH_PATTERNS: list[str] = [
    "specs",
    "specs/**",
    ".village",
    ".village/**",
    ".git",
    ".git/**",
]

# Porcelain status codes that indicate a changed (modified / added / untracked) file
_CHANGED_STATUS_PREFIXES: set[str] = {"M", "A", "?"}


@dataclass
class CommitResult:
    """Result of a commit attempt.

    Attributes:
        success: Whether the commit was created successfully.
        commit_hash: The SHA-1 hash of the created commit, or None on failure.
        message: Human-readable result or error message.
        rejected_files: Files that were excluded because they fell outside
            ``allowed_paths`` or matched protected patterns.
        violations: Content-scanner violations that caused the commit to be
            rejected.
    """

    success: bool
    commit_hash: str | None = None
    message: str = ""
    rejected_files: list[str] = field(default_factory=list)
    violations: list[dict[str, str | int | None]] = field(default_factory=list)


class CommitEngine:
    """Sole committer — agent cannot run ``git commit`` directly.

    Every commit goes through this engine, which validates content, enforces
    path restrictions, and creates tamper-proof snapshots using low-level git
    plumbing (``read-tree``, ``hash-object``, ``update-index``,
    ``write-tree``, ``commit-tree``).

    Args:
        worktree: The worktree (repository root) to operate on.
        rules: Optional :class:`RulesConfig` for content scanning.
        scanner: Optional pre-configured :class:`ContentScanner`. If omitted,
            one is created from *rules*.
    """

    def __init__(
        self,
        worktree: Path,
        rules: RulesConfig | None = None,
        scanner: ContentScanner | None = None,
    ) -> None:
        self.worktree = worktree.resolve()
        self.scanner = scanner or ContentScanner(rules)

    # ── Public API ─────────────────────────────────────────────────────

    def commit(
        self,
        message: str,
        allowed_paths: list[str] | None = None,
        git_user: str | None = None,
        git_email: str | None = None,
    ) -> CommitResult:
        """Validate and commit changes in the worktree.

        The commit pipeline:

        1. Discover changed (unstaged + untracked) files.
        2. Filter to ``allowed_paths`` — reject anything outside.
        3. Scan each changed file for content violations.
        4. Load the parent tree into the index (``git read-tree``).
        5. For each validated file: hash content (``git hash-object``) and
           update the index entry (``git update-index --cacheinfo``).
        6. Write the tree from the updated index (``git write-tree``).
        7. Create a commit with the role's identity (``git commit-tree``).
        8. Move HEAD (``git update-ref``) and sync index.

        If **any** file fails validation the entire commit is rejected.

        Args:
            message: Commit message.
            allowed_paths: Glob patterns for paths the agent is allowed to
                commit (e.g. ``["src/**", "tests/**"]``). If None, all
                non-protected paths are allowed.
            git_user: Author/committer name (``GIT_AUTHOR_NAME`` /
                ``GIT_COMMITTER_NAME``).
            git_email: Author/committer email (``GIT_AUTHOR_EMAIL`` /
                ``GIT_COMMITTER_EMAIL``).

        Returns:
            A :class:`CommitResult` describing the outcome.
        """
        # Step 1: Discover changed files
        changed = self.get_changed_files()
        if not changed:
            return CommitResult(
                success=False,
                message="No changes to commit",
            )

        # Step 2: Filter to allowed paths
        allowed, rejected = self.filter_allowed(changed, allowed_paths)
        if not allowed:
            return CommitResult(
                success=False,
                message="No allowed files to commit",
                rejected_files=[str(p) for p in rejected],
            )

        # Step 3: Content validation
        violations = self.validate_files(allowed)
        if violations:
            return CommitResult(
                success=False,
                message=f"Commit rejected: {len(violations)} content violation(s)",
                rejected_files=[str(p) for p in rejected],
                violations=[
                    {
                        "rule": v.rule,
                        "message": v.message,
                        "file": str(v.file_path) if v.file_path else None,
                        "line": v.line,
                        "pattern": v.pattern,
                    }
                    for v in violations
                ],
            )

        # Step 4-7: Create the commit
        parent_hash = self._get_head_hash()
        commit_hash = self.snapshot_commit(
            allowed_files=allowed,
            message=message,
            parent_hash=parent_hash,
            git_user=git_user,
            git_email=git_email,
        )

        if commit_hash is None:
            return CommitResult(
                success=False,
                message="Failed to create commit",
                rejected_files=[str(p) for p in rejected],
            )

        return CommitResult(
            success=True,
            commit_hash=commit_hash,
            message=f"Created commit {commit_hash}",
            rejected_files=[str(p) for p in rejected],
        )

    # ── File discovery ─────────────────────────────────────────────────

    def get_changed_files(self) -> list[Path]:
        """Get list of changed (unstaged + untracked) files in the worktree.

        Uses ``git status --porcelain`` to discover files that are modified,
        added, or untracked relative to HEAD.

        Returns:
            List of paths relative to the worktree root.
        """
        if not self.worktree.is_dir():
            logger.debug("Worktree %s does not exist", self.worktree)
            return []

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.worktree,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning("Failed to get changed files: %s", e.stderr.strip())
            return []
        except FileNotFoundError:
            logger.warning("git command not found")
            return []

        changed: list[Path] = []
        for line in result.stdout.splitlines():
            line = line.rstrip("\n")
            if not line:
                continue

            # Porcelain format: XY <path>
            #   XY = two-character status code
            #   For untracked: "?? <path>"
            status = line[:2].strip()
            path_str = line[2:].strip()

            if not path_str:
                continue

            # Skip if status does not indicate a change we care about
            if status not in _CHANGED_STATUS_PREFIXES and status[0] not in _CHANGED_STATUS_PREFIXES:
                # status like " M" (staging differs from worktree but not
                # staged) — the first char is the staging area status, second
                # is the worktree status. Check the worktree column.
                if len(status) < 2 or status[1] not in _CHANGED_STATUS_PREFIXES:
                    continue

            # Handle quoted filenames (git may quote special characters)
            if path_str.startswith('"') and path_str.endswith('"'):
                try:
                    path_str = bytes(path_str[1:-1], "utf-8").decode("unicode_escape")
                except (ValueError, UnicodeDecodeError):
                    pass

            changed.append(Path(path_str))

        return changed

    # ── Path filtering ─────────────────────────────────────────────────

    def filter_allowed(
        self,
        files: list[Path],
        allowed_paths: list[str] | None,
    ) -> tuple[list[Path], list[Path]]:
        """Split *files* into allowed and rejected lists.

        A file is allowed if:

        - It does **not** match any protected pattern (``specs/**``,
          ``.village/**``, ``.git/**``).
        - ``allowed_paths`` is None (all non-protected paths are allowed), **or**
          it matches at least one glob pattern in ``allowed_paths``.

        Args:
            files: List of file paths (relative to the worktree root).
            allowed_paths: Glob patterns for permissible paths, or None
                to allow all non-protected paths.

        Returns:
            Tuple of ``(allowed, rejected)``.
        """
        allowed: list[Path] = []
        rejected: list[Path] = []

        for path in files:
            path_str = path.as_posix()

            # Always reject protected paths
            if self._matches_any(path_str, _PROTECTED_PATH_PATTERNS):
                rejected.append(path)
                continue

            # If no allowed_paths specified, everything non-protected is allowed
            if allowed_paths is None:
                allowed.append(path)
                continue

            # Check against explicit allowed patterns
            if self._matches_any(path_str, allowed_paths):
                allowed.append(path)
            else:
                rejected.append(path)

        return allowed, rejected

    # ── Content validation ─────────────────────────────────────────────

    def validate_files(self, files: list[Path]) -> list[ScanViolation]:
        """Scan each file against content rules.

        Uses :meth:`ContentScanner.scan_file` to check each file for
        forbidden patterns, content violations, etc.

        Args:
            files: List of file paths (relative to the worktree root) to scan.

        Returns:
            List of :class:`ScanViolation` objects. Empty if all files pass.
        """
        all_violations: list[ScanViolation] = []

        for path in files:
            resolved = self.worktree / path
            if not resolved.is_file():
                continue

            violations = self.scanner.scan_file(resolved)
            all_violations.extend(violations)

        return all_violations

    # ── Tamper-proof commit ────────────────────────────────────────────

    def snapshot_commit(
        self,
        allowed_files: list[Path],
        message: str,
        parent_hash: str | None = None,
        git_user: str | None = None,
        git_email: str | None = None,
    ) -> str | None:
        """Create a commit with ONLY the validated files.

        Uses low-level git plumbing to prevent race conditions,
        while preserving files from the parent commit tree:

        1. Read the parent tree into the index (``git read-tree HEAD``)
        2. For each changed file: ``git hash-object -w`` then
           ``git update-index --add --cacheinfo`` to update the index entry
        3. ``git write-tree`` from the updated index
        4. ``git commit-tree`` to create the commit
        5. ``git update-ref`` to move HEAD
        6. ``git reset --mixed HEAD`` to sync the index

        Args:
            allowed_files: List of file paths (relative to worktree root)
                to include in the commit.
            message: Commit message.
            parent_hash: Hash of the parent commit. If None, creates an
                orphan commit (no parent).
            git_user: Override for ``GIT_AUTHOR_NAME`` /
                ``GIT_COMMITTER_NAME``.
            git_email: Override for ``GIT_AUTHOR_EMAIL`` /
                ``GIT_COMMITTER_EMAIL``.

        Returns:
            The commit SHA-1 hash, or None on failure.
        """
        if not allowed_files:
            logger.debug("snapshot_commit called with empty file list")
            return None

        # Step 1: Load the parent tree into the index so unchanged files
        # are preserved in the new commit.
        if parent_hash:
            try:
                subprocess.run(
                    ["git", "read-tree", parent_hash],
                    capture_output=True,
                    cwd=self.worktree,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                logger.warning("git read-tree failed: %s", e.stderr.decode(errors="replace").strip())
                return None
        else:
            # No parent — start with a clean index (orphan commit)
            try:
                subprocess.run(
                    ["git", "read-tree", "--empty"],
                    capture_output=True,
                    cwd=self.worktree,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                logger.warning("git read-tree --empty failed: %s", e.stderr.decode(errors="replace").strip())
                return None

        # Step 2: For each allowed file, hash its current content on disk
        # and update the index entry.
        for path in allowed_files:
            resolved = self.worktree / path
            if not resolved.is_file():
                logger.debug("File %s disappeared before commit, skipping", path)
                continue

            try:
                content = resolved.read_bytes()
            except OSError as e:
                logger.warning("Failed to read %s for commit: %s", path, e)
                continue

            # Hash the exact content read at this moment
            try:
                hash_result = subprocess.run(
                    ["git", "hash-object", "-w", "--stdin"],
                    input=content,
                    capture_output=True,
                    cwd=self.worktree,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                logger.warning("git hash-object failed for %s: %s", path, e.stderr.decode(errors="replace").strip())
                continue

            blob_hash = hash_result.stdout.strip().decode()
            path_str = path.as_posix()

            # Update the index with the new blob
            try:
                subprocess.run(
                    ["git", "update-index", "--add", "--cacheinfo", f"100644,{blob_hash},{path_str}"],
                    capture_output=True,
                    cwd=self.worktree,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                logger.warning("git update-index failed for %s: %s", path, e.stderr.decode(errors="replace").strip())
                continue

        # Step 3: Write the tree from the updated index
        try:
            wt_result = subprocess.run(
                ["git", "write-tree"],
                capture_output=True,
                text=True,
                cwd=self.worktree,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning("git write-tree failed: %s", e.stderr.strip())
            return None

        tree_hash = wt_result.stdout.strip()

        # Step 4: Create the commit with the role's identity
        env = os.environ.copy()
        if git_user:
            env["GIT_AUTHOR_NAME"] = git_user
            env["GIT_COMMITTER_NAME"] = git_user
        if git_email:
            env["GIT_AUTHOR_EMAIL"] = git_email
            env["GIT_COMMITTER_EMAIL"] = git_email

        parent_args: list[str] = []
        if parent_hash:
            parent_args = ["-p", parent_hash]

        try:
            ct_result = subprocess.run(
                ["git", "commit-tree", tree_hash, *parent_args, "-m", message],
                capture_output=True,
                text=True,
                cwd=self.worktree,
                env=env,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning("git commit-tree failed: %s", e.stderr.strip())
            return None

        commit_hash = ct_result.stdout.strip()

        # Step 5: Move HEAD to the new commit
        try:
            subprocess.run(
                ["git", "update-ref", "HEAD", commit_hash],
                capture_output=True,
                cwd=self.worktree,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning("git update-ref failed: %s", e.stderr.decode(errors="replace").strip())
            # The commit object was created but HEAD wasn't updated — still
            # return the hash so callers can recover
            return commit_hash

        # Step 6: The index already matches the new tree (we updated it),
        # but run a reset to ensure it stays in sync.
        try:
            subprocess.run(
                ["git", "reset", "--mixed", "HEAD"],
                capture_output=True,
                cwd=self.worktree,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning("git reset --mixed HEAD failed: %s", e.stderr.decode(errors="replace").strip())
            # Index sync is best-effort; the commit itself was successful

        logger.info("Created commit %s with %d file(s)", commit_hash, len(allowed_files))
        return commit_hash

    # ── Internal helpers ───────────────────────────────────────────────

    def _get_head_hash(self) -> str | None:
        """Return the SHA-1 hash of HEAD, or None if no commits exist."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.worktree,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    @staticmethod
    def _matches_any(path: str, patterns: list[str]) -> bool:
        """Check if *path* matches any of the given glob patterns."""
        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False
