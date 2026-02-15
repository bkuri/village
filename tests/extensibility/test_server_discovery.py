"""Test ServerDiscovery ABC and DefaultServerDiscovery."""

import pytest

from village.extensibility.server_discovery import (
    DefaultServerDiscovery,
    MCPServer,
    ServerDiscovery,
)


class TestMCPServer:
    """Test MCPServer dataclass."""

    def test_mcp_server_initialization(self):
        """Test MCPServer initialization with required fields."""
        server = MCPServer(
            name="test-server",
            type="stdio",
            command="python",
        )
        assert server.name == "test-server"
        assert server.type == "stdio"
        assert server.command == "python"
        assert server.args == []
        assert server.env == {}
        assert server.enabled is True

    def test_mcp_server_with_args(self):
        """Test MCPServer with args."""
        args = ["-m", "server", "--port", "8080"]
        server = MCPServer(
            name="test-server",
            type="stdio",
            command="python",
            args=args,
        )
        assert server.args == args

    def test_mcp_server_with_env(self):
        """Test MCPServer with environment variables."""
        env = {"API_KEY": "secret", "DEBUG": "true"}
        server = MCPServer(
            name="test-server",
            type="stdio",
            command="python",
            env=env,
        )
        assert server.env == env

    def test_mcp_server_enabled_true(self):
        """Test MCPServer with enabled=True."""
        server = MCPServer(
            name="test-server",
            type="stdio",
            command="python",
            enabled=True,
        )
        assert server.enabled is True

    def test_mcp_server_enabled_false(self):
        """Test MCPServer with enabled=False."""
        server = MCPServer(
            name="test-server",
            type="stdio",
            command="python",
            enabled=False,
        )
        assert server.enabled is False

    def test_mcp_server_all_fields(self):
        """Test MCPServer with all fields."""
        args = ["-m", "server"]
        env = {"VAR": "value"}
        server = MCPServer(
            name="full-server",
            type="sse",
            command="node",
            args=args,
            env=env,
            enabled=True,
        )

        assert server.name == "full-server"
        assert server.type == "sse"
        assert server.command == "node"
        assert server.args == args
        assert server.env == env
        assert server.enabled is True

    def test_mcp_server_none_args_becomes_empty(self):
        """Test that None args becomes empty list via post_init."""
        server = MCPServer(
            name="test-server",
            type="stdio",
            command="python",
            args=None,
        )
        assert server.args == []

    def test_mcp_server_none_env_becomes_empty(self):
        """Test that None env becomes empty dict via post_init."""
        server = MCPServer(
            name="test-server",
            type="stdio",
            command="python",
            env=None,
        )
        assert server.env == {}

    def test_mcp_server_mutation(self):
        """Test that MCPServer fields can be mutated."""
        server = MCPServer(
            name="test-server",
            type="stdio",
            command="python",
        )
        server.args.append("--verbose")
        server.env["NEW_VAR"] = "value"

        assert "--verbose" in server.args
        assert server.env["NEW_VAR"] == "value"


