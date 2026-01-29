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

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "LLMConfig":
        """Load LLM config from environment variables and config file."""
        provider_env = os.environ.get("VILLAGE_LLM_PROVIDER")
        provider_config = config.get("LLM_PROVIDER")
        provider = provider_env or provider_config or "openrouter"

        model_env = os.environ.get("VILLAGE_LLM_MODEL")
        model_config = config.get("LLM_MODEL")
        model = model_env or model_config or "anthropic/claude-3.5-sonnet"

        api_key_env = os.environ.get("VILLAGE_LLM_API_KEY")
        api_key_config = config.get("LLM_API_KEY")
        api_key = api_key_env or api_key_config

        timeout_env = os.environ.get("VILLAGE_LLM_TIMEOUT")
        timeout_str = os.environ.get("VILLAGE_LLM_TIMEOUT") or config.get("LLM_TIMEOUT")
        timeout = int(timeout_str) if timeout_str else 300

        max_tokens_env = os.environ.get("VILLAGE_LLM_MAX_TOKENS")
        max_tokens_str = os.environ.get("VILLAGE_LLM_MAX_TOKENS") or config.get("LLM_MAX_TOKENS")
        max_tokens = int(max_tokens_str) if max_tokens_str else 4096

        llm_config = LLMConfig(
            provider=provider,
            model=model,
            timeout=timeout,
            max_tokens=max_tokens,
        )
        if api_key:
            llm_config.api_key_env = api_key

        return llm_config


@dataclass
class MCPConfig:
    """MCP client configuration."""

    enabled: bool = True
    client_type: str = "mcp-use"
    mcp_use_path: str = "mcp-use"

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "MCPConfig":
        """Load MCP config from environment variable and config file."""
        enabled_env = os.environ.get("VILLAGE_MCP_ENABLED")
        enabled_config = config.get("MCP_ENABLED")
        enabled = enabled_env or enabled_config
        enabled = enabled in ("1", "true", "yes")

        client_type_env = os.environ.get("VILLAGE_MCP_CLIENT")
        client_type_config = config.get("MCP_CLIENT")
        client_type = client_type_env or client_type_config or "mcp-use"

        mcp_use_path = config.get("MCP_USE_PATH")
        mcp_use_path_value = mcp_use_path if mcp_use_path is not None else "mcp-use"

        return cls(
            enabled=enabled,
            client_type=client_type,
            mcp_use_path=mcp_use_path_value,
        )


@dataclass
class SafetyConfig:
    """Safety configuration for rollback behavior."""

    rollback_on_failure: bool = True

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "SafetyConfig":
        """Load safety config from environment variable and config file."""
        rollback_env = os.environ.get("VILLAGE_ROLLBACK_ON_FAILURE", "").lower()
        rollback_config = config.get("ROLLBACK_ON_FAILURE", "").lower()
        rollback_on_failure = rollback_env or rollback_config
        enabled = rollback_on_failure in ("1", "true", "yes")

        return cls(rollback_on_failure=enabled)


@dataclass
class ConflictConfig:
    """Conflict detection configuration."""

    enabled: bool = True
    block_on_conflict: bool = False

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "ConflictConfig":
        """Load conflict config from environment variables and config file."""
        enabled_env = os.environ.get("VILLAGE_CONFLICT_DETECTION_ENABLED", "").lower()
        enabled_config = config.get("CONFLICT_DETECTION_ENABLED", "").lower()
        enabled = enabled_env or enabled_config
        conflict_detection_enabled = enabled in ("1", "true", "yes")

        block_env = os.environ.get("VILLAGE_BLOCK_ON_CONFLICT", "").lower()
        block_config = config.get("BLOCK_ON_CONFLICT", "").lower()
        block = block_env or block_config
        block_on_conflict = block in ("1", "true", "yes")

        return cls(
            enabled=conflict_detection_enabled,
            block_on_conflict=block_on_conflict,
        )


