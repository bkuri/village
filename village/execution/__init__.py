"""Execution engine — command validation, content scanning, and approval manifests.

The engine is the policy enforcement layer that sits between AI agents
and the filesystem.  It classifies actions into security tiers, validates
them against rules and manifests, and optionally executes them.
"""

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from village.execution.manifest import ApprovalManifest
from village.execution.scanner import ContentScanner, ScanViolation
from village.execution.tiers import ClassifiedAction, Tier, TierClassifier
from village.execution.validator import CommandValidator, ValidationResult
from village.rules.schema import RulesConfig

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a full execute pipeline."""

    status: str  # "ok" | "blocked" | "error"
    stdout: str = ""
    stderr: str = ""
    reason: str | None = None
    violations: list[ScanViolation] = field(default_factory=list)
    action: ClassifiedAction | None = None
    validation: ValidationResult | None = None


class ExecutionEngine:
    """Top-level policy enforcement engine.

    Combines the :class:`TierClassifier`, :class:`CommandValidator`, and
    :class:`ContentScanner` into a single pipeline:

    classify → validate → execute → return result

    Args:
        rules: Optional :class:`RulesConfig` to load rules from.
    """

    def __init__(self, rules: RulesConfig | None = None) -> None:
        self.rules = rules
        self.classifier = TierClassifier()
        self.validator = CommandValidator(rules=rules)
        self.scanner = ContentScanner(rules=rules)

    def execute(
        self,
        worktree: Path,
        action: dict[str, object],
        manifest: ApprovalManifest | None = None,
    ) -> ExecutionResult:
        """Run the full execute pipeline on a single action.

        The pipeline is:

        1. **Classify**: determine the action type (bash, write) and tier.
        2. **Validate**: check against rules and manifest.
        3. **Execute**: if allowed, run the action.
        4. **Scan**: if a file write, scan the result for content violations.

        Args:
            worktree: The working directory for execution.
            action: Action dictionary with keys:

                - ``type``: ``"bash"`` or ``"write"``
                - ``command``: shell command string (for bash actions)
                - ``path``: file path (for write actions)
                - ``content``: file content (for write actions)

            manifest: Optional :class:`ApprovalManifest` loading allowed
                commands and scripts.

        Returns:
            :class:`ExecutionResult` with status, output, and any violations.
        """
        raw_type = action.get("type", "bash")
        action_type = str(raw_type) if isinstance(raw_type, str) else "bash"

        # ── Step 1: Classify ──────────────────────────────────────────
        if action_type == "bash":
            raw_cmd = action.get("command", "")
            command = str(raw_cmd) if isinstance(raw_cmd, str) else ""
            classified = self.classifier.classify_bash(command)
        elif action_type == "write":
            raw_path = action.get("path", "")
            path = str(raw_path) if isinstance(raw_path, str) else ""
            raw_content = action.get("content")
            content = str(raw_content) if isinstance(raw_content, str) else None
            classified = self.classifier.classify_write(path, content)
        else:
            return ExecutionResult(
                status="error",
                reason=f"Unknown action type: {action_type}",
            )

        # ── Step 2: Validate ──────────────────────────────────────────
        validation = self.validator.validate(classified, manifest=manifest)

        if not validation.allowed:
            return ExecutionResult(
                status="blocked",
                reason=validation.reason or "Action blocked by policy",
                action=classified,
                validation=validation,
            )

        # ── Step 3: Execute ───────────────────────────────────────────
        try:
            if action_type == "bash":
                result = self._execute_bash(worktree, classified)
            elif action_type == "write":
                raw_path = action.get("path", "")
                path_val = str(raw_path) if isinstance(raw_path, str) else ""
                raw_content = action.get("content", "")
                content_val = str(raw_content) if isinstance(raw_content, str) else ""
                result = self._execute_write(worktree, path_val, content_val)
            else:
                return ExecutionResult(status="error", reason=f"Unknown action type: {action_type}")
        except subprocess.CalledProcessError as e:
            return ExecutionResult(
                status="error",
                stdout=e.stdout or "",
                stderr=e.stderr or "",
                reason=f"Command failed with exit code {e.returncode}",
                action=classified,
                validation=validation,
            )
        except OSError as e:
            return ExecutionResult(
                status="error",
                reason=f"Execution failed: {e}",
                action=classified,
                validation=validation,
            )

        # ── Step 4: Scan (for write actions) ──────────────────────────
        violations: list[ScanViolation] = []
        if action_type == "write":
            raw_path = action.get("path", "")
            path_val = str(raw_path) if isinstance(raw_path, str) else ""
            file_path = worktree / path_val
            violations = self.scanner.scan_file(file_path)

        return ExecutionResult(
            status="ok",
            stdout=result.get("stdout", ""),
            stderr=result.get("stderr", ""),
            action=classified,
            validation=validation,
            violations=violations,
        )

    # ── Internal execution helpers ────────────────────────────────────

    @staticmethod
    def _execute_bash(worktree: Path, action: ClassifiedAction) -> dict[str, str]:
        """Execute a bash command via ``subprocess.run``.

        Args:
            worktree: Working directory.
            action: The classified action.

        Returns:
            Dict with ``stdout`` and ``stderr`` keys.

        Raises:
            subprocess.CalledProcessError: If the command fails.
            OSError: If the working directory is invalid.
        """
        command = action.command or ""
        # Use list form (no shell=True) for security
        try:
            import shlex

            tokens = shlex.split(command)
        except ValueError:
            tokens = [command]

        result = subprocess.run(
            tokens,
            capture_output=True,
            text=True,
            cwd=worktree,
            timeout=300,
        )

        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                tokens,
                output=result.stdout,
                stderr=result.stderr,
            )

        return {"stdout": result.stdout, "stderr": result.stderr}

    @staticmethod
    def _execute_write(worktree: Path, path: str, content: str) -> dict[str, str]:
        """Write content to a file.

        Creates parent directories as needed.

        Args:
            worktree: Working directory.
            path: Relative or absolute path of the file to write.
            content: Content to write.

        Returns:
            Dict with ``stdout`` and ``stderr`` keys.

        Raises:
            OSError: If the file cannot be written.
        """
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = worktree / path

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        return {"stdout": f"Written {len(content)} bytes to {path}\n", "stderr": ""}


__all__ = [
    "ClassifiedAction",
    "CommandValidator",
    "ContentScanner",
    "ExecutionEngine",
    "ExecutionResult",
    "ScanViolation",
    "Tier",
    "TierClassifier",
    "ValidationResult",
]
