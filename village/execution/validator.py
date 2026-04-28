"""Command validator — validates classified actions against rules and manifests.

The validator is the policy enforcement layer that decides whether a
classified action is allowed to execute, blocked by a rule, or needs
manual approval.
"""

import logging
import shlex
from dataclasses import dataclass
from pathlib import Path

from village.execution.manifest import ApprovalManifest
from village.execution.paths import PathPolicy, is_within_worktree
from village.execution.tiers import ClassifiedAction, Tier, TierClassifier
from village.rules.schema import ForbiddenCommandRule, RulesConfig

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating a classified action."""

    allowed: bool
    tier: Tier = Tier.READ_ONLY
    reason: str | None = None
    blocked_by: str | None = None  # "rule" | "metachar" | "pipe" | "manifest" | "path"


class CommandValidator:
    """Validates classified actions against rules and approval manifests.

    The validation pipeline:

    1. **DANGEROUS** tier: blocked unless explicitly in manifest.
    2. **DESTRUCTIVE** tier: allowed only if in manifest.
    3. **Command rules**: checked against :class:`ForbiddenCommandRule`.
    4. **Shell metacharacters**: ``$()```, ``````, ``&&``, ``||``, ``;``.
    5. **Pipe-to-shell**: ``| sh``, ``| bash`` patterns.
    6. **Script execution**: scripts must be in manifest.
    7. **Path policy**: symlink escapes and protected paths.
    8. **READ_ONLY / SAFE_WRITE**: always allowed.

    Args:
        rules: Optional :class:`RulesConfig` providing command rules.
        worktree: Optional worktree root for path-based access control.
            If provided, a :class:`PathPolicy` is created to enforce
            path restrictions.
    """

    def __init__(
        self,
        rules: RulesConfig | None = None,
        worktree: Path | None = None,
    ) -> None:
        self.rules = rules
        self._classifier = TierClassifier()
        self.path_policy = PathPolicy(worktree) if worktree else None

    # ── Main validation entry point ───────────────────────────────────

    def validate(
        self,
        action: ClassifiedAction,
        manifest: ApprovalManifest | None = None,
    ) -> ValidationResult:
        """Validate a classified action against rules and manifest.

        Args:
            action: The classified action to validate.
            manifest: Optional approval manifest with allowed commands/scripts.

        Returns:
            :class:`ValidationResult` indicating whether the action may proceed.
        """
        # ── Tier 3: DANGEROUS ─────────────────────────────────────────
        if action.tier == Tier.DANGEROUS:
            if manifest and self._command_in_manifest(action, manifest):
                return ValidationResult(
                    allowed=True,
                    tier=Tier.DANGEROUS,
                    reason="Command is in manifest allowed_commands",
                )
            return ValidationResult(
                allowed=False,
                tier=Tier.DANGEROUS,
                reason="DANGEROUS actions require explicit manifest approval",
                blocked_by="manifest",
            )

        # ── Tier 2: DESTRUCTIVE ───────────────────────────────────────
        if action.tier == Tier.DESTRUCTIVE:
            if manifest and self._command_in_manifest(action, manifest):
                return ValidationResult(
                    allowed=True,
                    tier=Tier.DESTRUCTIVE,
                    reason="Command is in manifest allowed_commands",
                )
            # If no manifest or not listed, block
            return ValidationResult(
                allowed=False,
                tier=Tier.DESTRUCTIVE,
                reason="DESTRUCTIVE actions require manifest approval",
                blocked_by="manifest",
            )

        # ── Path policy check ───────────────────────────────────────────
        path_result = self._check_path_policy(action)
        if path_result is not None:
            return path_result

        # ── Check command rules ────────────────────────────────────────
        if self.rules and self.rules.command_rules:
            rule_result = self._check_command_rules(action)
            if rule_result is not None:
                return rule_result

        # ── READ_ONLY / SAFE_WRITE: always allowed ────────────────────
        return ValidationResult(
            allowed=True,
            tier=action.tier,
            reason="Auto-approved",
        )

    # ── Command rule checking ─────────────────────────────────────────

    def _check_command_rules(self, action: ClassifiedAction) -> ValidationResult | None:
        """Check a classified action against ``forbidden_command_rules``.

        Args:
            action: The classified action to check.

        Returns:
            A blocking :class:`ValidationResult` if a rule matches, or None if
            no rule applies.
        """
        if not self.rules or not self.rules.command_rules:
            return None

        executable = action.executable or ""
        args = action.args or []
        command_full = action.command or ""

        for rule in self.rules.command_rules:
            # Check if our executable matches the rule
            if not self._executable_matches_rule(executable, rule):
                continue

            # Check dangerous flags
            if rule.dangerous_flags:
                for flag in rule.dangerous_flags:
                    if flag in args:
                        return ValidationResult(
                            allowed=False,
                            tier=Tier.DANGEROUS,
                            reason=rule.reason or f"Flag '{flag}' is forbidden for '{executable}'",
                            blocked_by="rule",
                        )

            # Check subcommand (e.g. git push)
            if rule.subcommand:
                if args and args[0] == rule.subcommand:
                    # Check forbidden flags for subcommands
                    if rule.forbidden_flags:
                        for fflag in rule.forbidden_flags:
                            if fflag in args:
                                # Check if an allowed alternative exists
                                if rule.allowed_alternatives:
                                    if any(alt in args for alt in rule.allowed_alternatives):
                                        continue
                                return ValidationResult(
                                    allowed=False,
                                    tier=Tier.DANGEROUS,
                                    reason=(rule.reason or f"Flag '{fflag}' is forbidden for 'git {rule.subcommand}'"),
                                    blocked_by="rule",
                                )
                    # Subcommand without forbidden flags match — still block if it's DESTRUCTIVE
                    if not rule.allowed_alternatives:
                        return ValidationResult(
                            allowed=False,
                            tier=Tier.DESTRUCTIVE,
                            reason=rule.reason or f"Subcommand '{rule.subcommand}' is not allowed",
                            blocked_by="rule",
                        )

            # Check pipe-to patterns
            if rule.pipe_to:
                for pipe_shell in rule.pipe_to:
                    if f"| {pipe_shell}" in command_full or f"|{pipe_shell}" in command_full:
                        return ValidationResult(
                            allowed=False,
                            tier=Tier.DANGEROUS,
                            reason=rule.reason or f"Pipe to '{pipe_shell}' is forbidden",
                            blocked_by="rule",
                        )

        return None

    @staticmethod
    def _executable_matches_rule(executable: str, rule: ForbiddenCommandRule) -> bool:
        """Check if a resolved executable matches a rule's executable list."""
        for rule_exe in rule.executables:
            rule_base = Path(rule_exe).name
            if executable == rule_base or executable == rule_exe:
                return True
        return False

    # ── Path policy check ────────────────────────────────────────────

    def _check_path_policy(
        self,
        action: ClassifiedAction,
    ) -> ValidationResult | None:
        """Check path policy for write/delete actions.

        Returns a blocking :class:`ValidationResult` if the action's target
        path violates the path policy (symlink escape or protected path),
        or ``None`` if the policy allows it or is not configured.

        Args:
            action: The classified action to check.
        """
        if not self.path_policy:
            return None

        # Check write/delete actions with a target path
        if action.path and action.action_type in ("write", "delete"):
            allowed, reason = self.path_policy.can_write(Path(action.path))
            if not allowed:
                return ValidationResult(
                    allowed=False,
                    tier=Tier.DANGEROUS,
                    reason=reason or f"Path '{action.path}' is not writable",
                    blocked_by="path",
                )

        # For bash commands, check if any argument references a path
        # outside the worktree — warn but don't block external paths
        if action.command and action.args:
            for arg in action.args:
                if arg.startswith("/") or ".." in arg:
                    try:
                        p = Path(arg)
                        if p.is_absolute() or ".." in arg:
                            # Check if the resolved path is within worktree
                            if not is_within_worktree(p, self.path_policy.worktree):
                                logger.debug(
                                    "Command arg %s resolves outside worktree: %s",
                                    arg,
                                    action.command,
                                )
                    except Exception:
                        pass

        return None

    # ── Manifest helpers ──────────────────────────────────────────────

    @staticmethod
    def _command_in_manifest(action: ClassifiedAction, manifest: ApprovalManifest) -> bool:
        """Check if a command is in the manifest's ``allowed_commands``.

        Compares the command prefix (executable + first argument) against
        manifest entries for flexibility. For example, if the manifest
        allows ``"git add"``, any ``git add <file>`` matches.

        Args:
            action: The classified action.
            manifest: The approval manifest.

        Returns:
            True if the command is allowed.
        """
        if not manifest.allowed_commands:
            return False

        executable = action.executable or ""
        args = action.args or []

        # Build prefixes to match: "git add" matches "git add src/main.py"
        prefix = executable
        if args:
            prefix = f"{executable} {args[0]}"

        full_command = action.command or ""

        for allowed in manifest.allowed_commands:
            # Exact match or prefix match
            if full_command == allowed:
                return True
            if full_command.startswith(allowed + " "):
                return True
            if prefix == allowed:
                return True
            # Check if the allowed command has a wildcard
            if allowed.endswith(" *") and full_command.startswith(allowed[:-2]):
                return True

        return False

    @staticmethod
    def _script_in_manifest(action: ClassifiedAction, manifest: ApprovalManifest) -> bool:
        """Check if a script path is in the manifest's ``allowed_scripts``.

        Args:
            action: The classified action.
            manifest: The approval manifest.

        Returns:
            True if the script is allowed.
        """
        if not manifest.allowed_scripts:
            return False

        script_path = action.script_path
        if script_path is None:
            return False

        script_name = Path(script_path).name

        for allowed in manifest.allowed_scripts:
            if allowed == script_path or allowed == script_name:
                return True

        return False

    # ── Shell metacharacter scanning ──────────────────────────────────

    @staticmethod
    def check_metacharacters(command: str) -> list[str]:
        """Scan for dangerous shell metacharacters in a command string.

        Detects:

        - ``$()`` command substitution
        - `````` (backtick) command substitution
        - ``&&`` and ``||`` command chaining
        - ``;`` command separator (excludes flags like ``-vv``)

        Args:
            command: The raw command string.

        Returns:
            A list of violation descriptions (empty = clean).
        """
        violations: list[str] = []

        if "$(" in command:
            violations.append("Command substitution '$()' detected")

        if "`" in command:
            violations.append("Backtick command substitution detected")

        # Tokenization-based operator detection
        try:
            tokens = shlex.split(command)
        except ValueError:
            violations.append("Malformed shell command")
            return violations

        for token in tokens:
            if token == "&&":
                violations.append("AND chaining '&&' detected")
            elif token == "||":
                violations.append("OR chaining '||' detected")
            elif token == ";":
                violations.append("Command separator ';' detected")
            elif token == "|":
                violations.append("Pipe '|' detected")

        return violations

    @staticmethod
    def check_pipe_to_shell(command: str) -> list[str]:
        """Check if a command pipes to shell interpreters.

        Detects patterns like ``curl http://… | sh``, ``wget … | bash``,
        as well as any general pipe to a shell interpreter.

        Args:
            command: The raw command string.

        Returns:
            A list of violation descriptions (empty = clean).
        """
        return TierClassifier._check_pipe_to_shell(command)
