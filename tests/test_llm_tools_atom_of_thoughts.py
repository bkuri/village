"""Tests for Atom of Thoughts tool mapping."""

from pathlib import Path

from village.config import Config, MCPConfig
from village.llm.tools import (
    ATOM_OF_THOUGHTS,
    ATOM_OF_THOUGHTS_TOOL,
    MCPToolMapping,
    format_mcp_tool_name,
)


class TestAtomOfThoughtsMapping:
    """Test Atom of Thoughts tool mapping."""

    def test_atom_of_thoughts_mapping_creation(self):
        """Test ATOM_OF_THOUGHTS mapping can be created."""
        mapping = MCPToolMapping(
            server="atom_of_thoughts",
            tool="AoT-light",
        )
        assert mapping.server == "atom_of_thoughts"
        assert mapping.tool == "AoT-light"

    def test_atom_of_thoughts_format_method(self):
        """Test mapping.format() method works with custom pattern."""
        mapping = MCPToolMapping(
            server="atom_of_thoughts",
            tool="AoT-light",
        )
        result = mapping.format("custom_{server}_{tool}")
        assert result == "custom_atom_of_thoughts_AoT-light"

    def test_atom_of_thoughts_format_with_mcproxy_pattern(self):
        """Test mapping works with mcproxy pattern."""
        mapping = MCPToolMapping(
            server="atom_of_thoughts",
            tool="AoT-light",
        )
        result = mapping.format("mcproxy_{server}__{tool}")
        assert result == "mcproxy_atom_of_thoughts__AoT-light"


class TestAtomOfThoughtsToolDefinition:
    """Test Atom of Thoughts tool definition."""

    def test_atom_of_thoughts_tool_exists(self):
        """Test ATOM_OF_THOUGHTS_TOOL is defined."""
        assert ATOM_OF_THOUGHTS_TOOL is not None
        assert hasattr(ATOM_OF_THOUGHTS_TOOL, "name")
        assert hasattr(ATOM_OF_THOUGHTS_TOOL, "description")
        assert hasattr(ATOM_OF_THOUGHTS_TOOL, "input_schema")

    def test_atom_of_thoughts_tool_name(self):
        """Test ATOM_OF_THOUGHTS_TOOL has correct name."""
        assert ATOM_OF_THOUGHTS_TOOL.name == "aot_light"

    def test_atom_of_thoughts_tool_description(self):
        """Test ATOM_OF_THOUGHTS_TOOL has description."""
        assert ATOM_OF_THOUGHTS_TOOL.description
        assert len(ATOM_OF_THOUGHTS_TOOL.description) > 10

    def test_atom_of_thoughts_tool_input_schema(self):
        """Test ATOM_OF_THOUGHTS_TOOL has input schema."""
        assert ATOM_OF_THOUGHTS_TOOL.input_schema
        assert "type" in ATOM_OF_THOUGHTS_TOOL.input_schema
        assert ATOM_OF_THOUGHTS_TOOL.input_schema["type"] == "object"


class TestFormatMcpToolName:
    """Test format_mcp_tool_name function."""

    def test_format_with_config_none(self):
        """Test format_mcp_tool_name creates default config when None."""
        mock_mcp = MCPConfig(tool_name_pattern="mcproxy_{server}__{tool}")
        config = Config(
            git_root=Path("/tmp"),
            village_dir=Path("/tmp/.village"),
            worktrees_dir=Path("/tmp/.worktrees"),
            mcp=mock_mcp,
        )
        result = format_mcp_tool_name(ATOM_OF_THOUGHTS, config)
        assert result == "mcproxy_atom_of_thoughts__AoT-light"

    def test_format_with_config_pattern(self):
        """Test format_mcp_tool_name with custom pattern."""
        mock_mcp = MCPConfig(tool_name_pattern="test_{server}__{tool}")
        config = Config(
            git_root=Path("/tmp"),
            village_dir=Path("/tmp/.village"),
            worktrees_dir=Path("/tmp/.worktrees"),
            mcp=mock_mcp,
        )
        result = format_mcp_tool_name(ATOM_OF_THOUGHTS, config)
        assert result == "test_atom_of_thoughts__AoT-light"