@dataclass
class MetricsConfig:
    """Metrics configuration."""

    backend: str = "prometheus"
    port: int = 9090
    export_interval_seconds: int = 60
    statsd_host: str = "localhost"
    statsd_port: int = 8125

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "MetricsConfig":
        """Load metrics config from environment variables and config file."""
        backend_env = os.environ.get("VILLAGE_METRICS_BACKEND")
        backend_config = config.get("METRICS_BACKEND")
        backend = backend_env or backend_config or "prometheus"

        port_str = os.environ.get("VILLAGE_METRICS_PORT") or config.get("METRICS_PORT")
        port = int(port_str) if port_str else 9090

        interval_str = os.environ.get("VILLAGE_METRICS_EXPORT_INTERVAL") or config.get(
            "METRICS_EXPORT_INTERVAL"
        )
        interval_str = os.environ.get("VILLAGE_METRICS_EXPORT_INTERVAL") or config.get(
            "METRICS_EXPORT_INTERVAL"
        )
        export_interval_seconds = int(interval_str) if interval_str else 60

        statsd_host_env = os.environ.get("VILLAGE_STATSD_HOST")
        statsd_host_config = config.get("STATSD_HOST")
        statsd_host = statsd_host_env or statsd_host_config or "localhost"

        statsd_port_str = os.environ.get("VILLAGE_STATSD_PORT") or config.get("STATSD_PORT")
        statsd_port = int(statsd_port_str) if statsd_port_str else 8125

        return cls(
            backend=backend,
            port=port,
            export_interval_seconds=export_interval_seconds,
            statsd_host=statsd_host,
            statsd_port=statsd_port,
        )


@dataclass
class DashboardConfig:
    """Dashboard configuration."""

    refresh_interval_seconds: int = 2
    enabled: bool = True

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "DashboardConfig":
        """Load dashboard config from environment variables and config file."""
        interval_str = os.environ.get("VILLAGE_DASHBOARD_REFRESH_INTERVAL") or config.get(
            "DASHBOARD_REFRESH_INTERVAL"
        )
        interval_str = os.environ.get("VILLAGE_DASHBOARD_REFRESH_INTERVAL") or config.get(
            "DASHBOARD_REFRESH_INTERVAL"
        )
        refresh_interval_seconds = int(interval_str) if interval_str else 2

        enabled_env = os.environ.get("VILLAGE_DASHBOARD_ENABLED", "").lower()
        enabled_config = config.get("DASHBOARD_ENABLED", "").lower()
        enabled = enabled_env or enabled_config
        dashboard_enabled = enabled in ("1", "true", "yes")

        return cls(
            refresh_interval_seconds=refresh_interval_seconds,
            enabled=dashboard_enabled,
        )


@dataclass
class CIConfig:
    """CI/CD configuration."""

    github_token: str | None = None
    gitlab_token: str | None = None
    jenkins_token: str | None = None

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "CIConfig":
        """Load CI/CD config from environment variables."""
        github_token = os.environ.get("GITHUB_TOKEN")
        gitlab_token = os.environ.get("GITLAB_TOKEN")
        jenkins_token = os.environ.get("JENKINS_TOKEN")

        return cls(
            github_token=github_token,
            gitlab_token=gitlab_token,
            jenkins_token=jenkins_token,
        )


