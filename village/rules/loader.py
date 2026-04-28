import logging
from pathlib import Path

import yaml

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


def load_rules(path: Path) -> RulesConfig | None:
    """Load rules configuration from a YAML file.

    Returns None if the file does not exist or is invalid.
    """
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


def get_rules() -> RulesConfig | None:
    """Load rules from the default .village/rules.yaml path.

    Discovers the git root and loads from .village/rules.yaml.
    Returns None if no git root or rules file is found.
    """
    try:
        from village.probes.repo import find_git_root

        git_root = find_git_root()
    except RuntimeError:
        return None

    rules_path = git_root / ".village" / "rules.yaml"
    return load_rules(rules_path)
