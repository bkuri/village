"""Configuration loader."""

import configparser
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from village.probes.repo import find_git_root

TMUX_SESSION = "village"
DEFAULT_WORKTREES_DIR_NAME = ".worktrees"
DEFAULT_AGENT = "worker"
DEFAULT_MAX_WORKERS = 2
DEFAULT_SCM_KIND = "git"
DEFAULT_QUEUE_TTL_MINUTES = 5

logger = logging.getLogger(__name__)


@dataclass
class DebugConfig:
    """Debug configuration."""

    enabled: bool = False

    @classmethod
    def from_env(cls) -> "DebugConfig":
        """Load debug config from environment variable."""
        debug_env = os.environ.get("VILLAGE_DEBUG", "").lower()
        enabled = debug_env in ("1", "true", "yes")
        return cls(enabled=enabled)


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    provider: str = "openrouter"
    model: str = "anthropic/claude-3.5-sonnet"
    api_key_env: str = "OPENROUTER_API_KEY"
    timeout: int = 300
    max_tokens: int = 4096


@dataclass
class MCPConfig:
    """MCP client configuration."""

    enabled: bool = True
    client_type: str = "mcp-use"
    mcp_use_path: str = "mcp-use"


@dataclass
class AgentConfig:
    """Configuration for a single agent type."""

    opencode_args: str = ""
    contract: Optional[str] = None
    ppc_mode: Optional[str] = None
    ppc_traits: list[str] = field(default_factory=list)
    ppc_format: str = "markdown"
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


@dataclass
class Config:
    """Village configuration."""

    git_root: Path
    village_dir: Path
    worktrees_dir: Path
    tmux_session: str = TMUX_SESSION
    scm_kind: str = DEFAULT_SCM_KIND
    default_agent: str = DEFAULT_AGENT
    max_workers: int = DEFAULT_MAX_WORKERS
    queue_ttl_minutes: int = DEFAULT_QUEUE_TTL_MINUTES
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    _config_path: Path = field(init=False)
    locks_dir: Path = field(init=False)
    debug: DebugConfig = field(default_factory=DebugConfig.from_env)
    llm: LLMConfig = field(default_factory=LLMConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)

    def __post_init__(self) -> None:
        """Compute derived paths."""
        self._config_path = self.village_dir / "config"
        self.locks_dir = self.village_dir / "locks"

    @property
    def config_path(self) -> Path:
        """Get config file path."""
        return self._config_path

    def config_exists(self) -> bool:
        """Check if config file exists."""
        return self._config_path.exists()

    def ensure_exists(self) -> None:
        """Ensure village directories exist (mutating)."""
        logger.debug(f"Creating {self.village_dir}")
        self.village_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Creating {self.locks_dir}")
        self.locks_dir.mkdir(exist_ok=True)
        logger.debug(f"Creating {self.worktrees_dir}")
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)


def _parse_ppc_traits(value: str) -> list[str]:
    """
    Parse comma-separated PPC traits.

    Args:
        value: Comma-separated trait string (e.g., "conservative,terse")

    Returns:
        List of trait names (lowercase, trimmed)
    """
    if not value:
        return []
    return [t.strip().lower() for t in value.split(",") if t.strip()]


def _parse_config_file(config_path: Path) -> dict[str, str]:
    """
    Parse INI-style config file.

    Returns:
        Dict of config values (flattened: section.key -> value)
    """
    if not config_path.exists():
        return {}

    parser = configparser.ConfigParser()
    parser.read(config_path)

    config = {}

    # Parse DEFAULT section (values without [DEFAULT] prefix)
    if "DEFAULT" in parser:
        for key, value in parser["DEFAULT"].items():
            config[key.upper()] = value

    # Parse other sections
    for section in parser.sections():
        for key, value in parser[section].items():
            if section == "DEFAULT":
                continue
            config[f"{section}.{key}"] = value

    return config


