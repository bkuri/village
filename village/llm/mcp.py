"""MCP client abstraction for tool invocation."""

import asyncio
import json
import logging
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MCPToolDefinition:
    """Tool definition from MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]


class MCPClient(ABC):
    """MCP server client abstraction."""

    @abstractmethod
    async def invoke_tool(
        self,
        server_name: str,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> str:
        """Invoke tool on MCP server."""
        pass

    @abstractmethod
    async def list_tools(self, server_name: str) -> list[MCPToolDefinition]:
        """List available tools on MCP server."""
        pass


class MCPUseClient(MCPClient):
    """Wrapper around mcp-use CLI."""

    def __init__(self, mcp_use_path: str = "mcp-use"):
        """Initialize mcp-use client.

        Args:
            mcp_use_path: Path to mcp-use binary
        """
        self.mcp_use_path = mcp_use_path

    async def invoke_tool(
        self,
        server_name: str,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> str:
        """Call mcp-use to invoke tool.

        Args:
            server_name: MCP server name
            tool_name: Tool name to invoke
            tool_input: Tool input parameters

        Returns:
            Tool result as string

        Raises:
            subprocess.CalledProcessError: If mcp-use fails
            subprocess.TimeoutExpired: If invocation times out
        """
        cmd = [
            self.mcp_use_path,
            "call",
            server_name,
            tool_name,
            json.dumps(tool_input),
        ]

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"mcp-use call failed: {e.stderr}")
            raise
        except subprocess.TimeoutExpired:
            logger.error(f"mcp-use call timed out: {tool_name}")
            raise

    async def list_tools(self, server_name: str) -> list[MCPToolDefinition]:
        """List available tools on MCP server.

        Args:
            server_name: MCP server name

        Returns:
            List of tool definitions
        """
        cmd = [self.mcp_use_path, "list-tools", server_name]

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )

            data = json.loads(result.stdout)
            tools = [
                MCPToolDefinition(
                    name=t["name"],
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                )
                for t in data.get("tools", [])
            ]
            return tools
        except subprocess.CalledProcessError as e:
            logger.error(f"mcp-use list-tools failed: {e.stderr}")
            raise
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse mcp-use output: {e}")
            raise
        except subprocess.TimeoutExpired:
            logger.error(f"mcp-use list-tools timed out: {server_name}")
            raise