@dataclass
class NotificationConfig:
    """Notification configuration."""

    slack_webhook_url: str | None = None
    discord_webhook_url: str | None = None
    email_smtp_server: str | None = None
    task_failed_enabled: bool = False
    orphan_detected_enabled: bool = False
    high_priority_task_enabled: bool = False

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "NotificationConfig":
        """Load notification config from environment variables."""
        slack_webhook_url = os.environ.get("VILLAGE_SLACK_WEBHOOK_URL")
        discord_webhook_url = os.environ.get("VILLAGE_DISCORD_WEBHOOK_URL")
        email_smtp_server = os.environ.get("VILLAGE_EMAIL_SMTP_SERVER")

        task_failed_env = os.environ.get("VILLAGE_NOTIFY_TASK_FAILED", "false")
        task_failed = task_failed_env in ("1", "true", "yes")

        orphan_detected_env = os.environ.get("VILLAGE_NOTIFY_ORPHAN_DETECTED", "false")
        orphan_detected = orphan_detected_env in ("1", "true", "yes")

        high_priority_task_env = os.environ.get("VILLAGE_NOTIFY_HIGH_PRIORITY_TASK", "false")
        high_priority_task = high_priority_task_env in ("1", "true", "yes")

        return cls(
            slack_webhook_url=slack_webhook_url,
            discord_webhook_url=discord_webhook_url,
            email_smtp_server=email_smtp_server,
            task_failed_enabled=task_failed,
            orphan_detected_enabled=orphan_detected,
            high_priority_task_enabled=high_priority_task,
        )


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
class ExtensionConfig:
    """Extension system configuration."""

    enabled: bool = True
    processor_module: Optional[str] = None
    tool_invoker_module: Optional[str] = None
    thinking_refiner_module: Optional[str] = None
    chat_context_module: Optional[str] = None
    beads_integrator_module: Optional[str] = None
    server_discovery_module: Optional[str] = None
    llm_adapter_module: Optional[str] = None

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "ExtensionConfig":
        """Load extension config from environment variables and config file."""
        enabled_env = os.environ.get("VILLAGE_EXTENSIONS_ENABLED", "").lower()
        enabled_config = config.get("EXTENSIONS.ENABLED", "").lower()
        enabled = enabled_env or enabled_config
        extensions_enabled = enabled in ("1", "true", "yes") or not (enabled_env or enabled_config)

        processor_module = os.environ.get("VILLAGE_EXTENSION_PROCESSOR") or config.get(
            "EXTENSIONS.PROCESSOR_MODULE"
        )
        tool_invoker_module = os.environ.get("VILLAGE_EXTENSION_TOOL_INVOKER") or config.get(
            "EXTENSIONS.TOOL_INVOKER_MODULE"
        )
        thinking_refiner_module = os.environ.get("VILLAGE_EXTENSION_THINKING_REFINER") or config.get(
            "EXTENSIONS.THINKING_REFINER_MODULE"
        )
        chat_context_module = os.environ.get("VILLAGE_EXTENSION_CHAT_CONTEXT") or config.get(
            "EXTENSIONS.CHAT_CONTEXT_MODULE"
        )
        beads_integrator_module = os.environ.get("VILLAGE_EXTENSION_BEADS_INTEGRATOR") or config.get(
            "EXTENSIONS.BEADS_INTEGRATOR_MODULE"
        )
        server_discovery_module = os.environ.get("VILLAGE_EXTENSION_SERVER_DISCOVERY") or config.get(
            "EXTENSIONS.SERVER_DISCOVERY_MODULE"
        )
        llm_adapter_module = os.environ.get("VILLAGE_EXTENSION_LLM_ADAPTER") or config.get(
            "EXTENSIONS.LLM_ADAPTER_MODULE"
        )

        return cls(
            enabled=extensions_enabled,
            processor_module=processor_module,
            tool_invoker_module=tool_invoker_module,
            thinking_refiner_module=thinking_refiner_module,
            chat_context_module=chat_context_module,
            beads_integrator_module=beads_integrator_module,
            server_discovery_module=server_discovery_module,
            llm_adapter_module=llm_adapter_module,
        )


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
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    conflict: ConflictConfig = field(default_factory=ConflictConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    ci: CIConfig = field(default_factory=CIConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    extensions: ExtensionConfig = field(default_factory=ExtensionConfig)

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
    llm_config = LLMConfig.from_env_and_config(file_config)

    # Parse MCP configuration
    mcp_config = MCPConfig.from_env_and_config(file_config)

    # Parse safety configuration
    safety_config = SafetyConfig.from_env_and_config(file_config)

    # Parse conflict configuration
    conflict_config = ConflictConfig.from_env_and_config(file_config)

    # Parse metrics configuration
    metrics_config = MetricsConfig.from_env_and_config(file_config)

    # Parse dashboard configuration
    dashboard_config = DashboardConfig.from_env_and_config(file_config)

    # Parse CI configuration
    ci_config = CIConfig.from_env_and_config(file_config)

    # Parse notifications configuration
    notifications_config = NotificationConfig.from_env_and_config(file_config)

    # Parse extension configuration
    extensions_config = ExtensionConfig.from_env_and_config(file_config)

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
    logger.debug(f"Default agent: {default_agent}")
    logger.debug(f"Agent configs: {list(agents.keys())}")

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
        safety=safety_config,
        conflict=conflict_config,
        metrics=metrics_config,
        dashboard=dashboard_config,
        ci=ci_config,
        notifications=notifications_config,
        extensions=extensions_config,
    )
