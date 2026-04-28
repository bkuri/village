from dataclasses import dataclass


@dataclass
class ForbiddenContentRule:
    """A rule forbidding certain content patterns in files."""

    match: str  # literal or regex pattern
    reason: str
    paths: list[str] | None = None  # gitignore-style globs, optional


@dataclass
class ForbiddenCommandRule:
    """A rule forbidding certain commands or command patterns."""

    executables: list[str]  # ["rm", "/bin/rm", "/usr/bin/rm"]
    dangerous_flags: list[str] | None = None  # ["-rf", "-r", "--recursive", "--force"]
    pipe_to: list[str] | None = None  # ["sh", "bash", "zsh", "sudo"]
    subcommand: str | None = None  # for git: "push"
    forbidden_flags: list[str] | None = None  # ["--force", "-f"]
    allowed_alternatives: list[str] | None = None  # ["--force-with-lease"]
    files: list[str] | None = None  # path patterns this applies to
    reason: str = "Forbidden"


@dataclass
class TddConfig:
    """TDD enforcement configuration."""

    enabled: bool = True
    test_dirs: list[str] | None = None  # default: ["tests/", "test/"]


@dataclass
class FilenameConfig:
    """Filename casing enforcement configuration."""

    casing: str | None = None  # "snake_case", "kebab-case", "camelCase"
    paths: list[str] | None = None  # glob patterns


@dataclass
class RulesConfig:
    """Global policy rules configuration loaded from .village/rules.yaml."""

    version: int = 1
    guardrails: list[str] | None = None  # PPC guardrail module names
    content_rules: list[ForbiddenContentRule] | None = None
    command_rules: list[ForbiddenCommandRule] | None = None
    tdd: TddConfig | None = None
    filename: FilenameConfig | None = None
    override_token: str = "SKIP_RULES_CHECK"
