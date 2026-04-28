"""Tier classifier — classifies actions into security tiers.

The classifier inspects bash commands and file writes, resolving executables
to canonical names and checking them against known tier lists.
"""

import logging
import shlex
import subprocess
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

logger = logging.getLogger(__name__)


class Tier(IntEnum):
    """Security tier for an action.

    Higher values represent greater risk and require more approval.
    """

    READ_ONLY = 0  # Auto-approve: cat, ls, grep, git log, git diff
    SAFE_WRITE = 1  # Auto-approve with monitoring: mkdir, pytest, git add, ruff format
    DESTRUCTIVE = 2  # Validate against manifest: rm (single file), git reset --soft, pip install
    DANGEROUS = 3  # Block unless in manifest: rm -rf, git push --force, chmod 777, sudo


@dataclass
class ClassifiedAction:
    """A classified action with tier and resolved metadata."""

    action_type: str  # "bash" | "write" | "delete"
    command: str | None = None
    executable: str | None = None
    args: list[str] | None = field(default_factory=list)
    tier: Tier = Tier.READ_ONLY
    script_path: str | None = None  # if executing a script file


# ── Tier classification tables ────────────────────────────────────────
# Canonical executable names mapped to their tier.

_READ_ONLY_COMMANDS: set[str] = {
    "cat",
    "ls",
    "less",
    "more",
    "head",
    "tail",
    "grep",
    "egrep",
    "fgrep",
    "rg",
    "find",
    "wc",
    "sort",
    "uniq",
    "cut",
    "echo",
    "printf",
    "which",
    "type",
    "pwd",
    "date",
    "env",
    "printenv",
    "file",
    "stat",
    "du",
    "df",
    "realpath",
    "readlink",
    "basename",
    "dirname",
}

_SAFE_WRITE_COMMANDS: set[str] = {
    "mkdir",
    "touch",
    "cp",
    "mv",
    "pytest",
    "ruff",
    "mypy",
    "pyright",
    "black",
    "isort",
    "flake8",
    "uv",
    "pip",
    "npm",
    "yarn",
}

_DESTRUCTIVE_COMMANDS: set[str] = {
    "rm",
    "git",
    "pip",
    "pip3",
    "npm",
    "yarn",
    "cargo",
    "go",
    "apt",
    "apt-get",
    "brew",
    "docker",
    "kill",
    "pkill",
}

_DANGEROUS_COMMANDS: set[str] = {
    "sudo",
    "doas",
    "chmod",
    "chown",
    "chattr",
    "dd",
    "mkfs",
    "fdisk",
    "parted",
    "shutdown",
    "reboot",
    "poweroff",
    "init",
    "systemctl",
    "journalctl",
    "passwd",
    "useradd",
    "usermod",
    "userdel",
    "groupadd",
    "groupmod",
    "groupdel",
    "iptables",
    "ufw",
    "firewall-cmd",
}

# Commands that are safe when subcommands are restricted — we check the subcommand.
_GIT_READ_SUBCOMMANDS: set[str] = {"log", "diff", "status", "show", "branch", "ls-files", "config"}
_GIT_WRITE_SUBCOMMANDS: set[str] = {"add", "commit", "checkout", "stash", "merge", "rebase", "cherry-pick"}
_GIT_DESTRUCTIVE_SUBCOMMANDS: set[str] = {"reset", "push", "fetch", "pull", "clean"}
_GIT_DANGEROUS_FLAGS: set[str] = {"--force", "-f", "--hard"}