class TestDefaultServerDiscovery:
    """Test DefaultServerDiscovery behavior."""

    @pytest.mark.asyncio
    async def test_discover_servers_returns_empty_list(self):
        """Test that discover_servers returns empty list."""
        discovery = DefaultServerDiscovery()
        result = await discovery.discover_servers()

        assert result == []
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_filter_servers_returns_unchanged(self):
        """Test that filter_servers returns servers unchanged."""
        discovery = DefaultServerDiscovery()
        servers = [
            MCPServer(
                name="server1",
                type="stdio",
                command="python",
            ),
            MCPServer(
                name="server2",
                type="sse",
                command="node",
            ),
        ]

        result = await discovery.filter_servers(servers)

        assert result == servers
        assert len(result) == 2
        assert result[0].name == "server1"
        assert result[1].name == "server2"

    @pytest.mark.asyncio
    async def test_filter_servers_with_empty_list(self):
        """Test filter_servers with empty list."""
        discovery = DefaultServerDiscovery()
        result = await discovery.filter_servers([])

        assert result == []

    @pytest.mark.asyncio
    async def test_should_load_server_checks_enabled_true(self):
        """Test should_load_server returns True for enabled servers."""
        discovery = DefaultServerDiscovery()
        server = MCPServer(
            name="test-server",
            type="stdio",
            command="python",
            enabled=True,
        )

        result = await discovery.should_load_server(server)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_load_server_checks_enabled_false(self):
        """Test should_load_server returns False for disabled servers."""
        discovery = DefaultServerDiscovery()
        server = MCPServer(
            name="test-server",
            type="stdio",
            command="python",
            enabled=False,
        )

        result = await discovery.should_load_server(server)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_load_server_with_multiple_servers(self):
        """Test should_load_server with multiple servers."""
        discovery = DefaultServerDiscovery()

        servers = [
            MCPServer(
                name="enabled1",
                type="stdio",
                command="python",
                enabled=True,
            ),
            MCPServer(
                name="disabled1",
                type="stdio",
                command="python",
                enabled=False,
            ),
            MCPServer(
                name="enabled2",
                type="stdio",
                command="python",
                enabled=True,
            ),
        ]

        results = [await discovery.should_load_server(s) for s in servers]

        assert results == [True, False, True]


