"""Tests for ST → AoT Light strategy integration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from village.chat.baseline import BaselineReport
from village.chat.sequential_thinking import (
    TaskBreakdown,
    _build_aot_light_atomization_prompt,
    _build_st_analysis_prompt,
    _st_aot_light_strategy,
)
from village.config import Config, MCPConfig


class TestBuildStAnalysisPrompt:
    """Test ST analysis prompt builder."""

    def test_st_analysis_prompt_includes_requirements(self):
        """Test that ST analysis prompt asks for requirements."""
        baseline = BaselineReport(
            title="Implement feature X",
            reasoning="Need to add X functionality",
        )

        prompt = _build_st_analysis_prompt(baseline)

        assert "requirements" in prompt
        assert "technical_constraints" in prompt
        assert "system_components" in prompt
        assert "Implement feature X" in prompt

    def test_st_analysis_prompt_includes_beads_context(self):
        """Test that ST analysis prompt includes beads context when provided."""
        baseline = BaselineReport(
            title="Implement feature X",
            reasoning="Need to add X functionality",
        )
        beads_state = "Existing task: bd-123: Add login"

        prompt = _build_st_analysis_prompt(baseline, beads_state)

        assert "Existing task: bd-123: Add login" in prompt
        assert "dependencies on existing work" in prompt

    def test_st_analysis_prompt_includes_config(self):
        """Test that ST analysis prompt uses config for tool name."""
        mock_mcp = MCPConfig(tool_name_pattern="test_{server}__{tool}")
        config = Config(
            git_root=Path("/tmp"),
            village_dir=Path("/tmp/.village"),
            worktrees_dir=Path("/tmp/.worktrees"),
            mcp=mock_mcp,
        )

        baseline = BaselineReport(
            title="Implement feature X",
            reasoning="Need to add X functionality",
        )

        prompt = _build_st_analysis_prompt(baseline, config=config)

        assert "test_sequential_thinking__sequentialthinking" in prompt


class TestBuildAotLightAtomizationPrompt:
    """Test AoT-light atomization prompt builder."""

    def test_aot_light_prompt_includes_analysis(self):
        """Test that AoT-light prompt includes Sequential Thinking analysis."""
        baseline = BaselineReport(
            title="Implement feature X",
            reasoning="Need to add X functionality",
        )

        analysis = {
            "analysis": {
                "requirements": ["Add authentication"],
                "technical_constraints": ["Must use OAuth 2.0"],
                "system_components": ["User service", "Auth service"],
            },
            "summary": "Analysis complete",
        }

        prompt = _build_aot_light_atomization_prompt(analysis, baseline)

        assert "Add authentication" in prompt
        assert "User service" in prompt
        assert "Auth service" in prompt
        assert "Implement feature X" in prompt

    def test_aot_light_prompt_includes_atomic_requirements(self):
        """Test that AoT-light prompt specifies atomic task requirements."""
        baseline = BaselineReport(
            title="Implement feature X",
            reasoning="Need to add X functionality",
        )

        analysis = {
            "analysis": {
                "requirements": ["Add authentication"],
            }
        }

        prompt = _build_aot_light_atomization_prompt(analysis, baseline)

        assert "atomic, queueable tasks" in prompt
        assert "1-4 hours" in prompt
        assert "executed independently" in prompt
        assert "testable and verifiable" in prompt

    def test_aot_light_prompt_has_correct_json_format(self):
        """Test that AoT-light prompt has correct JSON schema in output."""
        baseline = BaselineReport(
            title="Implement feature X",
            reasoning="Need to add X functionality",
        )

        analysis = {
            "analysis": {
                "requirements": ["Test requirement"],
            }
        }

        prompt = _build_aot_light_atomization_prompt(analysis, baseline)

        assert '"items"' in prompt
        assert '"title"' in prompt
        assert '"description"' in prompt
        assert '"estimated_effort"' in prompt
        assert '"success_criteria"' in prompt
        assert '"dependencies"' in prompt


class TestStAotLightStrategy:
    """Test ST → AoT Light strategy implementation."""

    @pytest.fixture
    def baseline(self) -> BaselineReport:
        """Create test baseline."""
        return BaselineReport(
            title="Implement authentication",
            reasoning="Need to add OAuth 2.0 authentication",
        )

    @pytest.fixture
    def config(self) -> Config:
        """Create test config."""
        mock_mcp = MCPConfig(tool_name_pattern="mcproxy_{server}__{tool}")
        return Config(
            git_root=Path("/tmp"),
            village_dir=Path("/tmp/.village"),
            worktrees_dir=Path("/tmp/.worktrees"),
            mcp=mock_mcp,
        )

    @patch("village.chat.sequential_thinking.get_llm_client")
    def test_st_aot_light_runs_two_llm_calls(self, mock_get_llm, baseline, config):
        """Test that ST → AoT Light makes two LLM calls (analysis + atomization)."""
        from village.llm import LLMClient

        mock_client = MagicMock(spec=LLMClient)
        mock_client.supports_tools = True
        mock_get_llm.return_value = mock_client

        mock_client.call.side_effect = [
            '{"analysis": {"requirements": ["auth"]}, "summary": "analysis"}',
            '{"items": [{"title": "Task 1"}], "summary": "tasks"}',
        ]

        result = _st_aot_light_strategy(baseline, config)

        assert mock_client.call.call_count == 2
        assert isinstance(result, TaskBreakdown)
        assert len(result.items) == 1
        assert result.items[0].title == "Task 1"

    @patch("village.chat.sequential_thinking.get_llm_client")
    def test_st_aot_light_parses_analysis_successfully(self, mock_get_llm, baseline, config):
        """Test that ST → AoT Light successfully parses Sequential Thinking analysis."""
        from village.llm import LLMClient

        mock_client = MagicMock(spec=LLMClient)
        mock_client.supports_tools = True
        mock_get_llm.return_value = mock_client

        mock_client.call.side_effect = [
            '{"analysis": {"requirements": ["auth"], "technical_constraints": ["oauth"]}, "summary": "Analysis"}',
            '{"items": [{"title": "Auth setup", "description": "Setup auth", "estimated_effort": "2 hours", "success_criteria": ["auth works"], "dependencies": [], "tags": []}], "summary": "Tasks"}',
        ]

        result = _st_aot_light_strategy(baseline, config)

        assert len(result.items) == 1
        assert result.items[0].title == "Auth setup"
        assert result.items[0].description == "Setup auth"
        assert result.items[0].estimated_effort == "2 hours"

    @patch("village.chat.sequential_thinking.get_llm_client")
    def test_st_aot_light_fallback_on_analysis_parse_error(self, mock_get_llm, baseline, config):
        """Test that ST → AoT Light uses fallback when analysis parsing fails."""
        from village.llm import LLMClient

        mock_client = MagicMock(spec=LLMClient)
        mock_client.supports_tools = True
        mock_get_llm.return_value = mock_client

        mock_client.call.side_effect = [
            "Invalid JSON",  # Analysis fails to parse
            '{"items": [{"title": "Task 1"}], "summary": "tasks"}',
        ]

        result = _st_aot_light_strategy(baseline, config)

        assert isinstance(result, TaskBreakdown)
        assert len(result.items) == 1
        assert result.items[0].title == "Task 1"

    @patch("village.chat.sequential_thinking.get_llm_client")
    def test_st_aot_light_includes_tool_calls(self, mock_get_llm, baseline, config):
        """Test that ST → AoT Light includes Sequential Thinking and AoT-light tools."""
        from village.llm import LLMClient

        mock_client = MagicMock(spec=LLMClient)
        mock_client.supports_tools = True
        mock_get_llm.return_value = mock_client

        mock_client.call.side_effect = [
            '{"analysis": {}, "summary": "analysis"}',
            '{"items": [{"title": "Task 1"}], "summary": "tasks"}',
        ]

        _st_aot_light_strategy(baseline, config)

        # Check that tools were passed to the LLM calls
        calls = mock_client.call.call_args_list
        assert len(calls) == 2

        # First call should have Sequential Thinking tool
        first_call = calls[0]
        tools_kwarg = first_call.kwargs.get("tools") or (
            first_call.args[2] if len(first_call.args) > 2 else None
        )
        assert tools_kwarg is not None
        tools_str = str(tools_kwarg)
        assert (
            "sequentialthinking" in tools_str.lower() or "sequential_thinking" in tools_str.lower()
        )

        # Second call should have AoT-light tool
        second_call = calls[1]
        tools_kwarg = second_call.kwargs.get("tools") or (
            second_call.args[2] if len(second_call.args) > 2 else None
        )
        assert tools_kwarg is not None
        tools_str = str(tools_kwarg)
        assert (
            "aot_light" in tools_str.lower()
            or "AoT-light" in tools_str
            or "atom_of_thoughts" in tools_str.lower()
        )