def _resolve_executable(name: str) -> str:
    """Resolve a command name to its canonical executable basename.

    Strips directory prefixes (``/bin/rm`` → ``rm``) and resolves
    through ``$PATH`` using ``which`` when possible.

    Args:
        name: The command name or path as typed.

    Returns:
        The canonical basename.
    """
    base = Path(name).name

    # If it already looks like a plain name (no path separators), use it directly
    if "/" not in name:
        return base

    # Try to resolve through PATH
    try:
        result = subprocess.run(
            ["which", name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            resolved = result.stdout.strip()
            if resolved:
                return Path(resolved).name
    except (OSError, subprocess.TimeoutExpired):
        pass

    return base


def _classify_bash_git(args: list[str], executable: str) -> ClassifiedAction:
    """Classify a ``git`` subcommand into the appropriate tier.

    Args:
        args: Tokenized command arguments (everything after ``git``).
        executable: The resolved executable name (always ``git`` here).

    Returns:
        A :class:`ClassifiedAction` with the determined tier.
    """
    command_str = "git " + " ".join(args)
    subcommand = args[0] if args else ""
    flags = set(args[1:]) if len(args) > 1 else set()

    if subcommand in _GIT_READ_SUBCOMMANDS:
        tier = Tier.READ_ONLY
    elif subcommand in _GIT_WRITE_SUBCOMMANDS:
        tier = Tier.SAFE_WRITE
    elif subcommand in _GIT_DESTRUCTIVE_SUBCOMMANDS:
        # Check for dangerous flags like --force, --hard
        if flags & _GIT_DANGEROUS_FLAGS:
            tier = Tier.DANGEROUS
        else:
            tier = Tier.DESTRUCTIVE
    else:
        # Unknown git subcommand — treat as destructive
        tier = Tier.DESTRUCTIVE

    return ClassifiedAction(
        action_type="bash",
        command=command_str,
        executable=executable,
        args=args,
        tier=tier,
    )


def _classify_bash_docker(args: list[str], executable: str) -> ClassifiedAction:
    """Classify a ``docker`` subcommand into the appropriate tier.

    Args:
        args: Tokenized arguments (everything after ``docker``).
        executable: Resolved executable name (always ``docker`` here).

    Returns:
        A :class:`ClassifiedAction` with the determined tier.
    """
    command_str = executable + " " + " ".join(args)
    subcommand = args[0] if args else ""

    if subcommand in ("ps", "images", "inspect", "logs", "stats", "version"):
        tier = Tier.READ_ONLY
    elif subcommand in ("build", "pull", "push", "tag", "cp"):
        tier = Tier.DESTRUCTIVE
    elif subcommand in ("run", "exec", "start", "stop", "restart", "kill", "rm", "rmi", "prune"):
        tier = Tier.DANGEROUS
    else:
        tier = Tier.DESTRUCTIVE

    return ClassifiedAction(
        action_type="bash",
        command=command_str,
        executable=executable,
        args=args,
        tier=tier,
    )


def _has_shell_metachars(command: str) -> bool:
    """Check if a command contains shell metacharacters that imply chaining.

    Detects ``$()``, backticks, ``&&``, ``||``, ``;``, and ``|``.

    Args:
        command: The raw command string.

    Returns:
        True if dangerous metacharacters are found.
    """
    # Check for subshells
    if "$(" in command:
        return True
    if "`" in command:
        return True

    # Check for special operator tokens after parsing
    # (shlex does not treat ;, &&, ||, | as special, so we also check
    # the raw string for these)
    for op in ("&&", "||", ";", "|"):
        if op in command and op not in ("-vv", "-v", "-vvv"):  # avoid flag false-positives
            return True

    return False


class TierClassifier:
    """Classifies actions into security tiers.

    Call :meth:`classify_bash` or :meth:`classify_write` to get a
    :class:`ClassifiedAction` with the determined tier and metadata.
    """

    # ── Bash classification ───────────────────────────────────────────

    def classify_bash(self, command: str) -> ClassifiedAction:
        """Classify a bash command into a security tier.

        The classification pipeline:

        1. Tokenize with :func:`shlex.split`.
        2. Resolve the executable to its canonical basename.
        3. Check executable against known tier tables.
        4. Handle special subcommands (``git``, ``docker``).
        5. Elevate tier for shell metacharacters.
        6. Elevate tier for pipe-to-shell patterns.

        Args:
            command: The raw command string (e.g. ``rm -rf /tmp/foo``).

        Returns:
            A :class:`ClassifiedAction` with the determined tier.
        """
        try:
            tokens = shlex.split(command)
        except ValueError as e:
            logger.debug("Failed to parse command %r: %s", command, e)
            return ClassifiedAction(
                action_type="bash",
                command=command,
                tier=Tier.DANGEROUS,
            )

        if not tokens:
            return ClassifiedAction(action_type="bash", command="", tier=Tier.READ_ONLY)

        raw_exe = tokens[0]
        args = tokens[1:]

        # Resolve executable to canonical name
        executable = self.resolve_executable(raw_exe)

        # Default classification
        action = self._classify_plain(raw_exe, executable, args)

        # Special subcommand handling
        if executable == "git" and args:
            action = _classify_bash_git(args, executable)
        elif executable == "docker" and args:
            action = _classify_bash_docker(args, executable)

        # Elevate tier for shell metacharacters
        if action.tier < Tier.DESTRUCTIVE and _has_shell_metachars(command):
            action.tier = Tier.DESTRUCTIVE

        # Elevate tier for pipe-to-shell patterns
        if action.tier < Tier.DANGEROUS:
            pipe_to = self._check_pipe_to_shell(command)
            if pipe_to:
                action.tier = Tier.DANGEROUS

        return action

    def _classify_plain(
        self,
        raw_exe: str,
        executable: str,
        args: list[str],
    ) -> ClassifiedAction:
        """Classify a simple (non-git, non-docker) command.

        Args:
            raw_exe: The raw executable as typed (e.g. ``/bin/rm``).
            executable: The canonical basename (e.g. ``rm``).
            args: Tokenized arguments.

        Returns:
            A :class:`ClassifiedAction`.
        """
        cmd_str = raw_exe + (" " + " ".join(args) if args else "")

        if executable in _DANGEROUS_COMMANDS:
            tier = Tier.DANGEROUS
        elif executable in _DESTRUCTIVE_COMMANDS:
            # rm with -r/-f/-rf flags → dangerous
            if executable == "rm":
                flags = " ".join(args)
                if any(f in flags for f in ("-rf", "-fr", "-r", "-f", "--recursive", "--force")):
                    tier = Tier.DANGEROUS
                else:
                    tier = Tier.DESTRUCTIVE
            else:
                tier = Tier.DESTRUCTIVE
        elif executable in _SAFE_WRITE_COMMANDS:
            tier = Tier.SAFE_WRITE
        elif executable in _READ_ONLY_COMMANDS:
            tier = Tier.READ_ONLY
        else:
            # Unknown executable — safe default for CLI tools
            tier = Tier.SAFE_WRITE

        # Check if this is a script being executed
        script_path: str | None = None
        if Path(raw_exe).suffix in (".py", ".sh", ".bash", ".zsh", ".js", ".ts"):
            script_path = raw_exe
        elif args and Path(args[0]).suffix in (".py", ".sh", ".bash", ".zsh", ".js", ".ts"):
            # python script.py, bash script.sh
            script_path = args[0]

        return ClassifiedAction(
            action_type="bash",
            command=cmd_str,
            executable=executable,
            args=args,
            tier=tier,
            script_path=script_path,
        )

    # ── Write classification ──────────────────────────────────────────

    def classify_write(self, path: str, content: str | None = None) -> ClassifiedAction:
        """Classify a file write action.

        File writes are always classified as :attr:`Tier.SAFE_WRITE`.
        Content validation (forbidden patterns, PII) is performed by the
        :class:`~village.execution.scanner.ContentScanner`, not by the
        classifier.

        Args:
            path: The file path being written to.
            content: Optional file content (not used for tier classification).

        Returns:
            A :class:`ClassifiedAction` with tier ``SAFE_WRITE``.
        """
        return ClassifiedAction(
            action_type="write",
            command=f"write {path}",
            executable=None,
            tier=Tier.SAFE_WRITE,
        )

    # ── Executable resolution ─────────────────────────────────────────

    def resolve_executable(self, name: str) -> str:
        """Resolve a command name to its canonical basename.

        Strips directory prefixes and resolves through ``$PATH``.

        Args:
            name: The command name or path (e.g. ``/bin/rm``, ``./script.py``).

        Returns:
            The canonical basename (e.g. ``rm``).
        """
        return _resolve_executable(name)

    # ── Pipe-to-shell detection ───────────────────────────────────────

    @staticmethod
    def _check_pipe_to_shell(command: str) -> list[str]:
        """Check if a command pipes to shell interpreters.

        Detects patterns like ``curl http://… | sh``, ``wget … | bash``.

        Args:
            command: The raw command string.

        Returns:
            A list of violations found (empty = clean).
        """
        violations: list[str] = []

        # Split on pipe to check right-hand sides
        parts = command.split("|")
        if len(parts) < 2:
            return violations

        for i, part in enumerate(parts[1:], start=2):
            try:
                rhs_tokens = shlex.split(part.strip())
            except ValueError:
                continue
            if not rhs_tokens:
                continue
            rhs_exe = _resolve_executable(rhs_tokens[0])
            if rhs_exe in ("sh", "bash", "zsh", "dash", "ksh", "fish"):
                left_side = "|".join(parts[: i - 1]).strip()
                violations.append(f"Pipe-to-shell detected: '{left_side} | {rhs_exe}' allows arbitrary code execution")

        return violations