class TestCustomServerDiscovery:
    """Test custom ServerDiscovery implementations."""

    @pytest.mark.asyncio
    async def test_custom_discovery_returns_servers(self):
        """Test custom discovery that returns servers."""

        class StaticDiscovery(ServerDiscovery):
            async def discover_servers(self) -> list[MCPServer]:
                return [
                    MCPServer(
                        name="server1",
                        type="stdio",
                        command="python",
                    ),
                    MCPServer(
                        name="server2",
                        type="sse",
                        command="node",
                    ),
                ]

            async def filter_servers(self, servers: list[MCPServer]) -> list[MCPServer]:
                return servers

            async def should_load_server(self, server: MCPServer) -> bool:
                return server.enabled

        discovery = StaticDiscovery()
        servers = await discovery.discover_servers()

        assert len(servers) == 2
        assert servers[0].name == "server1"
        assert servers[1].name == "server2"

    @pytest.mark.asyncio
    async def test_custom_discovery_filters_servers(self):
        """Test custom discovery that filters servers."""

        class FilteringDiscovery(ServerDiscovery):
            async def discover_servers(self) -> list[MCPServer]:
                return []

            async def filter_servers(self, servers: list[MCPServer]) -> list[MCPServer]:
                return [s for s in servers if s.name.startswith("prod-")]

            async def should_load_server(self, server: MCPServer) -> bool:
                return server.enabled

        discovery = FilteringDiscovery()
        servers = [
            MCPServer(
                name="prod-server1",
                type="stdio",
                command="python",
            ),
            MCPServer(
                name="dev-server1",
                type="stdio",
                command="python",
            ),
            MCPServer(
                name="prod-server2",
                type="stdio",
                command="python",
            ),
        ]

        filtered = await discovery.filter_servers(servers)

        assert len(filtered) == 2
        assert all(s.name.startswith("prod-") for s in filtered)

    @pytest.mark.asyncio
    async def test_custom_discovery_conditionally_loads(self):
        """Test custom discovery that conditionally loads servers."""

        class ConditionalDiscovery(ServerDiscovery):
            async def discover_servers(self) -> list[MCPServer]:
                return []

            async def filter_servers(self, servers: list[MCPServer]) -> list[MCPServer]:
                return servers

            async def should_load_server(self, server: MCPServer) -> bool:
                return server.enabled and server.type == "stdio"

        discovery = ConditionalDiscovery()
        servers = [
            MCPServer(
                name="stdio-enabled",
                type="stdio",
                command="python",
                enabled=True,
            ),
            MCPServer(
                name="sse-enabled",
                type="sse",
                command="node",
                enabled=True,
            ),
            MCPServer(
                name="stdio-disabled",
                type="stdio",
                command="python",
                enabled=False,
            ),
        ]

        results = [await discovery.should_load_server(s) for s in servers]

        assert results == [True, False, False]

    @pytest.mark.asyncio
    async def test_custom_discovery_with_workflow(self):
        """Test custom discovery with full discover/filter/load workflow."""

        class WorkflowDiscovery(ServerDiscovery):
            async def discover_servers(self) -> list[MCPServer]:
                return [
                    MCPServer(
                        name="server1",
                        type="stdio",
                        command="python",
                        enabled=True,
                    ),
                    MCPServer(
                        name="server2",
                        type="sse",
                        command="node",
                        enabled=False,
                    ),
                    MCPServer(
                        name="server3",
                        type="stdio",
                        command="python",
                        enabled=True,
                    ),
                ]

            async def filter_servers(self, servers: list[MCPServer]) -> list[MCPServer]:
                return [s for s in servers if s.type == "stdio"]

            async def should_load_server(self, server: MCPServer) -> bool:
                return server.enabled

        discovery = WorkflowDiscovery()

        discovered = await discovery.discover_servers()
        assert len(discovered) == 3

        filtered = await discovery.filter_servers(discovered)
        assert len(filtered) == 2
        assert all(s.type == "stdio" for s in filtered)

        to_load = [s for s in filtered if await discovery.should_load_server(s)]
        assert len(to_load) == 2
        assert all(s.enabled for s in to_load)

    @pytest.mark.asyncio
    async def test_custom_discovery_with_state(self):
        """Test custom discovery that maintains state."""

        class StatefulDiscovery(ServerDiscovery):
            def __init__(self):
                self.discovery_count = 0
                self.loaded_servers = []

            async def discover_servers(self) -> list[MCPServer]:
                self.discovery_count += 1
                return [
                    MCPServer(
                        name="server1",
                        type="stdio",
                        command="python",
                    ),
                ]

            async def filter_servers(self, servers: list[MCPServer]) -> list[MCPServer]:
                return servers

            async def should_load_server(self, server: MCPServer) -> bool:
                if server.name not in self.loaded_servers:
                    self.loaded_servers.append(server.name)
                    return True
                return False

        discovery = StatefulDiscovery()

        await discovery.discover_servers()
        assert discovery.discovery_count == 1

        await discovery.discover_servers()
        assert discovery.discovery_count == 2

        server = MCPServer(
            name="server1",
            type="stdio",
            command="python",
        )

        assert await discovery.should_load_server(server) is True
        assert await discovery.should_load_server(server) is False

        assert discovery.loaded_servers == ["server1"]

    @pytest.mark.asyncio
    async def test_custom_discovery_dynamic_servers(self):
        """Test custom discovery that dynamically generates servers."""

        class DynamicDiscovery(ServerDiscovery):
            def __init__(self, config: dict[str, object]):
                self.config = config

            async def discover_servers(self) -> list[MCPServer]:
                servers = []
                for i in range(self.config.get("count", 3)):
                    servers.append(
                        MCPServer(
                            name=f"dynamic-server-{i}",
                            type="stdio",
                            command="python",
                        )
                    )
                return servers

            async def filter_servers(self, servers: list[MCPServer]) -> list[MCPServer]:
                return servers

            async def should_load_server(self, server: MCPServer) -> bool:
                return server.enabled

        discovery = DynamicDiscovery({"count": 5})
        servers = await discovery.discover_servers()

        assert len(servers) == 5
        for i, server in enumerate(servers):
            assert server.name == f"dynamic-server-{i}"


class TestServerDiscoveryABC:
    """Test that ServerDiscovery ABC cannot be instantiated directly."""

    def test_server_discovery_cannot_be_instantiated(self):
        """Test that abstract ServerDiscovery cannot be instantiated."""
        with pytest.raises(TypeError):
            ServerDiscovery()

    def test_custom_discovery_must_implement_all_methods(self):
        """Test that custom discovery must implement all abstract methods."""

        class IncompleteDiscovery(ServerDiscovery):
            async def discover_servers(self) -> list[MCPServer]:
                return []

            async def filter_servers(self, servers: list[MCPServer]) -> list[MCPServer]:
                return servers

        with pytest.raises(TypeError):
            IncompleteDiscovery()
