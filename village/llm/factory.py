"""Factory for creating LLM and MCP clients."""

import logging
import os
from typing import TYPE_CHECKING

from village.config import Config
from village.llm.client import LLMClient
from village.llm.mcp import MCPClient, MCPUseClient
from village.llm.providers.anthropic import AnthropicClient
from village.llm.providers.ollama import OllamaClient
from village.llm.providers.openrouter import OpenRouterClient

if TYPE_CHECKING:
    from village.extensibility.server_discovery import MCPServer

logger = logging.getLogger(__name__)


def get_llm_client(config: Config, agent_name: str | None = None) -> LLMClient:
    """
    Factory to get LLM client based on config.

    Priority order:
    1. Agent-specific override (if agent_name provided)
    2. Global LLM config

    Args:
        config: Village configuration
        agent_name: Optional agent name for per-agent override

    Returns:
        LLM client instance

    Raises:
        ValueError: If provider is unknown
    """
    provider = config.llm.provider
    model = config.llm.model
    api_key = None

    # Check for agent-specific override
    if agent_name and agent_name in config.agents:
        agent_config = config.agents[agent_name]
        if agent_config.llm_provider:
            provider = agent_config.llm_provider
        if agent_config.llm_model:
            model = agent_config.llm_model

    logger.debug(f"Creating LLM client: provider={provider}, model={model}")

    if provider == "anthropic":
        api_key = os.getenv(config.llm.api_key_env)
        if not api_key:
            raise ValueError(
                f"Anthropic API key not found. Set {config.llm.api_key_env} environment variable."
            )
        return AnthropicClient(api_key=api_key, model=model)

    elif provider == "openrouter":
        api_key = os.getenv(config.llm.api_key_env)
        if not api_key:
            raise ValueError(
                f"OpenRouter API key not found. Set {config.llm.api_key_env} environment variable."
            )
        return OpenRouterClient(api_key=api_key, model=model)

    elif provider == "ollama":
        # Ollama doesn't need API key
        # Check if OLLAMA_BASE_URL is set, otherwise use default
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return OllamaClient(base_url=base_url, model=model)

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def get_mcp_client(
    config: Config, discovered_servers: list["MCPServer"] | None = None
) -> MCPClient | None:
    """
    Factory to get MCP client based on config.

    Args:
        config: Village configuration
        discovered_servers: Optional list of discovered MCP servers

    Returns:
        MCP client instance, or None if MCP is disabled
    """
    if not config.mcp.enabled:
        logger.debug("MCP disabled in config")
        return None

    logger.debug(f"Creating MCP client: type={config.mcp.client_type}")

    if discovered_servers is not None:
        logger.info(
            f"Discovered {len(discovered_servers)} MCP servers: "
            f"{', '.join(s.name for s in discovered_servers)}"
        )

    if config.mcp.client_type == "mcp-use":
        return MCPUseClient(mcp_use_path=config.mcp.mcp_use_path)

    else:
        raise ValueError(f"Unknown MCP client type: {config.mcp.client_type}")
