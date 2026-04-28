import logging
from pathlib import Path

import yaml

from village.execution.refs import git_show
from village.rules.schema import (
    FilenameConfig,
    ForbiddenCommandRule,
    ForbiddenContentRule,
    RulesConfig,
    TddConfig,
)

logger = logging.getLogger(__name__)


def _parse_rules(data: dict[str, object] | None) -> RulesConfig | None:
    """Parse a raw dict into a RulesConfig, validating the version field."""
    if data is None:
        return None

    version = data.get("version", 1)
    if not isinstance(version, int) or version < 1:
        logger.warning(f"Invalid rules.yaml version: {version}, expected int >= 1")
        return None

    content_rules_raw = data.get("content_rules")
    content_rules: list[ForbiddenContentRule] | None = None
    if content_rules_raw is not None and isinstance(content_rules_raw, list):
        content_rules = []
        for item in content_rules_raw:
            if isinstance(item, dict):
                content_rules.append(
                    ForbiddenContentRule(
                        match=item.get("match", ""),
                        reason=item.get("reason", ""),
                        paths=item.get("paths"),
                    )
                )

    command_rules_raw = data.get("command_rules")
    command_rules: list[ForbiddenCommandRule] | None = None
    if command_rules_raw is not None and isinstance(command_rules_raw, list):
        command_rules = []
        for item in command_rules_raw:
            if isinstance(item, dict):
                command_rules.append(
                    ForbiddenCommandRule(
                        executables=item.get("executables", []),
                        dangerous_flags=item.get("dangerous_flags"),
                        pipe_to=item.get("pipe_to"),
                        subcommand=item.get("subcommand"),
                        forbidden_flags=item.get("forbidden_flags"),
                        allowed_alternatives=item.get("allowed_alternatives"),
                        files=item.get("files"),
                        reason=item.get("reason", "Forbidden"),
                    )
                )

    tdd_raw = data.get("tdd")
    tdd: TddConfig | None = None
    if tdd_raw is not None and isinstance(tdd_raw, dict):
        tdd = TddConfig(
            enabled=tdd_raw.get("enabled", True),
            test_dirs=tdd_raw.get("test_dirs"),
        )

    filename_raw = data.get("filename")
    filename: FilenameConfig | None = None
    if filename_raw is not None and isinstance(filename_raw, dict):
        filename = FilenameConfig(
            casing=filename_raw.get("casing"),
            paths=filename_raw.get("paths"),
        )

    guardrails_raw = data.get("guardrails")
    guardrails: list[str] | None = None
    if guardrails_raw is not None and isinstance(guardrails_raw, list):
        guardrails = [str(g) for g in guardrails_raw]

    override_token_raw = data.get("override_token")
    override_token = str(override_token_raw) if isinstance(override_token_raw, str) else "SKIP_RULES_CHECK"

    return RulesConfig(
        version=version,
        guardrails=guardrails,
        content_rules=content_rules,
        command_rules=command_rules,
        tdd=tdd,
        filename=filename,
        override_token=override_token,
    )


def load_rules(
    path: Path | None = None,
    git_root: Path | None = None,
    commit: str | None = None,
) -> RulesConfig | None:
    """Load rules configuration from a YAML file or git commit.

    When *commit* and *git_root* are provided, reads the rules from the
    specified git commit (tamper-proof mode).  Falls back to filesystem
    if the commit-based read returns nothing.

    Args:
        path: Path to the rules YAML file (ignored if *commit* is set).
        git_root: Git repository root directory (required with *commit*).
        commit: Git commit SHA to read the rules file from.

    Returns:
        :class:`RulesConfig` or None if the file does not exist or is invalid.
    """
    # Tamper-proof mode: read from git commit
    if commit and git_root:
        content = git_show(git_root, commit, ".village/rules.yaml")
        if content:
            return load_rules_from_string(content)

    # Fallback to filesystem
    if path is None:
        return None
    if not path.exists():
        return None

    try:
        raw = path.read_text(encoding="utf-8")
        return load_rules_from_string(raw)
    except Exception as e:
        logger.warning(f"Failed to load rules from {path}: {e}")
        return None


def load_rules_from_string(yaml_content: str) -> RulesConfig | None:
    """Load rules configuration from a YAML string."""
    try:
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            logger.warning("rules.yaml content is not a mapping")
            return None
        return _parse_rules(data)
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse rules YAML: {e}")
        return None


def get_rules(
    commit: str | None = None,
    git_root: Path | None = None,
) -> RulesConfig | None:
    """Load rules from the default .village/rules.yaml path.

    Discovers the git root and loads from .village/rules.yaml.
    Returns None if no git root or rules file is found.

    Args:
        commit: Optional git commit SHA for tamper-proof reads.
        git_root: Optional git root path (discovered if not provided).

    Returns:
        :class:`RulesConfig` or None.
    """
    if git_root is None:
        try:
            from village.probes.repo import find_git_root

            git_root = find_git_root()
        except RuntimeError:
            return None

    rules_path = git_root / ".village" / "rules.yaml"
    return load_rules(path=rules_path, git_root=git_root, commit=commit)
