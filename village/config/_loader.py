import configparser
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from village.config._agents import AgentConfig, _parse_ppc_traits, _validate_acp_agent
from village.config._sub_configs import (
    ACPConfig,
    ApprovalConfig,
    CIConfig,
    ConflictConfig,
    CouncilConfig,
    DashboardConfig,
    DebugConfig,
    ExtensionConfig,
    LLMConfig,
    MCPConfig,
    MemoryConfig,
    MetricsConfig,
    NotificationConfig,
    OnboardConfig,
    SafetyConfig,
    TaskBreakdownConfig,
    TelegramConfig,
    TransportConfig,
)
from village.probes.repo import find_git_root

TMUX_SESSION = "village"
DEFAULT_WORKTREES_DIR_NAME = ".worktrees"
DEFAULT_AGENT = "worker"
DEFAULT_MAX_WORKERS = 2
DEFAULT_SCM_KIND = "git"
DEFAULT_QUEUE_TTL_MINUTES = 5

logger = logging.getLogger(__name__)


def _parse_config_file(config_path: Path) -> dict[str, str]:
    if not config_path.exists():
        return {}

    parser = configparser.ConfigParser()
    parser.read(config_path)

    config = {}

    if "DEFAULT" in parser:
        for key, value in parser["DEFAULT"].items():
            config[key.upper()] = value

    for section in parser.sections():
        for key, value in parser[section].items():
            if section == "DEFAULT":
                continue
            config[f"{section}.{key}"] = value

    return config


def _normalize_config(config: dict[str, str]) -> dict[str, str]:
    normalized = dict(config)
    for key, value in config.items():
        if "." in key:
            flat = key.upper().replace(".", "_")
            if flat not in normalized:
                normalized[flat] = value
    return normalized


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
    ("telegram", TelegramConfig),
    ("transport", TransportConfig),
]


def _build_sub_configs(file_config: dict[str, str]) -> dict[str, object]:
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
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    transport: TransportConfig = field(default_factory=TransportConfig)


def get_global_config() -> GlobalConfig:
    raw_config = _load_global_config()
    file_config = _normalize_config(raw_config)
    sub_configs = _build_sub_configs(file_config)
    return GlobalConfig(**sub_configs)


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
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    transport: TransportConfig = field(default_factory=TransportConfig)

    def __post_init__(self) -> None:
        self._config_path = self.village_dir / "config"
        self.locks_dir = self.village_dir / "locks"
        self.traces_dir = self.village_dir / "traces"

    @property
    def config_path(self) -> Path:
        return self._config_path

    def config_exists(self) -> bool:
        return self._config_path.exists()

    def ensure_exists(self) -> None:
        logger.debug(f"Creating {self.village_dir}")
        self.village_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Creating {self.locks_dir}")
        self.locks_dir.mkdir(exist_ok=True)
        logger.debug(f"Creating {self.traces_dir}")
        self.traces_dir.mkdir(exist_ok=True)
        logger.debug(f"Creating {self.worktrees_dir}")
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)


def get_config() -> Config:
    git_root = find_git_root()
    return _build_config(git_root)


def get_config_for_cwd(cwd: str | Path) -> Config:
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
    village_dir = Path(os.environ.get("VILLAGE_DIR", git_root / ".village"))
    worktrees_dir = Path(
        os.environ.get(
            "VILLAGE_WORKTREES_DIR",
            git_root / DEFAULT_WORKTREES_DIR_NAME,
        )
    )

    config_path = village_dir / "config"
    global_config = _load_global_config()
    project_config = _parse_config_file(config_path)
    file_config = _merge_configs(global_config, project_config)

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

    scm_kind = os.environ.get("VILLAGE_SCM") or file_config.get("SCM_KIND") or DEFAULT_SCM_KIND

    default_agent = os.environ.get("VILLAGE_DEFAULT_AGENT") or file_config.get("DEFAULT_AGENT") or DEFAULT_AGENT

    sub_configs = _build_sub_configs(file_config)

    agents: dict[str, AgentConfig] = {}
    for key, value in file_config.items():
        if key.startswith("agent.") or key.startswith("AGENT."):
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
                agents[agent_name].acp_capabilities = [cap.strip().lower() for cap in value.split(",") if cap.strip()]

    validation_errors = []
    for agent_name, agent_config in agents.items():
        errors = _validate_acp_agent(agent_name, agent_config)
        validation_errors.extend(errors)

    if validation_errors:
        error_msg = "Agent configuration errors:\n" + "\n".join(f"  - {e}" for e in validation_errors)
        logger.error(error_msg)

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
