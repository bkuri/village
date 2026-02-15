"""Extension loader for initializing extensions from config."""

import importlib
import logging
from typing import Optional

from village.config import Config
from village.extensibility.beads_integrators import BeadsIntegrator
from village.extensibility.context import ChatContext
from village.extensibility.llm_adapters import LLMProviderAdapter
from village.extensibility.processors import ChatProcessor
from village.extensibility.registry import ExtensionRegistry
from village.extensibility.server_discovery import MCPServer, ServerDiscovery
from village.extensibility.thinking_refiners import ThinkingRefiner
from village.extensibility.tool_invokers import ToolInvoker

logger = logging.getLogger(__name__)


def load_extension_class(module_path: str, class_name: Optional[str] = None) -> object:
    """Load an extension class from a module path.

    Args:
        module_path: Python module path (e.g., "mydomain.extensibility")
        class_name: Class name to load (if None, uses last component of module_path)

    Returns:
        Instantiated extension object

    Raises:
        ImportError: If module cannot be imported
        AttributeError: If class cannot be found
    """
    if class_name is None:
        class_name = module_path.split(".")[-1]

    module = importlib.import_module(module_path)
    extension_class = getattr(module, class_name)
    return extension_class()


async def discover_mcp_servers(registry: ExtensionRegistry) -> list[MCPServer]:
    """Discover MCP servers using ServerDiscovery extension.

    Args:
        registry: Extension registry with ServerDiscovery registered

    Returns:
        List of discovered and filtered MCP servers
    """
    server_discovery = registry.get_server_discovery()

    discovered_servers = await server_discovery.discover_servers()
    logger.debug(f"Discovered {len(discovered_servers)} MCP servers")

    filtered_servers = await server_discovery.filter_servers(discovered_servers)
    logger.debug(f"Filtered to {len(filtered_servers)} MCP servers")

    enabled_servers = []
    for server in filtered_servers:
        should_load = await server_discovery.should_load_server(server)
        if should_load:
            enabled_servers.append(server)
            logger.debug(f"Enabled server: {server.name} ({server.type})")
        else:
            logger.debug(f"Skipped server: {server.name} (disabled by should_load_server)")

    logger.info(f"Total enabled MCP servers: {len(enabled_servers)}")
    return enabled_servers


async def initialize_extensions(config: Config) -> ExtensionRegistry:
    """Initialize extension registry from config.

    Loads domain-specific extension implementations from config if specified,
    otherwise uses default implementations.

    Args:
        config: Village configuration

    Returns:
        Initialized ExtensionRegistry
    """
    registry = ExtensionRegistry()

    if not config.extensions.enabled:
        logger.debug("Extensions disabled in config, using defaults")
        return registry

    ext_config = config.extensions

    if ext_config.processor_module:
        try:
            processor = load_extension_class(ext_config.processor_module)
            if isinstance(processor, ChatProcessor):
                registry.register_processor(processor)
                logger.info(f"Loaded ChatProcessor: {ext_config.processor_module}")
        except Exception as e:
            logger.warning(f"Failed to load ChatProcessor: {e}")

    if ext_config.tool_invoker_module:
        try:
            invoker = load_extension_class(ext_config.tool_invoker_module)
            if isinstance(invoker, ToolInvoker):
                registry.register_tool_invoker(invoker)
                logger.info(f"Loaded ToolInvoker: {ext_config.tool_invoker_module}")
        except Exception as e:
            logger.warning(f"Failed to load ToolInvoker: {e}")

    if ext_config.thinking_refiner_module:
        try:
            refiner = load_extension_class(ext_config.thinking_refiner_module)
            if isinstance(refiner, ThinkingRefiner):
                registry.register_thinking_refiner(refiner)
                logger.info(f"Loaded ThinkingRefiner: {ext_config.thinking_refiner_module}")
        except Exception as e:
            logger.warning(f"Failed to load ThinkingRefiner: {e}")

    if ext_config.chat_context_module:
        try:
            context_ext = load_extension_class(ext_config.chat_context_module)
            if isinstance(context_ext, ChatContext):
                registry.register_chat_context(context_ext)
                logger.info(f"Loaded ChatContext: {ext_config.chat_context_module}")
        except Exception as e:
            logger.warning(f"Failed to load ChatContext: {e}")

    if ext_config.beads_integrator_module:
        try:
            integrator = load_extension_class(ext_config.beads_integrator_module)
            if isinstance(integrator, BeadsIntegrator):
                registry.register_beads_integrator(integrator)
                logger.info(f"Loaded BeadsIntegrator: {ext_config.beads_integrator_module}")
        except Exception as e:
            logger.warning(f"Failed to load BeadsIntegrator: {e}")

    if ext_config.server_discovery_module:
        try:
            discovery = load_extension_class(ext_config.server_discovery_module)
            if isinstance(discovery, ServerDiscovery):
                registry.register_server_discovery(discovery)
                logger.info(f"Loaded ServerDiscovery: {ext_config.server_discovery_module}")
        except Exception as e:
            logger.warning(f"Failed to load ServerDiscovery: {e}")

    if ext_config.llm_adapter_module:
        try:
            adapter = load_extension_class(ext_config.llm_adapter_module)
            if isinstance(adapter, LLMProviderAdapter):
                registry.register_llm_adapter(adapter)
                logger.info(f"Loaded LLMAdapter: {ext_config.llm_adapter_module}")
        except Exception as e:
            logger.warning(f"Failed to load LLMAdapter: {e}")

    logger.info(f"Extension registry initialized: {registry.get_all_names()}")
    return registry
