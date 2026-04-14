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

        timeout_str = os.environ.get("VILLAGE_LLM_TIMEOUT") or config.get("LLM_TIMEOUT")
        timeout = int(timeout_str) if timeout_str else 300

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
    tool_name_pattern: str = "mcproxy_{server}__{tool}"

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "MCPConfig":
        """Load MCP config from environment variable and config file."""
        enabled_env = os.environ.get("VILLAGE_MCP_ENABLED")
        enabled_config = config.get("MCP_ENABLED")
        enabled_value = enabled_env or enabled_config
        enabled = enabled_value in ("1", "true", "yes") if enabled_value else True

        client_type_env = os.environ.get("VILLAGE_MCP_CLIENT")
        client_type_config = config.get("MCP_CLIENT")
        client_type = client_type_env or client_type_config or "mcp-use"

        mcp_use_path = config.get("MCP_USE_PATH")
        mcp_use_path_value = mcp_use_path if mcp_use_path is not None else "mcp-use"

        pattern_env = os.environ.get("VILLAGE_MCP_TOOL_PATTERN")
        pattern_config = config.get("MCP_TOOL_PATTERN")
        tool_name_pattern = pattern_env or pattern_config or "mcproxy_{server}__{tool}"

        return cls(
            enabled=enabled,
            client_type=client_type,
            mcp_use_path=mcp_use_path_value,
            tool_name_pattern=tool_name_pattern,
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

        interval_str = os.environ.get("VILLAGE_METRICS_EXPORT_INTERVAL") or config.get("METRICS_EXPORT_INTERVAL")
        interval_str = os.environ.get("VILLAGE_METRICS_EXPORT_INTERVAL") or config.get("METRICS_EXPORT_INTERVAL")
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
        interval_str = os.environ.get("VILLAGE_DASHBOARD_REFRESH_INTERVAL") or config.get("DASHBOARD_REFRESH_INTERVAL")
        interval_str = os.environ.get("VILLAGE_DASHBOARD_REFRESH_INTERVAL") or config.get("DASHBOARD_REFRESH_INTERVAL")
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
    type: str = "opencode"  # Agent type: "opencode", "pi", or "acp"
    pi_args: str = ""
    acp_command: Optional[str] = None  # Command to spawn ACP agent
    acp_capabilities: list[str] = field(default_factory=list)  # Capability names


@dataclass
class ExtensionConfig:
    """Extension system configuration."""

    enabled: bool = True
    processor_module: Optional[str] = None
    tool_invoker_module: Optional[str] = None
    thinking_refiner_module: Optional[str] = None
    chat_context_module: Optional[str] = None
    task_hooks_module: Optional[str] = None
    server_discovery_module: Optional[str] = None
    llm_adapter_module: Optional[str] = None

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "ExtensionConfig":
        """Load extension config from environment variable and config file."""
        enabled_env = os.environ.get("VILLAGE_EXTENSIONS_ENABLED") or config.get("EXTENSIONS.ENABLED")
        enabled = enabled_env is None or enabled_env.lower() in ("1", "true", "yes", "")

        processor_module = os.environ.get("VILLAGE_EXTENSIONS_PROCESSOR_MODULE") or config.get(
            "EXTENSIONS.PROCESSOR_MODULE"
        )

        tool_invoker_module = os.environ.get("VILLAGE_EXTENSIONS_TOOL_INVOKER_MODULE") or config.get(
            "EXTENSIONS.TOOL_INVOKER_MODULE"
        )

        thinking_refiner_module = os.environ.get("VILLAGE_EXTENSIONS_THINKING_REFINER_MODULE") or config.get(
            "EXTENSIONS.THINKING_REFINER_MODULE"
        )

        chat_context_module = os.environ.get("VILLAGE_EXTENSIONS_CHAT_CONTEXT_MODULE") or config.get(
            "EXTENSIONS.CHAT_CONTEXT_MODULE"
        )

        task_hooks_module = os.environ.get("VILLAGE_EXTENSIONS_TASK_HOOKS_MODULE") or config.get(
            "EXTENSIONS.TASK_HOOKS_MODULE"
        )

        server_discovery_module = os.environ.get("VILLAGE_EXTENSIONS_SERVER_DISCOVERY_MODULE") or config.get(
            "EXTENSIONS.SERVER_DISCOVERY_MODULE"
        )

        llm_adapter_module = os.environ.get("VILLAGE_EXTENSIONS_LLM_ADAPTER_MODULE") or config.get(
            "EXTENSIONS.LLM_ADAPTER_MODULE"
        )

        return cls(
            enabled=enabled,
            processor_module=processor_module,
            tool_invoker_module=tool_invoker_module,
            thinking_refiner_module=thinking_refiner_module,
            chat_context_module=chat_context_module,
            task_hooks_module=task_hooks_module,
            server_discovery_module=server_discovery_module,
            llm_adapter_module=llm_adapter_module,
        )


@dataclass
class TaskBreakdownConfig:
    """Task breakdown strategy configuration."""

    strategy: str = "st_aot_light"

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "TaskBreakdownConfig":
        """Load task breakdown config from environment variable and config file."""
        strategy_env = os.environ.get("VILLAGE_TASK_BREAKDOWN_STRATEGY")
        strategy_config = config.get("TASK_BREAKDOWN.STRATEGY")
        strategy = strategy_env or strategy_config or "st_aot_light"

        return cls(strategy=strategy)


@dataclass
class MemoryConfig:
    """File-based memory configuration."""

    enabled: bool = False
    store_path: str = ".village/memory/"

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "MemoryConfig":
        """Load memory config from environment variables and config file."""
        enabled_env = os.environ.get("VILLAGE_MEMORY_ENABLED", "").lower()
        enabled_config = config.get("memory.enabled", "").lower() or config.get("MEMORY.ENABLED", "").lower()
        enabled = enabled_env or enabled_config
        memory_enabled = enabled in ("1", "true", "yes")

        store_path_env = os.environ.get("VILLAGE_MEMORY_PATH")
        store_path_config = config.get("memory.store_path") or config.get("MEMORY.STORE_PATH")
        store_path = store_path_env or store_path_config or ".village/memory/"

        return cls(
            enabled=memory_enabled,
            store_path=store_path,
        )


@dataclass
class CouncilConfig:
    default_type: str = "chat"
    max_turns: int = 10
    extension_turns: int = 5
    default_rounds: int = 3
    resolution_strategy: str = "synthesis"
    personas_dir: str = "personas/"

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "CouncilConfig":
        default_type_env = os.environ.get("VILLAGE_COUNCIL_TYPE")
        default_type_config = config.get("council.default_type") or config.get("COUNCIL.DEFAULT_TYPE")
        default_type = default_type_env or default_type_config or "chat"

        max_turns_str = (
            os.environ.get("VILLAGE_COUNCIL_MAX_TURNS")
            or config.get("council.max_turns")
            or config.get("COUNCIL.MAX_TURNS")
        )
        max_turns = int(max_turns_str) if max_turns_str else 10

        ext_turns_str = (
            os.environ.get("VILLAGE_COUNCIL_EXTENSION_TURNS")
            or config.get("council.extension_turns")
            or config.get("COUNCIL.EXTENSION_TURNS")
        )
        extension_turns = int(ext_turns_str) if ext_turns_str else 5

        rounds_str = (
            os.environ.get("VILLAGE_COUNCIL_ROUNDS")
            or config.get("council.default_rounds")
            or config.get("COUNCIL.DEFAULT_ROUNDS")
        )
        default_rounds = int(rounds_str) if rounds_str else 3

        strategy_env = os.environ.get("VILLAGE_COUNCIL_RESOLUTION")
        strategy_config = config.get("council.resolution_strategy") or config.get("COUNCIL.RESOLUTION_STRATEGY")
        resolution_strategy = strategy_env or strategy_config or "synthesis"

        personas_env = os.environ.get("VILLAGE_COUNCIL_PERSONAS_DIR")
        personas_config = config.get("council.personas_dir") or config.get("COUNCIL.PERSONAS_DIR")
        personas_dir = personas_env or personas_config or "personas/"

        return cls(
            default_type=default_type,
            max_turns=max_turns,
            extension_turns=extension_turns,
            default_rounds=default_rounds,
            resolution_strategy=resolution_strategy,
            personas_dir=personas_dir,
        )


@dataclass
class OnboardConfig:
    """Adaptive onboarding configuration."""

    interview_model: str = "openrouter/anthropic/claude-3-haiku"
    max_questions: int = 15
    skip_on_first_up: bool = False
    ppc_mode: str = "onboard"
    ppc_traits: list[str] = field(default_factory=lambda: ["critical", "probing"])
    ppc_format: str = "markdown"
    critic_persona: str = "red-team"
    self_critique: bool = True

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "OnboardConfig":
        """Load onboard config from environment variables and config file."""
        model_env = os.environ.get("VILLAGE_ONBOARD_INTERVIEW_MODEL")
        model_config = config.get("ONBOARD.INTERVIEW_MODEL") or config.get("onboard.interview_model")
        interview_model = model_env or model_config or "openrouter/anthropic/claude-3-haiku"

        max_q_env = os.environ.get("VILLAGE_ONBOARD_MAX_QUESTIONS", "")
        max_q_config = config.get("ONBOARD.MAX_QUESTIONS") or config.get("onboard.max_questions")
        max_questions = int(max_q_env or max_q_config or 15)

        skip_env = os.environ.get("VILLAGE_ONBOARD_SKIP_ON_FIRST_UP", "").lower()
        skip_config = (
            config.get("ONBOARD.SKIP_ON_FIRST_UP", "").lower() or config.get("onboard.skip_on_first_up", "").lower()
        )
        skip_raw = skip_env or skip_config
        skip_on_first_up = skip_raw in ("1", "true", "yes") if skip_raw else False

        ppc_mode_config = config.get("ONBOARD.PPC_MODE") or config.get("onboard.ppc_mode")
        ppc_mode = ppc_mode_config or "onboard"

        traits_config = config.get("ONBOARD.PPC_TRAITS") or config.get("onboard.ppc_traits")
        ppc_traits = (
            [t.strip() for t in traits_config.split(",") if t.strip()] if traits_config else ["critical", "probing"]
        )

        ppc_format_config = config.get("ONBOARD.PPC_FORMAT") or config.get("onboard.ppc_format")
        ppc_format = ppc_format_config or "markdown"

        persona_config = config.get("ONBOARD.CRITIC_PERSONA") or config.get("onboard.critic_persona")
        critic_persona = persona_config or "red-team"

        critique_env = os.environ.get("VILLAGE_ONBOARD_SELF_CRITIQUE", "").lower()
        critique_config = (
            config.get("ONBOARD.SELF_CRITIQUE", "").lower() or config.get("onboard.self_critique", "").lower()
        )
        critique_raw = critique_env or critique_config
        self_critique = critique_raw not in ("0", "false", "no") if critique_raw else True

        return cls(
            interview_model=interview_model,
            max_questions=max_questions,
            skip_on_first_up=skip_on_first_up,
            ppc_mode=ppc_mode,
            ppc_traits=ppc_traits,
            ppc_format=ppc_format,
            critic_persona=critic_persona,
            self_critique=self_critique,
        )


@dataclass
class ACPAgentCapability:
    """ACP agent capability definition."""

    name: str
    description: str = ""
    parameters: dict[str, str] = field(default_factory=dict)


@dataclass
class ACPConfig:
    """ACP server configuration."""

    enabled: bool = False
    server_host: str = "localhost"
    server_port: int = 9876
    protocol_version: int = 1
    capabilities: list[ACPAgentCapability] = field(default_factory=list)
    permission_mode: str = "auto"  # auto | policy
    permission_policy_file: str | None = None

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "ACPConfig":
        """Load ACP config from environment variables and config file."""
        enabled_env = os.environ.get("VILLAGE_ACP_ENABLED", "").lower()
        enabled_config = config.get("ACP.ENABLED", "").lower() or config.get("acp.enabled", "").lower()
        enabled = enabled_env or enabled_config
        acp_enabled = enabled in ("1", "true", "yes")

        host_env = os.environ.get("VILLAGE_ACP_HOST")
        host_config = config.get("ACP.HOST") or config.get("acp.host")
        server_host = host_env or host_config or "localhost"

        port_str = os.environ.get("VILLAGE_ACP_PORT") or config.get("ACP.PORT") or config.get("acp.port")
        server_port = int(port_str) if port_str else 9876

        version_str = os.environ.get("VILLAGE_ACP_VERSION") or config.get("ACP.VERSION") or config.get("acp.version")
        protocol_version = int(version_str) if version_str else 1

        capabilities: list[ACPAgentCapability] = []
        for key, value in config.items():
            if key.startswith("ACP.CAPABILITY_") or key.startswith("acp.capability_"):
                prefix = "ACP.CAPABILITY_" if key.startswith("ACP.CAPABILITY_") else "acp.capability_"
                cap_name = key[len(prefix) :].lower()
                capabilities.append(
                    ACPAgentCapability(
                        name=cap_name,
                        description=value,
                    )
                )

        permission_mode = (
            os.environ.get("VILLAGE_ACP_PERMISSION_MODE")
            or config.get("ACP.PERMISSION_MODE")
            or config.get("acp.permission_mode")
            or "auto"
        )

        permission_policy_file = (
            os.environ.get("VILLAGE_ACP_PERMISSION_POLICY_FILE")
            or config.get("ACP.PERMISSION_POLICY_FILE")
            or config.get("acp.permission_policy_file")
        )

        return cls(
            enabled=acp_enabled,
            server_host=server_host,
            server_port=server_port,
            protocol_version=protocol_version,
            capabilities=capabilities,
            permission_mode=permission_mode,
            permission_policy_file=permission_policy_file,
        )


@dataclass
class ApprovalConfig:
    """Approval gate configuration."""

    enabled: bool = False
    threshold: int = 1

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "ApprovalConfig":
        """Load approval config from environment variables and config file."""
        enabled_env = os.environ.get("VILLAGE_APPROVAL_ENABLED", "").lower()
        enabled_config = (
            config.get("queue.approval_enabled", "").lower() or config.get("QUEUE.APPROVAL_ENABLED", "").lower()
        )
        enabled = enabled_env or enabled_config
        approval_enabled = enabled in ("1", "true", "yes")

        threshold_str = (
            os.environ.get("VILLAGE_APPROVAL_THRESHOLD")
            or config.get("queue.approval_threshold")
            or config.get("QUEUE.APPROVAL_THRESHOLD")
        )
        threshold = int(threshold_str) if threshold_str else 1

        return cls(enabled=approval_enabled, threshold=threshold)


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
    traces_dir: Path = field(init=False)
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
    task_breakdown: TaskBreakdownConfig = field(default_factory=TaskBreakdownConfig)
    acp: ACPConfig = field(default_factory=ACPConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    onboard: OnboardConfig = field(default_factory=OnboardConfig)
    council: CouncilConfig = field(default_factory=CouncilConfig)
    approval: ApprovalConfig = field(default_factory=ApprovalConfig)

    def __post_init__(self) -> None:
        """Compute derived paths."""
        self._config_path = self.village_dir / "config"
        self.locks_dir = self.village_dir / "locks"
        self.traces_dir = self.village_dir / "traces"

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
        logger.debug(f"Creating {self.traces_dir}")
        self.traces_dir.mkdir(exist_ok=True)
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


def _validate_acp_agent(agent_name: str, agent_config: AgentConfig) -> list[str]:
    """
    Validate ACP agent configuration.

    Args:
        agent_name: Agent name
        agent_config: Agent configuration

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if agent_config.type == "acp":
        # ACP agents require acp_command
        if not agent_config.acp_command:
            errors.append(f"ACP agent '{agent_name}' missing required field 'acp_command'")

        # Validate command is executable
        if agent_config.acp_command:
            cmd_parts = agent_config.acp_command.split()
            if cmd_parts:
                executable = cmd_parts[0]
                # Check if it's a path or command name
                if "/" not in executable:
                    # It's a command name - we can't validate without running it
                    pass
                else:
                    # It's a path - validate it exists
                    from pathlib import Path

                    if not Path(executable).exists():
                        errors.append(f"ACP agent '{agent_name}' command executable not found: {executable}")

    return errors


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


def _normalize_config(config: dict[str, str]) -> dict[str, str]:
    """Add uppercase SECTION_KEY forms for section.key entries.

    Bridges the gap between config file format (section.key)
    and what from_env_and_config methods expect (SECTION_KEY).
    """
    normalized = dict(config)
    for key, value in config.items():
        if "." in key:
            flat = key.upper().replace(".", "_")
            if flat not in normalized:
                normalized[flat] = value
    return normalized


# Sub-config fields shared between Config and GlobalConfig.
# Single source of truth — add new sub-configs here only.
_SUB_CONFIGS: list[tuple[str, type]] = [
    ("llm", LLMConfig),
    ("mcp", MCPConfig),
    ("safety", SafetyConfig),
    ("conflict", ConflictConfig),
    ("metrics", MetricsConfig),
    ("dashboard", DashboardConfig),
    ("ci", CIConfig),
    ("notifications", NotificationConfig),
    ("extensions", ExtensionConfig),
    ("task_breakdown", TaskBreakdownConfig),
    ("acp", ACPConfig),
    ("memory", MemoryConfig),
    ("onboard", OnboardConfig),
    ("council", CouncilConfig),
    ("approval", ApprovalConfig),
]


def _build_sub_configs(file_config: dict[str, str]) -> dict[str, object]:
    """Build all sub-config objects from a flat config dict."""
    return {name: cls.from_env_and_config(file_config) for name, cls in _SUB_CONFIGS}


def _global_config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(xdg) / "village" / "config"


def _load_global_config() -> dict[str, str]:
    path = _global_config_path()
    raw = _parse_config_file(path)
    if raw:
        logger.debug(f"Loaded global config from {path}: {len(raw)} keys")
    return raw


def _merge_configs(global_config: dict[str, str], project_config: dict[str, str]) -> dict[str, str]:
    """Merge global and project configs, with project taking priority.

    Applies normalization after merge so SECTION_KEY forms reflect
    the final merged values, not just global values.
    """
    merged = dict(global_config)
    merged.update(project_config)
    return _normalize_config(merged)


@dataclass
class GlobalConfig:
    """Configuration from global config file (~/.config/village/config).

    Unlike Config, this has no project-specific paths or git root.
    Used by tools that need config outside a project context (e.g., interview engine).
    """

    agents: dict[str, AgentConfig] = field(default_factory=dict)
    llm: LLMConfig = field(default_factory=LLMConfig)
    onboard: OnboardConfig = field(default_factory=OnboardConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    council: CouncilConfig = field(default_factory=CouncilConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    conflict: ConflictConfig = field(default_factory=ConflictConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    extensions: ExtensionConfig = field(default_factory=ExtensionConfig)
    task_breakdown: TaskBreakdownConfig = field(default_factory=TaskBreakdownConfig)
    acp: ACPConfig = field(default_factory=ACPConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    approval: ApprovalConfig = field(default_factory=ApprovalConfig)
    ci: CIConfig = field(default_factory=CIConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)


def get_global_config() -> GlobalConfig:
    raw_config = _load_global_config()
    file_config = _normalize_config(raw_config)
    sub_configs = _build_sub_configs(file_config)
    return GlobalConfig(**sub_configs)


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

    return _build_config(git_root)


def get_config_for_cwd(cwd: str | Path) -> Config:
    """
    Get configuration for a specific working directory.

    This is used by ACP when the editor provides a cwd for the project.

    Args:
        cwd: Working directory (should be a git repository)

    Returns:
        Config object with resolved paths and agent configs

    Raises:
        RuntimeError: If cwd is not in a git repository
    """
    import subprocess

    cwd = Path(cwd).resolve()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        git_root = Path(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Not a git repository: {cwd}") from e

    return _build_config(git_root)


def _build_config(git_root: Path) -> Config:
    """
    Build Config object for a given git root.

    Args:
        git_root: Path to git repository root

    Returns:
        Config object with resolved paths and agent configs
    """
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
    global_config = _load_global_config()
    project_config = _parse_config_file(config_path)
    file_config = _merge_configs(global_config, project_config)

    # Override max_workers from env var if provided
    max_workers_str = os.environ.get("VILLAGE_MAX_WORKERS")
    max_workers = DEFAULT_MAX_WORKERS
    if max_workers_str:
        try:
            max_workers = int(max_workers_str)
            if max_workers < 1:
                logger.warning(f"VILLAGE_MAX_WORKERS must be >=1, using default: {DEFAULT_MAX_WORKERS}")
                max_workers = DEFAULT_MAX_WORKERS
        except ValueError:
            logger.warning(f"Invalid VILLAGE_MAX_WORKERS value, using default: {DEFAULT_MAX_WORKERS}")

    # Override queue_ttl_minutes from env var or config file
    queue_ttl_str = os.environ.get("VILLAGE_QUEUE_TTL_MINUTES") or file_config.get("QUEUE_TTL_MINUTES")
    queue_ttl_minutes = DEFAULT_QUEUE_TTL_MINUTES
    if queue_ttl_str:
        try:
            queue_ttl_minutes = int(queue_ttl_str)
            if queue_ttl_minutes < 0:
                logger.warning(f"VILLAGE_QUEUE_TTL_MINUTES must be >=0, using default: {DEFAULT_QUEUE_TTL_MINUTES}")
                queue_ttl_minutes = DEFAULT_QUEUE_TTL_MINUTES
        except ValueError:
            logger.warning(f"Invalid VILLAGE_QUEUE_TTL_MINUTES value, using default: {DEFAULT_QUEUE_TTL_MINUTES}")

    # Override scm_kind from env var or config file
    scm_kind = os.environ.get("VILLAGE_SCM") or file_config.get("SCM_KIND") or DEFAULT_SCM_KIND

    # Override default_agent from env var or config file
    default_agent = os.environ.get("VILLAGE_DEFAULT_AGENT") or file_config.get("DEFAULT_AGENT") or DEFAULT_AGENT

    # Parse sub-configurations (shared with GlobalConfig via _SUB_CONFIGS)
    sub_configs = _build_sub_configs(file_config)

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
            elif field_name == "pi_args":
                agents[agent_name].pi_args = value
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
            elif field_name == "type":
                agents[agent_name].type = value.lower() if value else "opencode"
            elif field_name == "acp_command":
                agents[agent_name].acp_command = value
            elif field_name == "acp_capabilities":
                # Parse comma-separated capabilities
                agents[agent_name].acp_capabilities = [cap.strip().lower() for cap in value.split(",") if cap.strip()]

    # Validate ACP agents
    validation_errors = []
    for agent_name, agent_config in agents.items():
        errors = _validate_acp_agent(agent_name, agent_config)
        validation_errors.extend(errors)

    if validation_errors:
        error_msg = "Agent configuration errors:\n" + "\n".join(f"  - {e}" for e in validation_errors)
        logger.error(error_msg)
        # Don't raise - just warn. Allow partial configs for development.
        # raise ValueError(error_msg)

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
        **sub_configs,
    )