def get_config() -> Config:
    """
    Get current configuration.

    Resolves from:
    1. Git repo root (required)
    2. Config file (.village/config)
    3. Environment variables (optional)

    Returns:
        Config object with resolved paths and agent configs

    Raises:
        RuntimeError: If not in a git repository
    """
    git_root = find_git_root()

    # Override paths from env vars if provided
    village_dir = Path(os.environ.get("VILLAGE_DIR", git_root / ".village"))
    worktrees_dir = Path(
        os.environ.get(
            "VILLAGE_WORKTREES_DIR",
            git_root / DEFAULT_WORKTREES_DIR_NAME,
        )
    )

    # Parse config file if it exists
    config_path = village_dir / "config"
    file_config = _parse_config_file(config_path)

    # Override max_workers from env var if provided
    max_workers_str = os.environ.get("VILLAGE_MAX_WORKERS")
    max_workers = DEFAULT_MAX_WORKERS
    if max_workers_str:
        try:
            max_workers = int(max_workers_str)
            if max_workers < 1:
                logger.warning(
                    f"VILLAGE_MAX_WORKERS must be >=1, using default: {DEFAULT_MAX_WORKERS}"
                )
                max_workers = DEFAULT_MAX_WORKERS
        except ValueError:
            logger.warning(
                f"Invalid VILLAGE_MAX_WORKERS value, using default: {DEFAULT_MAX_WORKERS}"
            )

    # Override queue_ttl_minutes from env var or config file
    queue_ttl_str = os.environ.get("VILLAGE_QUEUE_TTL_MINUTES") or file_config.get(
        "QUEUE_TTL_MINUTES"
    )
    queue_ttl_minutes = DEFAULT_QUEUE_TTL_MINUTES
    if queue_ttl_str:
        try:
            queue_ttl_minutes = int(queue_ttl_str)
            if queue_ttl_minutes < 0:
                logger.warning(
                    f"VILLAGE_QUEUE_TTL_MINUTES must be >=0, "
                    f"using default: {DEFAULT_QUEUE_TTL_MINUTES}"
                )
                queue_ttl_minutes = DEFAULT_QUEUE_TTL_MINUTES
        except ValueError:
            logger.warning(
                f"Invalid VILLAGE_QUEUE_TTL_MINUTES value, "
                f"using default: {DEFAULT_QUEUE_TTL_MINUTES}"
            )

    # Override scm_kind from env var or config file
    scm_kind = os.environ.get("VILLAGE_SCM") or file_config.get("SCM_KIND") or DEFAULT_SCM_KIND

    # Override default_agent from env var or config file
    default_agent = (
        os.environ.get("VILLAGE_DEFAULT_AGENT") or file_config.get("DEFAULT_AGENT") or DEFAULT_AGENT
    )

    # Parse LLM configuration
    llm_config = LLMConfig()
    llm_provider = os.environ.get("VILLAGE_LLM_PROVIDER") or file_config.get("LLM_PROVIDER")
    if llm_provider:
        llm_config.provider = llm_provider

    llm_model = os.environ.get("VILLAGE_LLM_MODEL") or file_config.get("LLM_MODEL")
    if llm_model:
        llm_config.model = llm_model

    llm_api_key_env = file_config.get("LLM_API_KEY_ENV")
    if llm_api_key_env:
        llm_config.api_key_env = llm_api_key_env

    llm_timeout_str = os.environ.get("VILLAGE_LLM_TIMEOUT") or file_config.get("LLM_TIMEOUT")
    if llm_timeout_str:
        try:
            llm_config.timeout = int(llm_timeout_str)
        except ValueError:
            logger.warning(f"Invalid LLM_TIMEOUT value, using default: {llm_config.timeout}")

    llm_max_tokens_str = os.environ.get("VILLAGE_LLM_MAX_TOKENS") or file_config.get(
        "LLM_MAX_TOKENS"
    )
    if llm_max_tokens_str:
        try:
            llm_config.max_tokens = int(llm_max_tokens_str)
        except ValueError:
            logger.warning(f"Invalid LLM_MAX_TOKENS value, using default: {llm_config.max_tokens}")

    # Parse MCP configuration
    mcp_config = MCPConfig()
    mcp_enabled_str = os.environ.get("VILLAGE_MCP_ENABLED") or file_config.get("MCP_ENABLED")
    if mcp_enabled_str:
        mcp_config.enabled = mcp_enabled_str.lower() in ("1", "true", "yes")

    mcp_client_type = os.environ.get("VILLAGE_MCP_CLIENT") or file_config.get("MCP_CLIENT")
    if mcp_client_type:
        mcp_config.client_type = mcp_client_type

    mcp_use_path = file_config.get("MCP_USE_PATH")
    if mcp_use_path:
        mcp_config.mcp_use_path = mcp_use_path

    # Parse agent configs from file
    agents: dict[str, AgentConfig] = {}
    for key, value in file_config.items():
        if key.startswith("agent.") or key.startswith("AGENT."):
            # ConfigParser normalizes section names to lowercase
            # Key format: agent.build.opencode_args
            parts = key.split(".")
            if len(parts) < 3:
                continue

            agent_name = parts[1].lower()
            field_name = parts[2].lower()

            if agent_name not in agents:
                agents[agent_name] = AgentConfig()

            if field_name == "opencode_args":
                agents[agent_name].opencode_args = value
            elif field_name == "contract":
                agents[agent_name].contract = value
            elif field_name == "ppc_mode":
                agents[agent_name].ppc_mode = value.lower() if value else None
            elif field_name == "ppc_traits":
                agents[agent_name].ppc_traits = _parse_ppc_traits(value)
            elif field_name == "ppc_format":
                agents[agent_name].ppc_format = value.lower() if value else "markdown"
            elif field_name == "llm_provider":
                agents[agent_name].llm_provider = value.lower() if value else None
            elif field_name == "llm_model":
                agents[agent_name].llm_model = value if value else None

    logger.debug(f"Git root: {git_root}")
    logger.debug(f"Village dir: {village_dir}")
    logger.debug(f"Worktrees dir: {worktrees_dir}")
    logger.debug(f"Max workers: {max_workers}")
    logger.debug(f"Queue TTL minutes: {queue_ttl_minutes}")
    logger.debug(f"SCM kind: {scm_kind}")

    valid_scms = ["git", "jj"]
    if scm_kind not in valid_scms:
        raise ValueError(f"Invalid SCM kind: {scm_kind}. Must be one of: {', '.join(valid_scms)}")

    if scm_kind == "jj":
        logger.debug("Using Jujutsu (jj) SCM backend")

    logger.debug(f"Default agent: {default_agent}")
    logger.debug(f"Agent configs: {list(agents.keys())}")

    return Config(
        git_root=git_root,
        village_dir=village_dir,
        worktrees_dir=worktrees_dir,
        scm_kind=scm_kind,
        max_workers=max_workers,
        queue_ttl_minutes=queue_ttl_minutes,
        default_agent=default_agent,
        agents=agents,
        llm=llm_config,
        mcp=mcp_config,
    )
