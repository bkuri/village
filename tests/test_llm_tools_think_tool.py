"""Tests for Think tool mapping."""

from village.llm.tools import THINK_TOOL, MCPToolMapping


class TestThinkToolMapping:
    """Test Think tool mapping."""

    def test_think_tool_mapping_creation(self):
        """Test THINK_TOOL mapping can be created."""
        mapping = MCPToolMapping(
            server="think_tool",
            tool="think",
        )
        assert mapping.server == "think_tool"
        assert mapping.tool == "think"


class TestThinkToolDefinition:
    """Test Think tool definition."""

    def test_think_tool_name(self):
        """Test THINK_TOOL has correct name."""
        assert THINK_TOOL.name == "think"

    def test_think_tool_description(self):
        """Test THINK_TOOL has description."""
        assert THINK_TOOL.description
        assert len(THINK_TOOL.description) > 10

    def test_think_tool_input_schema(self):
        """Test THINK_TOOL has input schema."""
        assert THINK_TOOL.input_schema
        assert "type" in THINK_TOOL.input_schema
        assert THINK_TOOL.input_schema["type"] == "object"
        assert "properties" in THINK_TOOL.input_schema
        assert "thought" in THINK_TOOL.input_schema["properties"]
        assert THINK_TOOL.input_schema["required"] == ["thought"]
