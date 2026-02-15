"""Server discovery hooks for dynamic MCP server management."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class MCPServer:
    """MCP server specification."""

    name: str
    type: str  # e.g., "stdio", "sse"
    command: str
    args: list[str] | None = None
    env: dict[str, str] | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        """Initialize optional fields."""
        if self.args is None:
            self.args = []
        if self.env is None:
            self.env = {}


class ServerDiscovery(ABC):
    """Base class for dynamic MCP server discovery.

    Allows domains to customize which MCP servers are loaded based on
    availability, configuration, and runtime conditions.

    Example:
        class TradingServerDiscovery(ServerDiscovery):
            async def discover_servers(self) -> list[MCPServer]:
                # Load Jesse backtesting server only if strategy is defined
                servers = [
                    MCPServer(
                        name="perplexity",
                        type="stdio",
                        command="perplexity-mcp"
                    )
                ]
                if self.strategy_path.exists():
                    servers.append(
                        MCPServer(
                            name="jesse",
                            type="stdio",
                            command="jesse-mcp",
                            args=[str(self.strategy_path)]
                        )
                    )
                return servers
    """

    @abstractmethod
    async def discover_servers(self) -> list[MCPServer]:
        """Discover available MCP servers.

        Returns:
            List of MCPServer specifications to load
        """
        pass

    @abstractmethod
    async def filter_servers(self, servers: list[MCPServer]) -> list[MCPServer]:
        """Filter discovered servers.

        Can be used to disable certain servers based on conditions.

        Args:
            servers: List of discovered servers

        Returns:
            Filtered list of servers to load
        """
        pass

    @abstractmethod
    async def should_load_server(self, server: MCPServer) -> bool:
        """Determine if server should be loaded.

        Args:
            server: Server to check

        Returns:
            True if server should be loaded
        """
        pass


class DefaultServerDiscovery(ServerDiscovery):
    """Default server discovery with no servers."""

    async def discover_servers(self) -> list[MCPServer]:
        """Return empty list."""
        return []

    async def filter_servers(self, servers: list[MCPServer]) -> list[MCPServer]:
        """Return servers unchanged."""
        return servers

    async def should_load_server(self, server: MCPServer) -> bool:
        """Always load enabled servers."""
        return server.enabled
